"""Generate the preregistered pilot and separate engineering/baseline batches."""

import argparse
import itertools
import json
from pathlib import Path

from game_lab.engine import rng
from game_lab.models import DEFAULT_MODELS, select_models

MODELS = list(DEFAULT_MODELS)


def episode(i, task, condition, players, block, horizon=None, label="A", means=None):
    e = dict(
        id=i,
        block_id=block,
        task=task,
        condition=condition,
        horizon=horizon or (30 if task == "pd" else 60),
        players=players,
        seed=20261027,
        cooperate_label=label,
    )
    if task == "bandit":
        e["means"] = means or [0.3, 0.5, 0.7]
    if condition in ("neutral", "promise"):
        e["switch_after"] = 10
    return e


def batches(models=None):
    models = select_models(models, pair=True)
    core, stress, baseline = [], [], []
    permutations = list(itertools.permutations([0.3, 0.5, 0.7]))
    for i in range(12):
        players = models[:: 1 if i % 2 == 0 else -1]
        label = "AB"[(i // 2) % 2]
        block = f"pd-{i:02d}"
        for condition in ("C1", "C2", "C3"):
            core.append(
                episode(
                    f"{block}-{condition}", "pd", condition, players, block, label=label
                )
            )
        core.append(
            episode(
                f"bandit-{i:02d}",
                "bandit",
                "competitive",
                players,
                f"bandit-{i:02d}",
                means=list(permutations[i // 2]),
            )
        )
    for m, model in enumerate(dict.fromkeys(models)):
        for i in range(4):
            block = f"stress-{m}-{i}"
            for condition in ("neutral", "promise"):
                stress.append(
                    episode(
                        f"{block}-{condition}",
                        "pd",
                        condition,
                        [model, "script:switch"],
                        block,
                        label="AB"[i % 2],
                    )
                )
    for i, strategy in enumerate(
        ["cooperate", "defect", "tit_for_tat", "win_stay_lose_shift", "random"]
    ):
        baseline.append(
            episode(
                f"baseline-pd-{i}",
                "pd",
                "C2",
                ["script:" + strategy, "script:switch"],
                f"baseline-pd-{i}",
            )
        )
    for i in range(100):
        for name in ["random", "greedy", "ucb1", "oracle"]:
            block = f"baseline-bandit-{i:03d}"
            baseline.append(
                episode(
                    f"{block}-{name}",
                    "bandit",
                    "competitive",
                    ["script:" + name, "script:random"],
                    block,
                )
            )
    smoke = [
        episode("smoke-" + t, t, c, models, "smoke-" + t, horizon=3)
        for t, c in [("pd", "C2"), ("bandit", "competitive")]
    ]
    return {
        "smoke": smoke,
        "pilot_core": core,
        "pilot_stress": stress,
        "baselines": baseline,
    }


def configurations(models=None):
    """Return complete configs for CLI generation and the multi-study suite."""
    configs = {}
    for name, episodes in batches(models).items():
        # Randomized execution IDs preserve matched block IDs and counterbalancing.
        order = rng(20261027, "assignment", name).permutation(len(episodes))
        episodes = [
            {**episodes[int(j)], "id": f"{i:04d}-" + episodes[int(j)]["id"]}
            for i, j in enumerate(order)
        ]
        expected = sum(e["horizon"] * 2 for e in episodes)
        configs[name] = dict(
            run_id=name + "_20261027_v1",
            seed=20261027,
            episodes=episodes,
            inference=dict(temperature=0.7, top_p=0.9, num_ctx=8192, num_predict=64),
            max_calls=expected + max(20, expected // 10),
            max_seconds=21600,
            max_attempts=3,
            timeout_seconds=120,
        )
    return configs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs=2, metavar=("PLAYER_1", "PLAYER_2"))
    parser.add_argument("--out", type=Path, default=Path("configs"))
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    for name, config in configurations(args.models).items():
        path = out / (name + ".json")
        text = json.dumps(config, indent=2) + "\n"
        if path.exists() and path.read_text() != text:
            raise ValueError(f"Refusing to overwrite a different frozen configuration: {path}")
        path.write_text(text)
        print(name, len(config["episodes"]), "episodes;",
              sum(e["horizon"] * 2 for e in config["episodes"]), "agent decisions")


if __name__ == "__main__":
    main()
