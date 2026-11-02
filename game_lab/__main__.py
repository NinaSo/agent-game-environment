"""Run with `python -m game_lab --help` from the project directory."""

import argparse
import json
from pathlib import Path
import sys

from .runner import replay
from .pipeline import run_study
from .store import connect, export_data, status


def main():
    if sys.argv[1:2] == ["suite"]:
        from .suite import main as suite_main
        return suite_main(sys.argv[2:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.epilog = "Complete experiment with controls: python -m game_lab suite --help"
    sub = parser.add_subparsers(dest="command", required=True)
    execute = sub.add_parser("run")
    execute.add_argument("config", type=Path)
    execute.add_argument("--db", type=Path, required=True)
    execute.add_argument("--provider-config", type=Path, help="Backend JSON; defaults to local Ollama")
    for command in ("status", "replay", "export"):
        child = sub.add_parser(command)
        child.add_argument("db", type=Path)
        if command == "export":
            child.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "run":
        backend = json.loads(args.provider_config.read_text()) if args.provider_config else None
        result = run_study("game", json.loads(args.config.read_text()), args.db, backend)
    else:
        with connect(args.db.resolve(), readonly=True) as db:
            if args.command == "export":
                args.out.mkdir(parents=True, exist_ok=True)
                destination = args.out / "trace.json"
                destination.write_text(
                    json.dumps(export_data(db), indent=2, allow_nan=False) + "\n"
                )
                result = {"export": str(destination.resolve())}
            else:
                result = status(db) if args.command == "status" else replay(db)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
