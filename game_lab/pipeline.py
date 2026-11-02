"""Default collection entry point: unit tests, backend preflight, smoke, then study."""

from contextlib import closing
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from .engine import canonical, digest, legal_actions

ROOT = Path(__file__).resolve().parents[1]


def source_hashes():
    paths = list(ROOT.glob("*.py")) + [ROOT / "pyproject.toml"]
    for directory in ("game_lab", "followups", "diagnostic", "communication", "tests"):
        paths.extend((ROOT / directory).glob("*.py"))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)}


def _unit_tests(log_path, key_env=None):
    # Tests use fake providers; credentials are unnecessary in the test subprocess.
    env = {k: v for k, v in os.environ.items()
           if not k.endswith("API_KEY") and k != key_env}
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    command = [sys.executable, "-m", "pytest", "-q", str(ROOT / "tests")]
    with log_path.open("w") as log:
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=180, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ValueError(f"Unit-test gate timed out; see {log_path}") from exc
    if result.returncode:
        raise ValueError(f"Unit-test gate failed (exit {result.returncode}); see {log_path}")
    return {"status": "passed", "command": command, "log": str(log_path)}


def _modules(study):
    if study == "game":
        from . import runner, store
        return runner, store
    if study == "followups":
        from followups import studies
        return studies, studies
    if study == "diagnostic":
        from diagnostic import collection
        from followups import studies
        return collection, studies
    raise ValueError("Study must be game, followups or diagnostic")


def models_for(study, config):
    if study == "game":
        return sorted({m for ep in config["episodes"] for m in ep["players"]
                       if not m.startswith("script:")})
    return sorted({c["model"] for c in config["cases"]})


def smoke_config(study, config):
    """Cover each configured interface/model; smoke evidence is a separate sample."""
    if study != "game":
        if study == "followups":
            from followups.studies import generate_config
        else:
            from diagnostic.design import generate_config
        return generate_config(True, models=config.get("models"))
    result = copy.deepcopy(config)
    chosen = {}
    for ep in config["episodes"]:
        key = (ep["task"], ep["condition"], tuple(ep["players"]), tuple(legal_actions(ep)))
        if key not in chosen:
            sample = copy.deepcopy(ep)
            sample.update(id="smoke-" + ep["id"], block_id="smoke-" + ep["block_id"],
                          horizon=min(3, ep["horizon"]))
            if "switch_after" in sample:
                sample["switch_after"] = min(1, sample["horizon"])
            chosen[key] = sample
    result.update(run_id="automatic_smoke_" + config["run_id"], phase="excluded_smoke",
                  episodes=list(chosen.values()), max_attempts=3,
                  max_calls=sum(ep["horizon"] * 2 * 3 for ep in chosen.values()),
                  max_seconds=max(600, len(chosen) * 120))
    return result


def verify_complete(study, path, expected_config):
    collector, storage = _modules(study)
    table = "episodes" if study == "game" else "cases"
    count = len(expected_config[table])
    with closing(storage.connect(path, readonly=True)) as db:
        db.execute("BEGIN")
        recorded = json.loads(db.execute("SELECT value FROM manifest WHERE key='config'").fetchone()[0])
        if recorded != expected_config:
            raise ValueError("Gate database does not match its planned configuration")
        verified = collector.replay(db)
        states = {r[0]: r[1] for r in db.execute(f"SELECT status,COUNT(*) FROM {table} GROUP BY status")}
        if states != {"complete": count}:
            raise ValueError(f"Collection is not complete: {states}; expected {count} complete {table}")
        return {"status": "passed", "completed": count, "replay": verified}


class _PinnedProvider:
    """Reject a backend identity change between smoke and main initialization."""

    def __init__(self, provider, provenance):
        self.provider = provider
        self.provenance = provenance

    @property
    def timeout(self):
        return self.provider.timeout

    @timeout.setter
    def timeout(self, value):
        self.provider.timeout = value

    def metadata(self, models):
        current = self.provider.metadata(models)
        if current != self.provenance:
            raise ValueError("Backend/model metadata changed after preflight; main collection blocked")
        return current

    def choose(self, *args, **kwargs):
        return self.provider.choose(*args, **kwargs)

    def request(self, *args, **kwargs):
        return self.provider.request(*args, **kwargs)


def record_gate(db, gate):
    if gate is None:
        return  # Low-level collectors are also used by isolated unit tests.
    existing = db.execute("SELECT value FROM manifest WHERE key='preflight'").fetchone()
    if existing and json.loads(existing[0])["binding"] != gate["binding"]:
        raise ValueError("Resume refused: preflight binding changed")
    with db:
        db.execute("INSERT OR REPLACE INTO manifest VALUES ('preflight',?)", (canonical(gate),))


def run_study(study, config, db_path, provider_config=None):
    """All supported CLIs call here; there is deliberately no skip-gates switch."""
    from .adapters import make_provider, validate_provider_config
    collector, _ = _modules(study)
    collector.validate_config(config)
    backend = validate_provider_config(provider_config)
    path = Path(db_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    audit = path.parent / (path.name + ".preflight")
    audit.mkdir(exist_ok=True)
    report_path = audit / "gate.json"
    report = {"status": "running", "study": study, "started_at": time.time()}

    def save():
        temporary = report_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        temporary.replace(report_path)

    with path.with_suffix(path.suffix + ".pipeline.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another pipeline owns this study database") from exc
        try:
            if path.exists():
                from .provider import refuse_fatal_resume
                _, storage = _modules(study)
                with closing(storage.connect(path, readonly=True)) as db:
                    refuse_fatal_resume(db)
            code = source_hashes()
            report["stage"] = "unit_tests"
            save()
            report["unit_tests"] = _unit_tests(audit / "unit_tests.log", backend.get("api_key_env"))
            if source_hashes() != code:
                raise ValueError("Source changed during unit tests; collection blocked")
            report["stage"] = "backend_preflight"
            save()
            provider = make_provider(backend, timeout=config.get("timeout_seconds", 120))
            models = models_for(study, config)
            provenance = provider.metadata(models) if models else {"provider": "scripted", "models": {}}
            provider = _PinnedProvider(provider, provenance)
            binding = digest({"study": study, "config": config, "backend": backend,
                              "provider": provenance, "source": code})
            report.update(binding=binding, backend=backend, provider=provenance, source_hashes=code)
            # Reject an incompatible old journal before spending calls on smoke.
            if path.exists():
                from .provider import metadata_matches
                _, storage = _modules(study)
                with closing(storage.connect(path, readonly=True)) as db:
                    has_manifest = db.execute("SELECT 1 FROM sqlite_master WHERE name='manifest'").fetchone()
                    old = {r[0]: json.loads(r[1]) for r in db.execute("SELECT key,value FROM manifest")} if has_manifest else {}
                if old and (old.get("config") != config or old.get("source_hashes") != collector.source_hashes()
                            or not metadata_matches(old["provider"], provenance, models)
                            or ("preflight" in old and old["preflight"]["binding"] != binding)):
                    raise ValueError("Resume refused: existing collection differs from this configuration, source or backend")
            smoke_only = config.get("phase") == "excluded_smoke"
            smoke = copy.deepcopy(config) if smoke_only else smoke_config(study, config)
            smoke_path = path if smoke_only else audit / binding / "smoke.sqlite"
            design_path = audit / binding / "config.json"
            design_path.parent.mkdir(parents=True, exist_ok=True)
            design_path.write_text(json.dumps(smoke, indent=2) + "\n")
            report.update(stage="smoke", smoke_database=str(smoke_path))
            save()
            smoke_result = collector.run(smoke, smoke_path, provider=provider)
            report["smoke"] = verify_complete(study, smoke_path, smoke)
            if source_hashes() != code:
                raise ValueError("Source changed during smoke; main collection blocked")
            gate = {"binding": binding, "unit_tests": report["unit_tests"],
                    "smoke": report["smoke"], "smoke_database": str(smoke_path),
                    "source_hashes": code, "backend": backend, "provider": provenance, "passed_at": time.time()}
            report.update(stage="smoke_complete" if smoke_only else "main", preflight_status="passed")
            save()
            if smoke_only:
                _, storage = _modules(study)
                with closing(storage.connect(path)) as db:
                    record_gate(db, gate)
                result = smoke_result
            else:
                result = collector.run(config, path, provider=provider, preflight=gate)
            report["collection"] = result
            report["verification"] = verify_complete(study, path, config)
            report.update(status="passed", stage="complete", finished_at=time.time())
            save()
            return {"status": "passed", "gate_report": str(report_path), "collection": result}
        except Exception as exc:
            # Provider exceptions must contain no credentials (adapter contract).
            report.update(status="blocked", error=str(exc), finished_at=time.time())
            save()
            raise
