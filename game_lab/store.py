"""SQLite journal: durable attempts/actions, atomic two-player outcomes."""

import json
import sqlite3

from .engine import canonical


SCHEMA = """
CREATE TABLE IF NOT EXISTS manifest (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS episodes (
 id TEXT PRIMARY KEY, config TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', error TEXT);
CREATE TABLE IF NOT EXISTS decisions (
 episode_id TEXT NOT NULL REFERENCES episodes(id), player INTEGER NOT NULL CHECK(player IN (0,1)),
 trial INTEGER NOT NULL, observation TEXT NOT NULL, prompt TEXT NOT NULL,
 snapshot_hash TEXT NOT NULL, action TEXT,
 PRIMARY KEY(episode_id,player,trial));
CREATE TABLE IF NOT EXISTS attempts (
 episode_id TEXT NOT NULL, player INTEGER NOT NULL, trial INTEGER NOT NULL,
 attempt INTEGER NOT NULL, status TEXT NOT NULL, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 raw TEXT, latency REAL, usage TEXT, envelope TEXT, error TEXT,
 PRIMARY KEY(episode_id,player,trial,attempt),
 FOREIGN KEY(episode_id,player,trial) REFERENCES decisions(episode_id,player,trial));
CREATE TABLE IF NOT EXISTS rounds (
 episode_id TEXT NOT NULL REFERENCES episodes(id), trial INTEGER NOT NULL, result TEXT NOT NULL,
 PRIMARY KEY(episode_id,trial));
"""


def connect(path, readonly=False):
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
        db.executescript(SCHEMA)
    return db


def history(db, episode_id):
    return [
        json.loads(row[0])
        for row in db.execute(
            "SELECT result FROM rounds WHERE episode_id=? ORDER BY trial", (episode_id,)
        )
    ]


def manifest(db):
    return {
        r["key"]: json.loads(r["value"])
        for r in db.execute("SELECT * FROM manifest ORDER BY key")
    }


def export_data(db):
    result = {"manifest": manifest(db)}
    json_columns = {"config", "observation", "usage", "envelope", "result"}
    for table, order in [
        ("episodes", "id"),
        ("decisions", "episode_id,player,trial"),
        ("attempts", "episode_id,player,trial,attempt"),
        ("rounds", "episode_id,trial"),
    ]:
        result[table] = [
            {
                k: json.loads(v) if k in json_columns and v is not None else v
                for k, v in dict(row).items()
            }
            for row in db.execute(f"SELECT * FROM {table} ORDER BY {order}")
        ]
    return result


def commit_round(db, ep, result):
    actions = db.execute(
        "SELECT player, action FROM decisions WHERE episode_id=? AND trial=? ORDER BY player",
        (ep["id"], result["trial"]),
    ).fetchall()
    if len(actions) != 2 or [r["action"] for r in actions] != result["actions"]:
        raise ValueError("Both durable actions must match the atomic round")
    with db:
        db.execute(
            "INSERT INTO rounds VALUES (?,?,?)",
            (ep["id"], result["trial"], canonical(result)),
        )
        status = "complete" if result["trial"] == ep["horizon"] else "running"
        db.execute(
            "UPDATE episodes SET status=?, error=NULL WHERE id=?", (status, ep["id"])
        )


def status(db):
    return {
        "episodes": {
            r[0]: r[1]
            for r in db.execute("SELECT status, COUNT(*) FROM episodes GROUP BY status")
        },
        "completed_rounds": db.execute("SELECT COUNT(*) FROM rounds").fetchone()[0],
        "accepted_actions": db.execute(
            "SELECT COUNT(*) FROM decisions WHERE action IS NOT NULL"
        ).fetchone()[0],
        "attempts": {
            r[0]: r[1]
            for r in db.execute("SELECT status,COUNT(*) FROM attempts GROUP BY status")
        },
    }
