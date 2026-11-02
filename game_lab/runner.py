"""Bounded local execution. Both choices use one prior-round state."""

import fcntl
import json
import math
from pathlib import Path
import platform
import time

import numpy as np

from .engine import (
    canonical,
    digest,
    legal_actions,
    observation,
    parse_action,
    prompt,
    scripted_choice,
    seed_for,
    transition,
    validate_episode,
)
from .provider import (Ollama, ProviderError, choice_payload, metadata_matches,
                       record_fatal, refuse_fatal_resume, verify_adapter_response)
from .store import commit_round, connect, history, manifest, status


DEFAULT_OPTIONS = {"temperature": 0.7, "top_p": 0.9, "num_ctx": 8192, "num_predict": 64}


def source_hashes():
    import hashlib

    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path(__file__).parent.glob("*.py"))
    }


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError("Configuration must be an object")
    if not isinstance(config.get("run_id"), str) or not config["run_id"]:
        raise ValueError("Nonempty run_id required")
    if not isinstance(config.get("episodes"), list) or not config["episodes"]:
        raise ValueError("Nonempty episode list required")
    for ep in config["episodes"]:
        if not isinstance(ep, dict):
            raise ValueError("Each episode must be an object")
        validate_episode(ep)
    if len({ep["id"] for ep in config["episodes"]}) != len(config["episodes"]):
        raise ValueError("Duplicate episode IDs")
    for name, default in [
        ("max_calls", 10000),
        ("max_seconds", 86400),
        ("max_attempts", 3),
    ]:
        if type(config.get(name, default)) is not int or config.get(name, default) < 1:
            raise ValueError(f"{name} must be positive integer")
    if config.get("max_attempts", 3) > 5:
        raise ValueError("At most five attempts are allowed")
    timeout = config.get("timeout_seconds", 120)
    if (
        type(timeout) not in (float, int)
        or not math.isfinite(timeout)
        or not 0 < timeout <= 300
    ):
        raise ValueError("timeout_seconds must be finite and in (0,300]")
    if not isinstance(config.get("inference", {}), dict):
        raise ValueError("Inference settings must be an object")
    options = {**DEFAULT_OPTIONS, **config.get("inference", {})}
    if set(options) != set(DEFAULT_OPTIONS):
        raise ValueError("Only frozen, supported inference options are accepted")
    if (
        type(options["num_ctx"]) is not int
        or not 2048 <= options["num_ctx"] <= 32768
        or type(options["num_predict"]) is not int
        or not 16 <= options["num_predict"] <= 256
    ):
        raise ValueError("Invalid context/generation budget")
    if (
        any(
            type(options[k]) not in (float, int) or not math.isfinite(options[k])
            for k in ("temperature", "top_p")
        )
        or not 0 <= options["temperature"] <= 2
        or not 0 < options["top_p"] <= 1
    ):
        raise ValueError("Invalid sampling options")
    return options


def _initialize(db, config, provider, models, options):
    code = source_hashes()
    existing = manifest(db)
    if existing:
        if existing["config"] != config or existing["source_hashes"] != code:
            raise ValueError("Resume refused: configuration or source code changed")
        if existing["runtime"] != {
            "python": platform.python_version(),
            "numpy": np.__version__,
        }:
            raise ValueError("Resume refused: runtime changed")
        if models:
            current = provider.metadata(models)
            old = existing["provider"]
            if not metadata_matches(old, current, models):
                raise ValueError("Resume refused: provider/model version changed")
        return
    provenance = (
        provider.metadata(models) if models else {"provider": "scripted", "models": {}}
    )
    metadata = {
        "config": config,
        "source_hashes": code,
        "provider": provenance,
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
        "inference": options,
        "elapsed_seconds": 0,
        "randomness": {
            "generator": "numpy.PCG64",
            "seed_mapping": "uint64(first16hex(SHA256(canonical([episode.seed, namespace, block_id, player, trial, arm?]))))",
            "environment_namespace": "environment",
            "baseline_namespace": "baseline",
            "decoder_namespace": "decoder",
            "state": "fresh generator for every keyed draw; no advancing shared state",
        },
        "prompt_version": "1",
        "script_version": "1",
    }
    with db:
        for key, value in metadata.items():
            db.execute("INSERT INTO manifest VALUES (?,?)", (key, canonical(value)))
        for ep in config["episodes"]:
            db.execute(
                "INSERT INTO episodes(id,config) VALUES (?,?)",
                (ep["id"], canonical(ep)),
            )


def _attempt(
    db,
    ep,
    player,
    trial,
    provider,
    options,
    max_attempts,
    calls_remaining,
    deadline=None,
):
    key = (ep["id"], player, trial)
    row = db.execute(
        "SELECT * FROM decisions WHERE episode_id=? AND player=? AND trial=?", key
    ).fetchone()
    if row["action"] is not None:
        return 0
    prior = db.execute(
        "SELECT COUNT(*) FROM attempts WHERE episode_id=? AND player=? AND trial=?", key
    ).fetchone()[0]
    if prior >= max_attempts:
        with db:
            db.execute(
                "UPDATE episodes SET status='incomplete', error='Attempt budget exhausted after interruption' WHERE id=?",
                (ep["id"],),
            )
        return 0
    model = ep["players"][player]
    count = 0
    for number in range(prior + 1, max_attempts + 1):
        if (
            count >= calls_remaining
            or deadline is not None
            and time.monotonic() >= deadline
        ):
            return count
        with db:
            db.execute(
                "INSERT INTO attempts(episode_id,player,trial,attempt,status) VALUES (?,?,?,?,'started')",
                (*key, number),
            )
        start = time.monotonic()
        response = {}
        try:
            if model.startswith("script:"):
                action = scripted_choice(
                    model[7:], ep, json.loads(row["observation"]), player
                )
                response = {
                    "raw": canonical({"choice": action}),
                    "latency": 0.0,
                    "usage": {},
                    "envelope": {
                        "scripted": True,
                        "privileged": model == "script:oracle",
                    },
                }
            else:
                old_timeout = getattr(provider, "timeout", None)
                if deadline is not None and old_timeout is not None:
                    provider.timeout = min(
                        old_timeout, max(0.01, deadline - time.monotonic())
                    )
                try:
                    response = provider.choose(
                        model,
                        row["prompt"],
                        legal_actions(ep),
                        options,
                        seed_for(ep["seed"], "decoder", ep["block_id"], player, trial)
                        % (2**31),
                    )
                finally:
                    if old_timeout is not None:
                        provider.timeout = old_timeout
            count += 1
            action = parse_action(response["raw"], legal_actions(ep))
            with db:
                db.execute(
                    "UPDATE attempts SET status='valid', raw=?, latency=?, usage=?, envelope=? WHERE episode_id=? AND player=? AND trial=? AND attempt=?",
                    (
                        response["raw"],
                        response.get("latency", time.monotonic() - start),
                        canonical(response.get("usage", {})),
                        canonical(response.get("envelope", {})),
                        *key,
                        number,
                    ),
                )
                db.execute(
                    "UPDATE decisions SET action=? WHERE episode_id=? AND player=? AND trial=? AND action IS NULL",
                    (action, *key),
                )
            return count
        except (ProviderError, ValueError, TypeError, KeyError) as exc:
            if not response:
                count += 1
            transient = isinstance(exc, ProviderError) and exc.transient
            raw = response.get("raw")
            if raw is None and isinstance(exc, ProviderError) and exc.raw is not None:
                raw = exc.raw if isinstance(exc.raw, str) else canonical(exc.raw)
            with db:
                db.execute(
                    "UPDATE attempts SET status=?, raw=?, latency=?, usage=?, envelope=?, error=? WHERE episode_id=? AND player=? AND trial=? AND attempt=?",
                    (
                        "transport_error" if transient else "invalid",
                        raw,
                        time.monotonic() - start,
                        canonical(response.get("usage", {})),
                        canonical(response.get("envelope", {})),
                        str(exc),
                        *key,
                        number,
                    ),
                )
                if not transient or number == max_attempts:
                    db.execute(
                        "UPDATE episodes SET status=?, error=? WHERE id=?",
                        ("incomplete" if transient else "invalid", str(exc), ep["id"]),
                    )
                if isinstance(exc, ProviderError) and exc.fatal:
                    record_fatal(db, exc)
            if isinstance(exc, ProviderError) and exc.fatal:
                raise
            if not transient:
                return count
            if number < max_attempts:
                time.sleep(min(0.1 * 2 ** (number - 1), 1))
    return count


def run(config, db_path, provider=None, preflight=None):
    """Low-level collector. Use pipeline.run_study for automatically gated collection."""
    options = validate_config(config)
    db_path = Path(db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with db_path.with_suffix(db_path.suffix + ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another runner owns this database") from exc
        db = connect(db_path)
        start = time.monotonic()
        try:
            refuse_fatal_resume(db)
            models = sorted(
                {
                    p
                    for ep in config["episodes"]
                    for p in ep["players"]
                    if not p.startswith("script:")
                }
            )
            provider = provider or Ollama(timeout=config.get("timeout_seconds", 120))
            _initialize(db, config, provider, models, options)
            from .pipeline import record_gate
            record_gate(db, preflight)
            elapsed = manifest(db)["elapsed_seconds"]
            # A crash with no persisted response is explicitly ambiguous; never pretend it succeeded.
            with db:
                db.execute(
                    "UPDATE attempts SET status='ambiguous', error='Runner interrupted before response was persisted' WHERE status='started'"
                )
            calls = db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
            max_calls = config.get("max_calls", 10000)
            deadline = start + max(0, config.get("max_seconds", 86400) - elapsed)
            while True:
                active = [
                    json.loads(r[0])
                    for r in db.execute(
                        "SELECT config FROM episodes WHERE status IN ('pending','running') ORDER BY id"
                    )
                ]
                if not active:
                    break
                # Complete a durable pending round even if the call budget was consumed before a crash.
                for ep in active:
                    past = history(db, ep["id"])
                    ready = db.execute(
                        "SELECT action FROM decisions WHERE episode_id=? AND trial=? ORDER BY player",
                        (ep["id"], len(past) + 1),
                    ).fetchall()
                    if len(ready) == 2 and all(r[0] is not None for r in ready):
                        commit_round(
                            db, ep, transition(ep, past, [r[0] for r in ready])
                        )
                active = [
                    json.loads(r[0])
                    for r in db.execute(
                        "SELECT config FROM episodes WHERE status IN ('pending','running') ORDER BY id"
                    )
                ]
                if not active or calls >= max_calls or time.monotonic() >= deadline:
                    break
                todo = []
                for ep in active:
                    past = history(db, ep["id"])
                    trial = len(past) + 1
                    with db:
                        db.execute(
                            "UPDATE episodes SET status='running' WHERE id=?",
                            (ep["id"],),
                        )
                        for player in (0, 1):
                            obs = observation(ep, past, player)
                            rendered = prompt(ep, obs)
                            db.execute(
                                "INSERT OR IGNORE INTO decisions VALUES (?,?,?,?,?,?,NULL)",
                                (
                                    ep["id"],
                                    player,
                                    trial,
                                    canonical(obs),
                                    rendered,
                                    digest({"observation": obs, "prompt": rendered}),
                                ),
                            )
                            saved = db.execute(
                                "SELECT * FROM decisions WHERE episode_id=? AND player=? AND trial=?",
                                (ep["id"], player, trial),
                            ).fetchone()
                            if saved["snapshot_hash"] != digest(
                                {"observation": obs, "prompt": rendered}
                            ):
                                raise ValueError(
                                    "Stored pre-decision snapshot does not match replay"
                                )
                            if saved["action"] is None:
                                todo.append(
                                    (ep["players"][player], ep["id"], player, ep, trial)
                                )
                for _, _, player, ep, trial in sorted(todo, key=lambda x: x[:3]):
                    if calls >= max_calls or time.monotonic() >= deadline:
                        break
                    if (
                        db.execute(
                            "SELECT status FROM episodes WHERE id=?", (ep["id"],)
                        ).fetchone()[0]
                        != "running"
                    ):
                        continue
                    calls += _attempt(
                        db,
                        ep,
                        player,
                        trial,
                        provider,
                        options,
                        config.get("max_attempts", 3),
                        max_calls - calls,
                        deadline,
                    )
                    with db:
                        db.execute(
                            "UPDATE manifest SET value=? WHERE key='elapsed_seconds'",
                            (canonical(elapsed + time.monotonic() - start),),
                        )
                for ep in active:
                    if (
                        db.execute(
                            "SELECT status FROM episodes WHERE id=?", (ep["id"],)
                        ).fetchone()[0]
                        != "running"
                    ):
                        continue
                    past = history(db, ep["id"])
                    actions = db.execute(
                        "SELECT action FROM decisions WHERE episode_id=? AND trial=? ORDER BY player",
                        (ep["id"], len(past) + 1),
                    ).fetchall()
                    if len(actions) == 2 and all(r[0] is not None for r in actions):
                        commit_round(
                            db, ep, transition(ep, past, [r[0] for r in actions])
                        )
                    elif not todo:
                        raise ValueError("No progress possible")
            return status(db)
        finally:
            db.close()


def replay(db):
    """Independently recompute states, prompts, raw choices, and scores from logged actions."""
    checked = 0
    recorded = manifest(db)
    configs = {ep["id"]: ep for ep in recorded["config"]["episodes"]}
    if set(configs) != {r[0] for r in db.execute("SELECT id FROM episodes")}:
        raise ValueError("Episode set differs from manifest")
    for row in db.execute("SELECT * FROM episodes ORDER BY id"):
        ep = json.loads(row["config"])
        if ep != configs[row["id"]]:
            raise ValueError("Episode configuration differs from manifest")
        past = []
        for stored in db.execute(
            "SELECT trial,result FROM rounds WHERE episode_id=? ORDER BY trial",
            (ep["id"],),
        ):
            result = json.loads(stored["result"])
            if stored["trial"] != len(past) + 1 or result["trial"] != stored["trial"]:
                raise ValueError("Round sequence mismatch")
            decisions = db.execute(
                "SELECT player,action FROM decisions WHERE episode_id=? AND trial=? ORDER BY player",
                (ep["id"], stored["trial"]),
            ).fetchall()
            if [r["player"] for r in decisions] != [0, 1] or [
                r["action"] for r in decisions
            ] != result["actions"]:
                raise ValueError(
                    "Committed round must have both matching durable decisions"
                )
            if transition(ep, past, result["actions"]) != result:
                raise ValueError(
                    f"Reward replay mismatch: {ep['id']} round {result['trial']}"
                )
            past.append(result)
        if row["status"] == "complete" and len(past) != ep["horizon"]:
            raise ValueError("False completed episode")
        for decision in db.execute(
            "SELECT * FROM decisions WHERE episode_id=? ORDER BY trial,player",
            (ep["id"],),
        ):
            trial, player = decision["trial"], decision["player"]
            if not 1 <= trial <= min(len(past) + 1, ep["horizon"]):
                raise ValueError("Decision is outside the observed round sequence")
            obs = observation(ep, past[: trial - 1], player)
            rendered = prompt(ep, obs)
            if (
                json.loads(decision["observation"]) != obs
                or decision["prompt"] != rendered
                or decision["snapshot_hash"]
                != digest({"observation": obs, "prompt": rendered})
            ):
                raise ValueError("Observation/prompt replay mismatch")
            if decision["action"] is not None:
                valid = db.execute(
                    "SELECT raw,envelope FROM attempts WHERE episode_id=? AND player=? AND trial=? AND status='valid'",
                    (ep["id"], player, trial),
                ).fetchall()
                if (
                    len(valid) != 1
                    or parse_action(valid[0][0], legal_actions(ep))
                    != decision["action"]
                ):
                    raise ValueError("Action does not match one valid attempt")
                if not ep["players"][player].startswith("script:"):
                    verify_adapter_response(
                        json.loads(valid[0]["envelope"]), valid[0]["raw"],
                        choice_payload(ep["players"][player], rendered, legal_actions(ep),
                                       recorded.get("inference", DEFAULT_OPTIONS),
                                       seed_for(ep["seed"], "decoder", ep["block_id"], player, trial) % 2**31),
                        recorded["provider"],
                    )
                if (
                    trial <= len(past)
                    and past[trial - 1]["actions"][player] != decision["action"]
                ):
                    raise ValueError("Committed action mismatch")
                checked += 1
    return {"verified_actions": checked, "status": "passed"}
