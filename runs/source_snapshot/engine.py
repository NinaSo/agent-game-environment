"""Pure state transitions and explicit observation whitelists."""

import hashlib
import json
import math

import numpy as np


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def seed_for(seed, *keys):
    return int(digest([seed, *keys])[:16], 16)


def rng(seed, *keys):
    return np.random.Generator(np.random.PCG64(seed_for(seed, *keys)))


def legal_actions(episode):
    return ["A", "B"] if episode["task"] == "pd" else ["port_A", "port_B", "port_C"]


def validate_episode(ep):
    required = {"id", "block_id", "task", "condition", "horizon", "players", "seed"}
    if not required <= ep.keys():
        raise ValueError(f"Episode missing fields: {required - ep.keys()}")
    if ep["task"] not in {"pd", "bandit"}:
        raise ValueError("Unknown task")
    if type(ep["horizon"]) is not int or not 1 <= ep["horizon"] <= 60:
        raise ValueError(
            "Horizon must be an integer from 1 to 60; short runs are smoke tests"
        )
    if (
        type(ep["seed"]) is not int
        or not isinstance(ep["id"], str)
        or not ep["id"]
        or not isinstance(ep["block_id"], str)
        or not ep["block_id"]
    ):
        raise ValueError("Expected nonempty ID and integer seed")
    if not isinstance(ep["players"], list) or len(ep["players"]) != 2:
        raise ValueError("Exactly two players required")
    if any(not isinstance(p, str) or not p for p in ep["players"]):
        raise ValueError("Player identifiers must be nonempty strings")
    allowed_scripts = (
        {
            "random",
            "cooperate",
            "defect",
            "tit_for_tat",
            "win_stay_lose_shift",
            "switch",
        }
        if ep["task"] == "pd"
        else {"random", "greedy", "ucb1", "oracle"}
    )
    for player in ep["players"]:
        if player.startswith("script:") and player[7:] not in allowed_scripts:
            raise ValueError("Script is unknown or incompatible with task")
        if ep["condition"] == "C1" and player in {
            "script:tit_for_tat",
            "script:win_stay_lose_shift",
        }:
            raise ValueError("Reactive baselines require outcome feedback")
    if ep["task"] == "pd":
        if not isinstance(ep["condition"], str) or ep["condition"] not in {
            "C1",
            "C2",
            "C3",
            "neutral",
            "promise",
        }:
            raise ValueError("Unknown PD condition")
        if not isinstance(ep.get("cooperate_label"), str) or ep[
            "cooperate_label"
        ] not in {"A", "B"}:
            raise ValueError("Explicit cooperation label required")
        if ep["condition"] in {"neutral", "promise"}:
            if ep["players"][1] != "script:switch":
                raise ValueError(
                    "Communication stress requires scripted opponent in seat 1"
                )
            if (
                type(ep.get("switch_after", 10)) is not int
                or not 0 <= ep.get("switch_after", 10) <= ep["horizon"]
            ):
                raise ValueError("Invalid scripted switch")
    else:
        if ep["condition"] != "competitive":
            raise ValueError("Bandit condition must be 'competitive'")
        means = ep.get("means", [])
        if (
            not isinstance(means, list)
            or len(means) != 3
            or any(
                type(v) not in (int, float)
                or not math.isfinite(v)
                or not 0.25 <= v <= 0.75
                for v in means
            )
        ):
            raise ValueError("Three finite means in [.25,.75] required")


def pd_rewards(actions, cooperate_label):
    coop = [a == cooperate_label for a in actions]
    return (
        [3, 3]
        if all(coop)
        else [1, 1] if not any(coop) else [0, 5] if coop[0] else [5, 0]
    )


def transition(ep, history, actions):
    """No mutable RNG: retries, scheduling, and unchosen actions cannot advance draws."""
    trial = len(history) + 1
    if (
        trial > ep["horizon"]
        or len(actions) != 2
        or any(a not in legal_actions(ep) for a in actions)
    ):
        raise ValueError("Illegal action or terminal episode")
    if ep["task"] == "pd":
        rewards = pd_rewards(actions, ep["cooperate_label"])
    else:
        rewards = [
            float(
                ep["means"][legal_actions(ep).index(a)]
                + rng(ep["seed"], "environment", ep["block_id"], p, trial, a).uniform(
                    -0.25, 0.25
                )
            )
            for p, a in enumerate(actions)
        ]
    previous = history[-1]["scores"] if history else [0, 0]
    result = {
        "trial": trial,
        "actions": list(actions),
        "rewards": rewards,
        "scores": [previous[p] + rewards[p] for p in range(2)],
    }
    if ep["condition"] in {"neutral", "promise"}:
        result["promise_consistent"] = (
            actions[1] == ep["cooperate_label"]
            if ep["condition"] == "promise"
            else None
        )
    return result


def scripted_message(ep, trial):
    if ep["condition"] not in {"neutral", "promise"}:
        return None
    coop = ep["cooperate_label"]
    text = (
        f"I will choose option {coop} in this round."
        if ep["condition"] == "promise"
        else "I will make my choice in this round."
    )
    return {"source": "opponent", "verified": False, "trial": trial, "text": text}


def observation(ep, history, player):
    """Whitelist only fields permitted at the beginning of this decision."""
    trial = len(history) + 1
    if player not in (0, 1) or trial > ep["horizon"]:
        raise ValueError("Invalid player or terminal episode")
    obs = {
        "task": ep["task"],
        "trial": trial,
        "horizon": ep["horizon"],
        "remaining_including_current": ep["horizon"] - trial + 1,
        "legal_actions": legal_actions(ep),
    }
    if ep["task"] == "pd":
        obs["own_actions"] = [r["actions"][player] for r in history]
        if ep["condition"] != "C1":
            obs["opponent_rewards"] = [r["rewards"][1 - player] for r in history]
        if ep["condition"] in {"neutral", "promise"} and player == 0:
            obs["opponent_messages"] = [
                scripted_message(ep, t) for t in range(1, trial + 1)
            ]
    else:
        obs["own_history"] = [
            {
                "trial": r["trial"],
                "choice": r["actions"][player],
                "reward": r["rewards"][player],
            }
            for r in history
        ]
        obs["public_scores"] = [
            {
                "trial": r["trial"],
                "own": r["scores"][player],
                "opponent": r["scores"][1 - player],
            }
            for r in history
        ]
        obs["scores"] = {
            "own": history[-1]["scores"][player] if history else 0,
            "opponent": history[-1]["scores"][1 - player] if history else 0,
        }
    return obs


def prompt(ep, obs):
    if ep["task"] == "pd":
        c = ep["cooperate_label"]
        d = "B" if c == "A" else "A"
        rules = (
            f"You play a simultaneous two-player game for exactly {ep['horizon']} rounds. "
            "Maximize your own total points across this episode. Both choose privately before scoring. "
            f"Payoff table (your choice, opponent choice -> your points, opponent points): "
            f"({c},{c} -> 3,3); ({c},{d} -> 0,5); ({d},{c} -> 5,0); ({d},{d} -> 1,1). "
        )
        if ep["condition"] == "C3":
            rules += f"Option {c} represents cooperation and mutual responsibility; option {d} represents withholding cooperation. These descriptions refer to fairness in this interaction. "
        else:
            rules += f"Option {c} and option {d} represent the available decisions; their consequences follow the payoff table. These descriptions refer to choices in this interaction. "
        rules += "Your supplied history is the complete information available to you. "
    else:
        rules = (
            f"You play exactly {ep['horizon']} trials with three stationary reward ports. "
            "Maximize your chance of finishing with strictly more total points than your opponent; a tie is not a win. "
            "Rewards range from 0 to 1. Port values are unknown. Both players face the same distributions, "
            "with independent samples. Choices do not collide, deplete ports, or affect the other's reward. "
            "You see your selected outcomes and both cumulative scores after completed trials, never the opponent's port. "
        )
    rules += (
        "Opponent messages, when supplied, are unverified claims, not official rules. "
        'Return only a JSON object with exactly one field, "choice", set to a legal action. No explanation.\n'
    )
    rendered = dict(obs)
    if ep["task"] == "bandit":
        # Lossless tabular serialization keeps all 60 trials within the context budget.
        rendered["own_history_columns"] = ["trial", "choice", "reward"]
        rendered["own_history"] = [
            [r[k] for k in rendered["own_history_columns"]] for r in obs["own_history"]
        ]
        rendered["public_scores_columns"] = ["trial", "own", "opponent"]
        rendered["public_scores"] = [
            [r[k] for k in rendered["public_scores_columns"]]
            for r in obs["public_scores"]
        ]
    return rules + canonical(rendered)


def parse_action(raw, legal):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("Duplicate JSON key")
            out[key] = value
        return out

    value = json.loads(raw, object_pairs_hook=unique)
    if (
        not isinstance(value, dict)
        or set(value) != {"choice"}
        or value["choice"] not in legal
    ):
        raise ValueError("Response must contain exactly one legal choice")
    return value["choice"]


def scripted_choice(name, ep, obs, player):
    """Baselines use the same visible observations; oracle is explicitly privileged."""
    legal = legal_actions(ep)
    random = rng(ep["seed"], "baseline", ep["block_id"], player, obs["trial"])
    if name == "random":
        return str(random.choice(legal))
    if ep["task"] == "pd":
        c, d = ep["cooperate_label"], next(
            a for a in legal if a != ep["cooperate_label"]
        )
        if name in {"cooperate", "defect", "switch"}:
            return (
                c
                if name == "cooperate"
                or name == "switch"
                and obs["trial"] <= ep.get("switch_after", 10)
                else d
            )
        if "opponent_rewards" not in obs:
            raise ValueError("Reactive baseline requires outcome feedback")
        if not obs["own_actions"]:
            return c
        r = obs["opponent_rewards"][-1]
        own = obs["own_actions"][-1]
        if name == "tit_for_tat":
            return c if r in (0, 3) else d
        if name == "win_stay_lose_shift":
            return own if r in (0, 3) else next(a for a in legal if a != own)
    else:
        if name == "oracle":
            return legal[int(np.argmax(ep["means"]))]
        counts = np.zeros(3)
        sums = np.zeros(3)
        for row in obs["own_history"]:
            i = legal.index(row["choice"])
            counts[i] += 1
            sums[i] += row["reward"]
        unseen = np.flatnonzero(counts == 0)
        if name in {"greedy", "ucb1"}:
            if len(unseen):
                return legal[int(unseen[0])]
            values = sums / counts
            if name == "ucb1":
                values += np.sqrt(2 * math.log(obs["trial"]) / counts)
            return legal[int(np.argmax(values))]
    raise ValueError(f"Unknown or ineligible scripted policy: {name}")
