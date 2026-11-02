"""Rebuild descriptive pilot results from read-only, replay-validated logs.

No fitting or psychological claims: section 10 recovery/held-out gates stay closed.
"""

import argparse
from contextlib import closing
from collections import defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np

from game_lab.engine import canonical, rng
from game_lab.runner import replay
from game_lab.store import connect, export_data


def ratio(n, d):
    return n / d if d else None


def csv_write(path, rows, fields=None):
    fields = fields or list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def json_write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def summarize(data, label):
    rounds = defaultdict(list)
    for r in data["rounds"]:
        rounds[r["episode_id"]].append(r["result"])
    summaries, metrics, features, targets, trajectories = [], [], [], [], []
    configs = {e["id"]: e["config"] for e in data["episodes"]}
    committed = {(e, r["trial"]): r for e, rs in rounds.items() for r in rs}
    for d in data["decisions"]:
        ep = configs[d["episode_id"]]
        base = dict(
            run=label,
            episode=d["episode_id"],
            block=ep["block_id"],
            model=ep["players"][d["player"]],
            player=d["player"],
            trial=d["trial"],
            condition=ep["condition"],
            task=ep["task"],
            observation_id=d["snapshot_hash"],
        )
        features.append(
            {
                **base,
                "observation_json": canonical(d["observation"]),
                "prompt_text": d["prompt"],
            }
        )
        result = committed.get((d["episode_id"], d["trial"]))
        targets.append(
            {
                **base,
                "action": d["action"],
                "reward": result["rewards"][d["player"]] if result else None,
                "committed": result is not None,
            }
        )
    for e in data["episodes"]:
        ep, history = e["config"], rounds[e["id"]]
        complete = e["status"] == "complete"
        for p, model in enumerate(ep["players"]):
            base = dict(
                run=label,
                episode=e["id"],
                block=ep["block_id"],
                model=model,
                player=p,
                task=ep["task"],
                condition=ep["condition"],
            )
            n = len(history)
            actions = [r["actions"][p] for r in history]
            rewards = [r["rewards"][p] for r in history]
            coops = (
                sum(a == ep.get("cooperate_label") for a in actions)
                if ep["task"] == "pd"
                else None
            )
            score = history[-1]["scores"][p] if history else 0
            opponent = history[-1]["scores"][1 - p] if history else 0
            regret = (
                sum(
                    max(ep["means"])
                    - ep["means"][["port_A", "port_B", "port_C"].index(a)]
                    for a in actions
                )
                if ep["task"] == "bandit"
                else None
            )
            repeats = sum(a == b for a, b in zip(actions[1:], actions[:-1]))
            summary = {
                **base,
                "cooperate_label": (
                    ep.get("cooperate_label") if ep["task"] == "pd" else None
                ),
                "literal_A_count": actions.count("A") if ep["task"] == "pd" else None,
                "status": e["status"],
                "error": e["error"],
                "planned_rounds": ep["horizon"],
                "completed_rounds": n,
                "score": score,
                "opponent_score": opponent,
                "score_gap": score - opponent,
                "win": int(score > opponent) if complete else None,
                "tie": int(score == opponent) if complete else None,
                "cooperation_count": coops,
                "cooperation_rate": ratio(coops, n) if coops is not None else None,
                "repeat_count": repeats,
                "repeat_denominator": max(n - 1, 0),
                "repeat_rate": ratio(repeats, max(n - 1, 0)),
                "expected_total_regret": regret,
                "mean_regret_per_pull": (
                    ratio(regret, n) if regret is not None else None
                ),
                "mean_reward": ratio(sum(rewards), n),
            }
            if ep["task"] == "pd":
                post = history[ep.get("switch_after", 10) :]
                summary["post_switch_cooperation"] = (
                    ratio(
                        sum(r["actions"][p] == ep["cooperate_label"] for r in post),
                        len(post),
                    )
                    if ep["condition"] in ("neutral", "promise")
                    else None
                )
                summary["post_switch_mean_reward"] = (
                    ratio(sum(r["rewards"][p] for r in post), len(post))
                    if ep["condition"] in ("neutral", "promise")
                    else None
                )
                summary["cooperation_lower_missing_bound"] = coops / ep["horizon"]
                summary["cooperation_upper_missing_bound"] = (
                    coops + ep["horizon"] - n
                ) / ep["horizon"]
            summaries.append(summary)
            if not complete:
                continue
            measures = [("repeat", repeats, max(n - 1, 0))]
            if ep["task"] == "pd":
                measures.append(("cooperation", coops, n))
                measures.append(
                    (
                        "mutual_cooperation",
                        sum(
                            all(a == ep["cooperate_label"] for a in r["actions"])
                            for r in history
                        ),
                        n,
                    )
                )
                measures.append(
                    (
                        "mutual_defection",
                        sum(
                            all(a != ep["cooperate_label"] for a in r["actions"])
                            for r in history
                        ),
                        n,
                    )
                )
                for third in range(3):
                    part = actions[third * n // 3 : (third + 1) * n // 3]
                    measures.append(
                        (
                            f"cooperation_third_{third+1}",
                            sum(a == ep["cooperate_label"] for a in part),
                            len(part),
                        )
                    )
                # C1 outcomes exist to the evaluator but are unavailable to the model.
                if ep["condition"] != "C1":
                    for state in ("CC", "CD", "DC", "DD"):
                        eligible = [
                            i
                            for i, r in enumerate(history[:-1])
                            if "".join(
                                "C" if r["actions"][j] == ep["cooperate_label"] else "D"
                                for j in (p, 1 - p)
                            )
                            == state
                        ]
                        measures.append(
                            (
                                "cooperate_after_" + state,
                                sum(
                                    actions[i + 1] == ep["cooperate_label"]
                                    for i in eligible
                                ),
                                len(eligible),
                            )
                        )
            else:
                ports = ["port_A", "port_B", "port_C"]
                best = {
                    port
                    for port, mean in zip(ports, ep["means"])
                    if mean == max(ep["means"])
                }
                measures.append(
                    ("highest_mean_port", sum(a in best for a in actions), n)
                )
                measures.extend(
                    ("selection_" + port, actions.count(port), n) for port in ports
                )
                # Rank is pre-decision and descriptive, not randomly assigned.
                for rank in ("ahead", "tied", "behind"):
                    indices = []
                    for i in range(1, n):
                        gap = (
                            history[i - 1]["scores"][p]
                            - history[i - 1]["scores"][1 - p]
                        )
                        observed = (
                            "ahead" if gap > 0 else "behind" if gap < 0 else "tied"
                        )
                        if observed == rank:
                            indices.append(i)
                    measures.append(
                        (
                            "switch_when_" + rank,
                            sum(actions[i] != actions[i - 1] for i in indices),
                            len(indices),
                        )
                    )
            for name, num, den in measures:
                metrics.append(
                    {
                        **base,
                        "metric": name,
                        "numerator": num,
                        "denominator": den,
                        "value": ratio(num, den),
                        "excluded_rounds": n - den,
                        "inference_status": "descriptive_completed_episode",
                    }
                )
            for r in history:
                trajectories.append(
                    {
                        **base,
                        "trial": r["trial"],
                        "score": r["scores"][p],
                        "reward": r["rewards"][p],
                        "choice": r["actions"][p],
                        "cooperate": (
                            int(r["actions"][p] == ep.get("cooperate_label"))
                            if ep["task"] == "pd"
                            else None
                        ),
                    }
                )
    return summaries, metrics, features, targets, trajectories


def contrasts(summaries):
    results, indices = [], {}
    models = sorted(
        {r["model"] for r in summaries if not r["model"].startswith("script:")}
    )
    comparisons = [
        ("C2", "C1", "cooperation_rate"),
        ("C3", "C2", "cooperation_rate"),
        ("promise", "neutral", "post_switch_cooperation"),
        ("promise", "neutral", "post_switch_mean_reward"),
    ]
    family_size = len(models) * 3
    for model in models:
        for treatment, control, measure in comparisons:
            byblock = defaultdict(dict)
            for row in summaries:
                if (
                    row["model"] == model
                    and row["status"] == "complete"
                    and row["condition"] in (treatment, control)
                    and not row["run"].startswith(("smoke", "baseline"))
                ):
                    byblock[(row["run"], row["block"])][row["condition"]] = row[measure]
            pairs = [
                (block, v[treatment] - v[control])
                for block, v in sorted(byblock.items())
                if set(v) == {treatment, control}
            ]
            primary = measure != "post_switch_mean_reward"
            key = model + ":" + treatment + "-" + control + ":" + measure
            values = np.array([v for _, v in pairs], dtype=float)
            low = high = None
            if len(values) >= 2:
                ix = rng(20261027, "bootstrap", key).integers(
                    0, len(values), (2000, len(values))
                )
                indices[key] = {
                    "blocks": [list(b) for b, _ in pairs],
                    "indices": ix.tolist(),
                }
                tail = 0.05 / (max(family_size, 1) if primary else 1) / 2
                low, high = np.quantile(
                    values[ix].mean(axis=1), [tail, 1 - tail]
                ).tolist()
            results.append(
                dict(
                    model=model,
                    contrast=treatment + " minus " + control,
                    metric=measure,
                    paired_blocks=len(values),
                    changed_pairs=int(np.count_nonzero(values)),
                    effect=float(values.mean()) if len(values) else None,
                    ci_low=low,
                    ci_high=high,
                    degenerate_bootstrap=bool(len(values) >= 2 and np.ptp(values) == 0),
                    bootstrap_replicates=2000,
                    primary=primary,
                    family_size=family_size if primary else 1,
                    nominal_coverage=1 - 0.05 / (max(family_size, 1) if primary else 1),
                    inference_status="pilot_descriptive_coverage_not_validated",
                )
            )
    return results, indices


def validity(data, label):
    rows = []
    groups = defaultdict(list)
    for e in data["episodes"]:
        for p, m in enumerate(e["config"]["players"]):
            groups[(e["config"]["task"], e["config"]["condition"], m)].append((e, p))
    for (task, condition, model), eps in sorted(groups.items()):
        keys = {(e["id"], p) for e, p in eps}
        attempts = [
            a for a in data["attempts"] if (a["episode_id"], a["player"]) in keys
        ]
        attempted = {(a["episode_id"], a["player"], a["trial"]) for a in attempts}
        invalid = {
            (a["episode_id"], a["player"], a["trial"])
            for a in attempts
            if a["status"] == "invalid"
        }
        valid = {
            (a["episode_id"], a["player"], a["trial"])
            for a in attempts
            if a["status"] == "valid"
        }
        rows.append(
            dict(
                run=label,
                task=task,
                condition=condition,
                model=model,
                planned_episodes=len(eps),
                completed_episodes=sum(e["status"] == "complete" for e, p in eps),
                invalid_episodes=sum(e["status"] == "invalid" for e, p in eps),
                incomplete_episodes=sum(e["status"] != "complete" for e, p in eps),
                attempted_decisions=len(attempted),
                valid_decisions=len(valid),
                invalid_decisions=len(invalid),
                invalid_decision_rate=ratio(len(invalid), len(attempted)),
                attempts=len(attempts),
                transport_errors=sum(
                    a["status"] == "transport_error" for a in attempts
                ),
                ambiguous_attempts=sum(a["status"] == "ambiguous" for a in attempts),
            )
        )
    return rows


def group_metrics(rows):
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["run"], r["task"], r["condition"], r["model"], r["metric"])].append(
            r
        )
    return [
        dict(
            zip(("run", "task", "condition", "model", "metric"), k),
            numerator=sum(r["numerator"] for r in rs),
            denominator=sum(r["denominator"] for r in rs),
            value=ratio(
                sum(r["numerator"] for r in rs), sum(r["denominator"] for r in rs)
            ),
            episodes=len(rs),
            eligible_episodes=sum(r["denominator"] > 0 for r in rs),
        )
        for k, rs in sorted(grouped.items())
    ]


def figures(out, summaries, trajectories, effects):
    os.environ.setdefault("MPLCONFIGDIR", str(out / ".mplconfig"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 160,
        }
    )
    models = sorted(
        {s["model"] for s in summaries if not s["model"].startswith("script:")}
    )
    colors = ["#117d83", "#c66a36"]
    chart_tables = {}
    fig, ax = plt.subplots(figsize=(7, 4))
    points = []
    for j, m in enumerate(models):
        for i, c in enumerate(("C1", "C2", "C3")):
            eligible = [
                s
                for s in summaries
                if s["model"] == m
                and s["condition"] == c
                and s["status"] == "complete"
                and s["run"].startswith("pilot_core")
            ]
            values = [s["cooperation_rate"] for s in eligible]
            if values:
                x = i + (j - 0.5) * 0.25
                ax.scatter(
                    [x] * len(values), values, color=colors[j % 2], alpha=0.35, s=22
                )
                ax.scatter(
                    [x],
                    [np.mean(values)],
                    color=colors[j % 2],
                    marker="_",
                    s=300,
                    label=m if i == 0 else None,
                )
                points.extend(
                    dict(
                        model=m,
                        condition=c,
                        episode=s["episode"],
                        cooperation=s["cooperation_rate"],
                        episodes=len(values),
                        mean=float(np.mean(values)),
                    )
                    for s in eligible
                )
    ax.set(
        xticks=range(3),
        xticklabels=["C1 · own choices", "C2 · outcome feedback", "C3 · moral framing"],
        ylabel="Cooperation fraction",
        ylim=(-0.04, 1.04),
        title="Prisoner’s Dilemma · one dot per episode",
    )
    if points:
        ax.legend()
    fig.tight_layout()
    fig.savefig(out / "pd_cooperation.png")
    fig.savefig(out / "pd_cooperation.svg")
    plt.close(fig)
    chart_tables["pd_cooperation"] = points
    fig, ax = plt.subplots(figsize=(7, 4))
    points = []
    for j, m in enumerate(models):
        for trial in range(1, 61):
            values = [
                t["score"]
                for t in trajectories
                if t["model"] == m
                and t["task"] == "bandit"
                and t["trial"] == trial
                and t["run"].startswith("pilot_core")
            ]
            if values:
                points.append(
                    dict(
                        model=m,
                        trial=trial,
                        mean_score=float(np.mean(values)),
                        episodes=len(values),
                    )
                )
        mine = [p for p in points if p["model"] == m]
        if mine:
            ax.plot(
                [p["trial"] for p in mine],
                [p["mean_score"] for p in mine],
                label=m,
                color=colors[j % 2],
            )
    ax.set(
        xlabel="Completed trial",
        ylabel="Mean cumulative score",
        title="Competitive bandit · mean across complete dyads",
    )
    if points:
        ax.legend()
    fig.tight_layout()
    fig.savefig(out / "bandit_scores.png")
    fig.savefig(out / "bandit_scores.svg")
    plt.close(fig)
    chart_tables["bandit_scores"] = points
    fig, ax = plt.subplots(figsize=(7, 4))
    points = []
    for j, m in enumerate(models):
        for c, style in [("neutral", "-"), ("promise", "--")]:
            mine = []
            for trial in range(1, 31):
                vals = [
                    t["cooperate"]
                    for t in trajectories
                    if t["model"] == m
                    and t["condition"] == c
                    and t["trial"] == trial
                    and t["run"].startswith("pilot_stress")
                ]
                if vals:
                    row = dict(
                        model=m,
                        condition=c,
                        trial=trial,
                        cooperation=float(np.mean(vals)),
                        episodes=len(vals),
                    )
                    points.append(row)
                    mine.append(row)
            if mine:
                ax.plot(
                    [p["trial"] for p in mine],
                    [p["cooperation"] for p in mine],
                    style,
                    label=m + " · " + c,
                    color=colors[j % 2],
                )
    ax.axvline(10.5, color="#777777", linestyle=":", label="Script starts defecting")
    ax.set(
        xlabel="Round",
        ylabel="Cooperation fraction",
        ylim=(-0.04, 1.04),
        title="Scripted communication · fixed opponent actions",
    )
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "scripted_messages.png")
    fig.savefig(out / "scripted_messages.svg")
    plt.close(fig)
    chart_tables["scripted_messages"] = points
    for name, rows in chart_tables.items():
        csv_write(out / (name + ".csv"), rows)


def label_figure(out, rows):
    """Display the existing label-check rates without recomputing any analysis."""
    if not rows:
        return
    os.environ.setdefault("MPLCONFIGDIR", str(out / ".mplconfig"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.ticker import PercentFormatter

    models = sorted({row["model"] for row in rows})
    conditions = ("C1", "C2", "C3")
    colors = {"A": "#117d83", "B": "#c66a36"}
    lookup = {
        (row["model"], row["condition"], row["cooperate_label"]): row
        for row in rows
    }
    fig, axes = plt.subplots(
        1, len(models), figsize=(10.5, 5.2), squeeze=False, sharex=True, sharey=True
    )
    for ax, model in zip(axes[0], models):
        for label, offset in (("A", -0.18), ("B", 0.18)):
            for i, condition in enumerate(conditions):
                row = lookup.get((model, condition, label))
                if row is None or row["cooperation_rate"] is None:
                    continue
                value = 100 * float(row["cooperation_rate"])
                y = i + offset
                ax.barh(y, value, height=0.3, color=colors[label], zorder=3)
                inside = value >= 90
                ax.text(
                    value - 2 if inside else value + 1.5,
                    y,
                    f"{value:.1f}%" if 0 < value < 100 else f"{value:.0f}%",
                    va="center",
                    ha="right" if inside else "left",
                    color="white" if inside else "#17323d",
                    fontsize=11,
                    fontweight="bold",
                )
        ax.set(
            xlim=(0, 105),
            ylim=(2.6, -0.6),
            xticks=[0, 25, 50, 75, 100],
            yticks=range(3),
            yticklabels=[
                "Own choices only\nC1",
                "Opponent rewards visible\nC2",
                "Same feedback + moral wording\nC3",
            ],
            xlabel="Cooperative choices",
            title=model.replace("gemma3", "Gemma 3").replace("qwen3", "Qwen 3"),
        )
        ax.xaxis.set_major_formatter(PercentFormatter())
        ax.grid(axis="x", color="#dce3de", linewidth=0.8, zorder=0)
        ax.tick_params(axis="y", length=0, labelsize=10)
        for spine in ax.spines.values():
            spine.set_visible(False)
    fig.suptitle("Same payoffs, swapped action labels", x=0.03, ha="left", fontsize=17)
    fig.legend(
        handles=[
            Patch(color=colors["A"], label="A means cooperate; B means defect"),
            Patch(color=colors["B"], label="B means cooperate; A means defect"),
        ],
        loc="upper left",
        bbox_to_anchor=(0.025, 0.92),
        frameon=False,
        ncol=2,
        fontsize=10,
    )
    qwen = [row for row in rows if row["model"] == "qwen3:4b"]
    if qwen:
        total = sum(int(row["decisions"]) for row in qwen)
        literal_b = total - sum(int(row["literal_A_count"]) for row in qwen)
        fig.text(
            0.03, 0.085,
            f"Qwen chose the letter B in {literal_b:,} of {total:,} decisions, whichever action B represented.",
            fontsize=10, color="#17323d",
        )
    fig.text(
        0.03, 0.035,
        "Exploratory check after inspecting outcomes; this pattern does not establish a causal mechanism.",
        fontsize=9, color="#61737a",
    )
    fig.subplots_adjust(left=0.26, right=0.98, top=0.76, bottom=0.22, wspace=0.14)
    fig.savefig(out / "pd_label_sensitivity.png", dpi=180)
    fig.savefig(out / "pd_label_sensitivity.svg")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("databases", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, default=Path("results"))
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    if len({p.stem for p in args.databases}) != len(args.databases):
        parser.error(
            "Database stems must be unique; duplicate run labels are not allowed."
        )
    summaries = []
    metrics = []
    features = []
    targets = []
    trajectories = []
    runs = []
    traces = {}
    for path in args.databases:
        with closing(connect(path.resolve(), readonly=True)) as db:
            db.execute(
                "BEGIN"
            )  # Consistent read snapshot, independent of a live writer.
            verification = replay(db)
            if path.stem.startswith("baseline"):
                # Baseline prompts remain in SQLite; avoid duplicating 48k long histories in RAM.
                from game_lab.store import manifest

                data = {
                    "manifest": manifest(db),
                    "decisions": [],
                    "episodes": [
                        {**dict(r), "config": json.loads(r["config"])}
                        for r in db.execute("SELECT * FROM episodes ORDER BY id")
                    ],
                    "rounds": [
                        {**dict(r), "result": json.loads(r["result"])}
                        for r in db.execute(
                            "SELECT * FROM rounds ORDER BY episode_id,trial"
                        )
                    ],
                    "attempts": [
                        dict(r)
                        for r in db.execute(
                            "SELECT episode_id,player,trial,attempt,status,error FROM attempts ORDER BY episode_id,player,trial,attempt"
                        )
                    ],
                    "export_scope": "All baseline outcomes and attempt metadata. Exact baseline prompts and raw responses remain in runs/baselines.sqlite.",
                }
            else:
                data = export_data(db)
        label = path.stem
        traces[label] = data
        parts = summarize(data, label)
        for dest, source in zip(
            (summaries, metrics, features, targets, trajectories), parts
        ):
            dest.extend(source)
        attempts = data["attempts"]
        counts = {
            s: sum(e["status"] == s for e in data["episodes"])
            for s in ("pending", "running", "complete", "invalid", "incomplete")
        }
        runs.append(
            dict(
                name=label,
                episodes=len(data["episodes"]),
                counts=counts,
                rounds=len(data["rounds"]),
                attempts=len(attempts),
                attempt_status={
                    s: sum(a["status"] == s for a in attempts)
                    for s in sorted({a["status"] for a in attempts})
                },
                elapsed_seconds=data["manifest"]["elapsed_seconds"],
                verification=verification,
                manifest=data["manifest"],
            )
        )
        json_write(out / (label + "_trace.json"), data)
    effects, indices = contrasts(summaries)
    aggregates = group_metrics(metrics)
    validity_rows = [r for name, data in traces.items() for r in validity(data, name)]
    csv_write(out / "validity.csv", validity_rows)
    label_groups = defaultdict(list)
    for row in summaries:
        if (
            row["run"].startswith("pilot_core")
            and row["task"] == "pd"
            and row["status"] == "complete"
        ):
            label_groups[
                (row["model"], row["condition"], row["cooperate_label"])
            ].append(row)
    label_diagnostics = [
        dict(
            model=k[0],
            condition=k[1],
            cooperate_label=k[2],
            episodes=len(rs),
            literal_A_count=sum(r["literal_A_count"] for r in rs),
            decisions=sum(r["completed_rounds"] for r in rs),
            cooperation_rate=float(np.mean([r["cooperation_rate"] for r in rs])),
            analysis_status="post_hoc_descriptive_label_check",
        )
        for k, rs in sorted(label_groups.items())
    ]
    csv_write(out / "label_diagnostics.csv", label_diagnostics)
    for name, rows in [
        ("episode_summary", summaries),
        ("behavioral_metrics", metrics),
        ("aggregate_metrics", aggregates),
        ("decision_features", features),
        ("decision_targets", targets),
        ("trajectories", trajectories),
        ("condition_contrasts", effects),
    ]:
        csv_write(out / (name + ".csv"), rows)
    json_write(out / "bootstrap_indices.json", indices)
    gates = {
        name: {"status": "not_run", "reason": reason}
        for name, reason in {
            "candidate_policy_fitting": "Pilot does not meet recovery and independent held-out validation gates. No fitted parameter or family claims.",
            "model_and_parameter_recovery": "Section 10 requires a frozen simulation bank and at least 200 datasets per setting; these have not been executed.",
            "controlled_probes": "Diagnostic snapshot continuations require a separate frozen budget and manifest.",
            "main_study": "Pilot precision and runtime must inform a new preregistered independent collection.",
            "coverage_validation": "Bootstrap percentile intervals are descriptive; small pilot coverage and extreme-tail stability have not been validated.",
        }.items()
    }
    json_write(out / "analysis_gates.json", gates)
    # Schema-valid status records explicitly prevent absent stages looking like results.
    for name in ("policy_fits", "recovery_confusion", "parameter_recovery"):
        csv_write(
            out / (name + ".csv"),
            [
                {
                    "status": "not_run",
                    "reason": gates[
                        (
                            "candidate_policy_fitting"
                            if name == "policy_fits"
                            else "model_and_parameter_recovery"
                        )
                    ]["reason"],
                }
            ],
        )
    for name in ("probe_manifest", "split_manifest"):
        json_write(
            out / (name + ".json"),
            {
                "status": "not_created",
                "reason": "No probes or held-out model fitting in this mechanics pilot.",
            },
        )
    figures(out, summaries, trajectories, effects)
    label_figure(out, label_diagnostics)
    inspection = []
    for name, data in traces.items():
        if name.startswith("baseline"):
            continue
        ep_configs = {e["id"]: e["config"] for e in data["episodes"]}
        raw = {
            (a["episode_id"], a["player"], a["trial"]): a["raw"]
            for a in data["attempts"]
            if a["status"] == "valid"
        }
        for d in data["decisions"]:
            ep = ep_configs[d["episode_id"]]
            if d["trial"] in (1, ep["horizon"] // 2, ep["horizon"]):
                inspection.append(
                    dict(
                        run=name,
                        episode=d["episode_id"],
                        player=d["player"],
                        trial=d["trial"],
                        model=ep["players"][d["player"]],
                        observation=d["observation"],
                        prompt=d["prompt"],
                        action=d["action"],
                        raw=raw.get((d["episode_id"], d["player"], d["trial"])),
                        snapshot_hash=d["snapshot_hash"],
                    )
                )
    dataset = {
        "runs": runs,
        "episodes": summaries,
        "metrics": aggregates,
        "contrasts": effects,
        "gates": gates,
        "inspection": inspection,
        "validity": validity_rows,
        "label_diagnostics": label_diagnostics,
    }
    json_write(out / "dashboard_data.json", dataset)
    # External JS makes the dashboard portable under file:// without a web server.
    (out / "dashboard_data.js").write_text(
        "window.LAB_DATA = " + json.dumps(dataset, allow_nan=False) + ";\n"
    )
    hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out.glob("*.csv"))
    }
    json_write(
        out / "analysis_manifest.json",
        dict(
            version=1,
            source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            numpy=np.__version__,
            seed=20261027,
            bootstrap=2000,
            primary_contrast_family=sum(e["primary"] for e in effects),
            tables_sha256=hashes,
            claim_scope="descriptive pilot; no policy or parameter inference",
        ),
    )
    print(
        json.dumps(
            {
                "output": str(out.resolve()),
                "runs": [{k: r[k] for k in ("name", "counts", "rounds")} for r in runs],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
