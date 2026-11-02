"""Frozen follow-up design, isolated collection journal, and descriptive reporting."""

import csv
from contextlib import closing
import fcntl
import hashlib
import itertools
import json
from pathlib import Path
import platform
import sqlite3
import time

import numpy as np

from game_lab.engine import canonical, digest, parse_action, seed_for
from game_lab.provider import (Ollama, ProviderError, choice_payload, metadata_matches,
                               record_fatal, refuse_fatal_resume, verify_adapter_response)
from game_lab.models import DEFAULT_MODELS, case_models, select_models


OPTIONS = {"temperature": 0.7, "top_p": 0.9, "num_ctx": 8192, "num_predict": 64}
MODELS = list(DEFAULT_MODELS)
PD_PAYOFFS = {
    (True, True): (3, 3),
    (True, False): (0, 5),
    (False, True): (5, 0),
    (False, False): (1, 1),
}


def build_case(case):
    """Single source of truth for disclosed evidence, prompt order, and scoring."""
    labels = list(case["label_pair"])
    shown = labels[:: 1 if case["prompt_order"] == 0 else -1]
    legal = labels[:: 1 if case["schema_order"] == 0 else -1]
    mapping = labels[case["mapping"]]
    if case["study"] == "known_reward":
        points = {label: 10 if label == mapping else 1 for label in labels}
        lines = [
            f"Option {label}: you receive {points[label]} {'point' if points[label] == 1 else 'points'}."
            for label in shown
        ]
        prompt = (
            "This is a single decision. Maximize your own points on this decision.\n"
        )
        prompt += "\n".join(lines)
    elif case["study"] == "fixed_opponent_pd":
        opponent = case["opponent_choice"]
        points = {
            label: PD_PAYOFFS[(label == mapping, opponent == mapping)][0]
            for label in labels
        }
        lines = []
        for own in shown:
            for other in labels:
                own_points, other_points = PD_PAYOFFS[
                    (own == mapping, other == mapping)
                ]
                lines.append(
                    f"Your choice {own}, opponent choice {other}: you receive {own_points} {'point' if own_points == 1 else 'points'}; opponent receives {other_points} {'point' if other_points == 1 else 'points'}."
                )
        prompt = "This game lasts exactly one round. Maximize YOUR points THIS ROUND.\n"
        prompt += "\n".join(lines)
        prompt += f"\nThe opponent's choice this round is fixed to {opponent}. Your choice cannot change it."
    else:
        raise ValueError("Unknown study")
    prompt += '\nReturn only a JSON object with exactly one field, "choice", set to your chosen option. No explanation.'
    answer = max(points, key=points.get)
    return {
        "prompt": prompt,
        "enum_order": legal,
        "answer": answer,
        "available_points": points,
        "first_shown": shown[0],
        "first_schema": legal[0],
    }


def generate_config(smoke=False, models=None):
    custom = models is not None
    models = select_models(models)
    cases = []
    for model in models:
        for labels, mapping, order, schema, repeat in itertools.product(
            ("AB", "XY", "KM"), range(2), range(2), range(2), range(5)
        ):
            cases.append(
                dict(
                    study="known_reward",
                    model=model,
                    label_pair=labels,
                    mapping=mapping,
                    prompt_order=order,
                    schema_order=schema,
                    repeat=repeat,
                    opponent_choice=None,
                )
            )
        for mapping, opponent, order, schema, repeat in itertools.product(
            range(2), "AB", range(2), range(2), range(5)
        ):
            cases.append(
                dict(
                    study="fixed_opponent_pd",
                    model=model,
                    label_pair="AB",
                    mapping=mapping,
                    prompt_order=order,
                    schema_order=schema,
                    repeat=repeat,
                    opponent_choice=opponent,
                )
            )
    for case in cases:
        case["id"] = digest(case)[:24]
        case["decoder_seed"] = (
            seed_for(20261028, "followup_decoder", case["id"]) % 2**31
        )
    cases.sort(
        key=lambda c: (c["model"], seed_for(20261028, "followup_order", c["id"]))
    )
    if smoke:
        cases = [
            next(c for c in cases if c["model"] == model and c["study"] == study)
            for model in models
            for study in ("known_reward", "fixed_opponent_pd")
        ]
    return {
        "version": 2 if custom else 1,
        **({"models": models} if custom else {}),
        "run_id": "payoff_checks_smoke" if smoke else "payoff_checks",
        "phase": "excluded_smoke" if smoke else "followup",
        "inference": OPTIONS.copy(),
        "max_calls": (6 if smoke else 240) * len(models),
        "max_seconds": (300 if smoke else 1800) * len(models),
        "max_attempts": 3,
        "timeout_seconds": 120,
        "cases": cases,
    }


def validate_config(config):
    if not isinstance(config, dict) or config.get("phase") not in (
        "followup",
        "excluded_smoke",
    ):
        raise ValueError("Unknown follow-up configuration")
    expected = generate_config(config["phase"] == "excluded_smoke", models=config.get("models"))
    for name in ("version", "run_id", "phase", "inference", "cases", "models"):
        if config.get(name) != expected.get(name):
            raise ValueError(f"Frozen design mismatch: {name}")
    if set(config) != set(expected):
        raise ValueError("Unknown or missing configuration field")
    for name in ("max_calls", "max_seconds", "max_attempts", "timeout_seconds"):
        if type(config[name]) is not int or not 1 <= config[name] <= expected[name]:
            raise ValueError(f"Invalid bounded budget: {name}")


SCHEMA = """
CREATE TABLE manifest (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE cases (id TEXT PRIMARY KEY, spec TEXT NOT NULL, evidence TEXT NOT NULL,
 snapshot_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', action TEXT, correct INTEGER, error TEXT);
CREATE TABLE attempts (case_id TEXT NOT NULL REFERENCES cases(id), attempt INTEGER NOT NULL,
 status TEXT NOT NULL, started_at REAL NOT NULL, raw TEXT, envelope TEXT, usage TEXT, latency REAL, error TEXT,
 PRIMARY KEY(case_id,attempt));
"""


def connect(path, readonly=False):
    path = Path(path).resolve()
    db = (
        sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        if readonly
        else sqlite3.connect(path)
    )
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    if not readonly:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
    return db


def metadata(db):
    return {
        r["key"]: json.loads(r["value"]) for r in db.execute("SELECT * FROM manifest")
    }


def source_hashes():
    root = Path(__file__).resolve().parent.parent
    paths = list((root / "followups").glob("*.py")) + [
        root / "game_lab" / name for name in ("engine.py", "provider.py", "models.py", "adapters.py", "pipeline.py")
    ]
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(paths)
    }


def _initialize(db, config, provider):
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='manifest'"
    ).fetchone()
    models = case_models(config)
    provenance = provider.metadata(models)
    current = {
        "config": config,
        "source_hashes": source_hashes(),
        "runtime": {"python": platform.python_version(), "numpy": np.__version__},
    }
    if exists:
        old = metadata(db)
        if any(old[k] != value for k, value in current.items()):
            raise ValueError("Resume refused: design, source, or runtime changed")
        if not metadata_matches(old["provider"], provenance, models):
            raise ValueError("Resume refused: provider/model changed")
        replay(db)
        return
    db.executescript("BEGIN IMMEDIATE;" + SCHEMA)
    with db:
        for key, value in {
            **current,
            "provider": provenance,
            "started_at": time.time(),
            "first_shown_definition": "first disclosed reward option / first own-action payoff-row group",
            "seed_schedule": "SHA256-derived independent decoder and ordering namespaces; full per-case seed stored",
        }.items():
            db.execute("INSERT INTO manifest VALUES (?,?)", (key, canonical(value)))
        for case in config["cases"]:
            evidence = build_case(case)
            db.execute(
                "INSERT INTO cases(id,spec,evidence,snapshot_hash) VALUES (?,?,?,?)",
                (case["id"], canonical(case), canonical(evidence), digest(evidence)),
            )


def status(db):
    return {
        "cases": {
            r[0]: r[1]
            for r in db.execute("SELECT status,COUNT(*) FROM cases GROUP BY status")
        },
        "attempts": {
            r[0]: r[1]
            for r in db.execute("SELECT status,COUNT(*) FROM attempts GROUP BY status")
        },
    }


def run(config, path, provider=None, preflight=None):
    """Low-level collector; CLI collection uses pipeline.run_study and its gates."""
    validate_config(config)
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another follow-up runner owns this database") from exc
        db = connect(path)
        try:
            refuse_fatal_resume(db)
            provider = provider or Ollama(timeout=config["timeout_seconds"])
            _initialize(db, config, provider)
            from game_lab.pipeline import record_gate
            record_gate(db, preflight)
            deadline = metadata(db)["started_at"] + config["max_seconds"]
            with db:
                db.execute(
                    "UPDATE attempts SET status='ambiguous',error='Interrupted before response persistence' WHERE status='started'"
                )
            calls = db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
            for case in config["cases"]:
                row = db.execute(
                    "SELECT * FROM cases WHERE id=?", (case["id"],)
                ).fetchone()
                if row["status"] != "pending":
                    continue
                evidence = json.loads(row["evidence"])
                prior = db.execute(
                    "SELECT COUNT(*) FROM attempts WHERE case_id=?", (case["id"],)
                ).fetchone()[0]
                if prior >= config["max_attempts"]:
                    with db:
                        db.execute(
                            "UPDATE cases SET status='incomplete',error='Attempt budget exhausted' WHERE id=?",
                            (case["id"],),
                        )
                    continue
                for attempt in range(prior + 1, config["max_attempts"] + 1):
                    if calls >= config["max_calls"] or time.time() >= deadline:
                        return status(db)
                    with db:
                        db.execute(
                            "INSERT INTO attempts(case_id,attempt,status,started_at) VALUES (?,?,'started',?)",
                            (case["id"], attempt, time.time()),
                        )
                    calls += 1
                    started = time.monotonic()
                    response = {}
                    previous_timeout = getattr(provider, "timeout", None)
                    if previous_timeout is not None:
                        provider.timeout = min(
                            config["timeout_seconds"], max(0.01, deadline - time.time())
                        )
                    try:
                        response = provider.choose(
                            case["model"],
                            evidence["prompt"],
                            evidence["enum_order"],
                            config["inference"],
                            case["decoder_seed"],
                        )
                        action = parse_action(response["raw"], evidence["enum_order"])
                        with db:
                            db.execute(
                                "UPDATE attempts SET status='valid',raw=?,envelope=?,usage=?,latency=? WHERE case_id=? AND attempt=?",
                                (
                                    response["raw"],
                                    canonical(response.get("envelope", {})),
                                    canonical(response.get("usage", {})),
                                    response.get("latency", time.monotonic() - started),
                                    case["id"],
                                    attempt,
                                ),
                            )
                            db.execute(
                                "UPDATE cases SET status='complete',action=?,correct=?,error=NULL WHERE id=?",
                                (action, int(action == evidence["answer"]), case["id"]),
                            )
                        break
                    except (ProviderError, ValueError, TypeError, KeyError) as exc:
                        transient = isinstance(exc, ProviderError) and exc.transient
                        raw = response.get("raw")
                        if (
                            raw is None
                            and isinstance(exc, ProviderError)
                            and exc.raw is not None
                        ):
                            raw = (
                                exc.raw
                                if isinstance(exc.raw, str)
                                else canonical(exc.raw)
                            )
                        with db:
                            db.execute(
                                "UPDATE attempts SET status=?,raw=?,envelope=?,usage=?,latency=?,error=? WHERE case_id=? AND attempt=?",
                                (
                                    "transport_error" if transient else "invalid",
                                    raw,
                                    canonical(response.get("envelope", {})),
                                    canonical(response.get("usage", {})),
                                    time.monotonic() - started,
                                    str(exc),
                                    case["id"],
                                    attempt,
                                ),
                            )
                            if not transient or attempt == config["max_attempts"]:
                                db.execute(
                                    "UPDATE cases SET status=?,error=? WHERE id=?",
                                    (
                                        "incomplete" if transient else "invalid",
                                        str(exc),
                                        case["id"],
                                    ),
                                )
                            if isinstance(exc, ProviderError) and exc.fatal:
                                record_fatal(db, exc)
                        if isinstance(exc, ProviderError) and exc.fatal:
                            raise
                        if not transient:
                            break
                        if attempt < config["max_attempts"]:
                            time.sleep(0.1 * 2 ** (attempt - 1))
                    finally:
                        if previous_timeout is not None:
                            provider.timeout = previous_timeout
            return status(db)
        finally:
            db.close()


def replay(db):
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Orphaned records violate case/attempt references")
    recorded = metadata(db)
    config = recorded["config"]
    validate_config(config)
    expected = {c["id"]: c for c in config["cases"]}
    rows = db.execute("SELECT * FROM cases").fetchall()
    if {r["id"] for r in rows} != set(expected):
        raise ValueError("Case set differs from frozen design")
    for row in rows:
        if row["status"] not in {"pending", "complete", "invalid", "incomplete"}:
            raise ValueError("Unknown case status")
        case = expected[row["id"]]
        evidence = build_case(case)
        if (
            json.loads(row["spec"]) != case
            or json.loads(row["evidence"]) != evidence
            or row["snapshot_hash"] != digest(evidence)
        ):
            raise ValueError("Stored prompt/evidence differs from frozen design")
        attempts = db.execute(
            "SELECT * FROM attempts WHERE case_id=? ORDER BY attempt", (row["id"],)
        ).fetchall()
        if [a["attempt"] for a in attempts] != list(range(1, len(attempts) + 1)) or len(
            attempts
        ) > config["max_attempts"]:
            raise ValueError("Invalid attempt sequence")
        if any(
            a["status"]
            not in {"started", "ambiguous", "valid", "invalid", "transport_error"}
            for a in attempts
        ):
            raise ValueError("Unknown attempt status")
        valid = [a for a in attempts if a["status"] == "valid"]
        if any(a["status"] in {"valid", "invalid"} for a in attempts[:-1]):
            raise ValueError("Attempt follows a terminal response")
        if (
            attempts
            and attempts[-1]["status"] == "invalid"
            and row["status"] != "invalid"
        ):
            raise ValueError("Final invalid response must mark the case invalid")
        if row["status"] == "invalid" and (
            not attempts or attempts[-1]["status"] != "invalid"
        ):
            raise ValueError("Invalid case lacks final invalid attempt")
        if row["status"] == "incomplete" and (
            len(attempts) != config["max_attempts"]
            or attempts[-1]["status"] not in {"transport_error", "ambiguous"}
        ):
            raise ValueError("Incomplete case has not exhausted its attempt budget")
        if row["status"] == "complete":
            if (
                len(valid) != 1
                or valid[0]["attempt"] != attempts[-1]["attempt"]
                or parse_action(valid[0]["raw"], evidence["enum_order"])
                != row["action"]
                or row["correct"] != int(row["action"] == evidence["answer"])
            ):
                raise ValueError("Accepted action or score differs from raw evidence")
            verify_adapter_response(
                json.loads(valid[0]["envelope"]), valid[0]["raw"],
                choice_payload(case["model"], evidence["prompt"], evidence["enum_order"],
                               config["inference"], case["decoder_seed"]), recorded["provider"],
            )
        elif valid or row["action"] is not None or row["correct"] is not None:
            raise ValueError("Uncommitted case contains accepted action")
    if db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] > config["max_calls"]:
        raise ValueError("Call budget exceeded")
    return {"status": "passed", "verified_cases": len(rows), **status(db)}


def report(path, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with closing(connect(path, readonly=True)) as db:
        db.execute("BEGIN")
        replay(db)
        manifest = metadata(db)
        cases = []
        for row in db.execute("SELECT * FROM cases ORDER BY id"):
            spec, evidence = json.loads(row["spec"]), json.loads(row["evidence"])
            complete = row["status"] == "complete"
            cases.append(
                {
                    **spec,
                    "status": row["status"],
                    "action": row["action"],
                    "answer": evidence["answer"],
                    "correct": row["correct"],
                    "attempt_count": db.execute(
                        "SELECT COUNT(*) FROM attempts WHERE case_id=?", (row["id"],)
                    ).fetchone()[0],
                    "first_shown": (
                        int(row["action"] == evidence["first_shown"])
                        if complete
                        else None
                    ),
                    "first_schema": (
                        int(row["action"] == evidence["first_schema"])
                        if complete
                        else None
                    ),
                    "literal_B": (
                        int(row["action"] == "B")
                        if complete and spec["label_pair"] == "AB"
                        else None
                    ),
                }
            )
        attempts = [
            {
                **dict(a),
                "envelope": json.loads(a["envelope"]) if a["envelope"] else None,
                "usage": json.loads(a["usage"]) if a["usage"] else None,
            }
            for a in db.execute("SELECT * FROM attempts ORDER BY case_id,attempt")
        ]
        evidence_rows = [
            {
                **dict(r),
                "spec": json.loads(r["spec"]),
                "evidence": json.loads(r["evidence"]),
            }
            for r in db.execute("SELECT * FROM cases ORDER BY id")
        ]
    summaries = []
    groupings = [(), ("study",), ("model",), ("study", "model")]
    groupings += [
        ("study", "model", field)
        for field in (
            "mapping",
            "label_pair",
            "prompt_order",
            "schema_order",
            "answer",
            "opponent_choice",
        )
    ]
    for fields in groupings:
        groups = {}
        for case in cases:
            groups.setdefault(tuple(case[k] for k in fields), []).append(case)
        for key, rows in sorted(groups.items()):
            valid = [r for r in rows if r["status"] == "complete"]
            item = {
                "group_by": "overall" if not fields else "+".join(fields),
                **dict(zip(fields, key)),
                "planned": len(rows),
                "accepted": len(valid),
                "correct": sum(r["correct"] for r in valid),
                "incorrect": sum(r["correct"] == 0 for r in valid),
                "invalid": sum(r["status"] == "invalid" for r in rows),
                "incomplete": sum(r["status"] == "incomplete" for r in rows),
                "pending": sum(r["status"] == "pending" for r in rows),
                "unattempted": sum(r["attempt_count"] == 0 for r in rows),
                "attempted_no_valid": sum(
                    r["attempt_count"] > 0 and r["status"] != "complete" for r in rows
                ),
            }
            item["accuracy_accepted"] = item["correct"] / len(valid) if valid else None
            item["accuracy_planned_lower"] = item["correct"] / len(rows)
            item["accuracy_planned_upper"] = (
                item["correct"] + len(rows) - len(valid)
            ) / len(rows)
            for metric in ("literal_B", "first_shown", "first_schema"):
                eligible = [r for r in valid if r[metric] is not None]
                item[metric + "_count"] = sum(r[metric] for r in eligible)
                item[metric + "_denominator"] = len(eligible)
                item[metric + "_rate"] = (
                    item[metric + "_count"] / len(eligible) if eligible else None
                )
            summaries.append(item)
    result = {
        "phase": manifest["config"]["phase"],
        "manifest": manifest,
        "summaries": summaries,
        "cases": cases,
        "inspection": [
            {
                "case_id": row["id"],
                "model": row["spec"]["model"],
                "study": row["spec"]["study"],
                "prompt": row["evidence"]["prompt"],
                "enum_order": row["evidence"]["enum_order"],
                "snapshot_hash": row["snapshot_hash"],
                "decoder_seed": row["spec"]["decoder_seed"],
                "raw_accepted_reply": next(
                    (
                        a["raw"]
                        for a in attempts
                        if a["case_id"] == row["id"] and a["status"] == "valid"
                    ),
                    None,
                ),
                "answer": row["evidence"]["answer"],
                "action": row["action"],
                "correct": row["correct"],
                "status": row["status"],
            }
            for row in evidence_rows
        ],
        "interpretation": "Descriptive one-shot checks. Repeated sampled responses are not independent game episodes; no internal mechanism or causal explanation is established.",
    }
    for name, rows in (("cases", cases), ("summary", summaries)):
        fields = list(dict.fromkeys(k for row in rows for k in row))
        with (out / (name + ".csv")).open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    (out / "report.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    (out / "evidence.json").write_text(
        json.dumps(
            {"manifest": manifest, "cases": evidence_rows, "attempts": attempts},
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )
    js = (
        json.dumps(result, allow_nan=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    (out / "data.js").write_text("window.FOLLOWUP_DATA = " + js + ";\n")
    return result
