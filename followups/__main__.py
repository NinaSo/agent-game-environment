import argparse
from contextlib import closing
import json
from pathlib import Path

from .studies import connect, generate_config, replay, report
from game_lab.pipeline import run_study


def main():
    parser = argparse.ArgumentParser(
        description="Independent known-reward and fixed-opponent PD checks"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--out", type=Path, default=Path("followups/configs"))
    gen.add_argument("--models", nargs="+", help="One or more model IDs on the selected backend")
    execute = sub.add_parser("run")
    execute.add_argument("config", type=Path)
    execute.add_argument("--db", type=Path, required=True)
    execute.add_argument("--provider-config", type=Path, help="Backend JSON; defaults to local Ollama")
    for name in ("replay", "report"):
        child = sub.add_parser(name)
        child.add_argument("db", type=Path)
        if name == "report":
            child.add_argument("--out", type=Path, default=Path("results/followups"))
    args = parser.parse_args()
    if args.command == "generate":
        args.out.mkdir(parents=True, exist_ok=True)
        result = []
        for smoke in (False, True):
            config = generate_config(smoke, models=args.models)
            path = args.out / (config["run_id"] + ".json")
            text = json.dumps(config, indent=2) + "\n"
            if path.exists() and path.read_text() != text:
                raise ValueError(
                    "Refusing to overwrite a different frozen configuration"
                )
            path.write_text(text)
            result.append(str(path))
    elif args.command == "run":
        backend = json.loads(args.provider_config.read_text()) if args.provider_config else None
        result = run_study("followups", json.loads(args.config.read_text()), args.db, backend)
    elif args.command == "report":
        result = report(args.db, args.out)
        result = {"out": str(args.out), "cases": len(result["cases"])}
    else:
        with closing(connect(args.db, readonly=True)) as db:
            db.execute("BEGIN")
            result = replay(db)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
