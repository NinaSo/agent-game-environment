"""Freeze paired message conditions with an explicit cooperate/defect interface."""

import argparse
import itertools
import json
from pathlib import Path

from game_lab.engine import digest, seed_for
from game_lab.models import DEFAULT_MODELS, select_models
from game_lab.runner import validate_config


MODELS = DEFAULT_MODELS


def configuration(smoke=False, models=None):
    custom = models is not None
    models = select_models(models)
    phase = "smoke" if smoke else "main"
    seed = 20261029
    episodes = []
    for model, order, repeat in itertools.product(
        models, range(1 if smoke else 2), range(1 if smoke else 4)
    ):
        # Hash custom names to avoid collisions such as "model:tag" / "model-tag".
        identity = digest(model)[:24] if custom else model.replace(':', '-')
        block = f"semantic-{phase}-{identity}-order{order}-repeat{repeat}"
        for condition in ("semantic_neutral", "semantic_promise"):
            episodes.append(
                {
                    "id": f"{block}-{condition}",
                    "block_id": block,
                    "task": "pd",
                    "condition": condition,
                    "horizon": 3 if smoke else 30,
                    "players": [model, "script:switch"],
                    "seed": seed_for(seed, "communication_episode", block),
                    "cooperate_label": "cooperate",
                    "action_order": ["cooperate", "defect"][:: 1 if order == 0 else -1],
                    "switch_after": 1 if smoke else 10,
                    "presentation_order": order,
                    "sampling_repeat": repeat,
                }
            )
    episodes.sort(key=lambda ep: seed_for(seed, "communication_assignment", ep["id"]))
    config = {
        "run_id": f"semantic_messages_{phase}_20261029_v1",
        "seed": seed,
        "phase": "excluded_smoke" if smoke else "paired_semantic_messages",
        "episodes": episodes,
        "inference": {
            "temperature": 0.7,
            "top_p": 0.9,
            "num_ctx": 8192,
            "num_predict": 64,
        },
        "max_calls": (18 if smoke else 1152) * len(models),
        "max_seconds": (300 if smoke else 3600) * len(models),
        "timeout_seconds": 120,
        "max_attempts": 3,
        "analysis_windows": {
            "pre": [1, 1 if smoke else 10],
            "transition": [2, 2] if smoke else [11, 11],
            "post": [3, 3] if smoke else [12, 30],
        },
        "presentation_control": "Jointly reverse legal enum and own-action payoff row groups; opponent row order stays cooperate then defect.",
    }
    validate_config(config)
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("communication/configs"))
    parser.add_argument("--models", nargs="+", help="One or more model IDs on the selected backend")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for smoke in (False, True):
        config = configuration(smoke, models=args.models)
        path = args.out / ("semantic_smoke.json" if smoke else "semantic_main.json")
        text = json.dumps(config, indent=2) + "\n"
        if path.exists() and path.read_text() != text:
            raise ValueError(
                f"Refusing to overwrite changed frozen configuration: {path}"
            )
        path.write_text(text)
        print(path)


if __name__ == "__main__":
    main()
