"""Create compact dashboard figures from saved results; never call a model."""

import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results" / "dashboard"
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/agent_game_lab_dashboard_mpl")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import PercentFormatter

MODELS = ("gemma3:4b", "qwen3:4b")
NAMES = {"gemma3:4b": "Gemma 3 4B", "qwen3:4b": "Qwen 3 4B"}
COLORS = {"gemma3:4b": "#117d83", "qwen3:4b": "#c66a36"}


def read_csv(name):
    with (ROOT / "results" / name).open() as handle:
        return list(csv.DictReader(handle))


def percent(value):
    return f"{100 * value:.2f}".rstrip("0").rstrip(".") + "%"


def save(fig, name, rows):
    fig.savefig(OUT / f"{name}.png", dpi=160, facecolor="white")
    fig.savefig(OUT / f"{name}.svg", facecolor="white")
    plt.close(fig)
    with (OUT / f"{name}.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def rate_row(model, group, numerator, denominator):
    return dict(
        model=model,
        group=group,
        numerator=numerator,
        denominator=denominator,
        fraction=numerator / denominator,
    )


def grouped_rates(name, title, subtitle, groups, rows):
    """One color per model, direct labels, and visible markers for zero bars."""
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    for row in rows:
        offset = -0.18 if row["model"] == MODELS[0] else 0.18
        y = list(groups).index(row["group"]) + offset
        value = row["fraction"]
        ax.barh(y, value, height=0.3, color=COLORS[row["model"]], zorder=3)
        if value == 0:
            ax.plot(
                0,
                y,
                marker="|",
                markersize=14,
                markeredgewidth=3,
                color=COLORS[row["model"]],
                clip_on=False,
            )
        inside = value > 0.73
        ax.text(
            value - 0.02 if inside else value + 0.016,
            y,
            f"{percent(value)}  ({row['numerator']}/{row['denominator']})",
            ha="right" if inside else "left",
            va="center",
            fontsize=11,
            fontweight="bold",
            color="white" if inside else "#17323d",
        )
    ax.set(
        xlim=(0, 1.03),
        ylim=(len(groups) - 0.45, -0.55),
        yticks=range(len(groups)),
        yticklabels=list(groups.values()),
        xticks=[0, 0.25, 0.5, 0.75, 1],
        xlabel=(
            "Cooperative choices" if name != "followup_accuracy" else "Correct choices"
        ),
    )
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.grid(axis="x", color="#e2e8e5", linewidth=0.8, zorder=0)
    ax.tick_params(axis="y", length=0, labelsize=11)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.text(0.035, 0.94, title, fontsize=17, fontweight="bold", color="#17323d")
    fig.text(0.035, 0.875, subtitle, fontsize=10.5, color="#61737a")
    fig.legend(
        handles=[Patch(color=COLORS[m], label=NAMES[m]) for m in MODELS],
        loc="upper left",
        bbox_to_anchor=(0.025, 0.835),
        ncol=2,
        frameon=False,
        fontsize=11,
    )
    fig.subplots_adjust(left=0.26, right=0.97, top=0.71, bottom=0.14)
    save(fig, name, rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
    episodes = [
        r
        for r in read_csv("episode_summary.csv")
        if r["status"] == "complete" and r["model"] in MODELS
    ]
    core = [r for r in episodes if r["run"] == "pilot_core"]
    pd = []
    for condition in ("C1", "C2", "C3"):
        for model in MODELS:
            group = [
                r for r in core if r["condition"] == condition and r["model"] == model
            ]
            pd.append(
                rate_row(
                    model,
                    condition,
                    sum(int(r["cooperation_count"]) for r in group),
                    sum(int(r["completed_rounds"]) for r in group),
                )
            )
    grouped_rates(
        "pd_cooperation",
        "Cooperation across three conditions",
        "12 games per model and condition · 30 rounds per game",
        {
            "C1": "C1 · Own choices",
            "C2": "C2 · Reward feedback",
            "C3": "C3 · Moral wording",
        },
        pd,
    )

    labels = []
    for letter in "AB":
        for model in MODELS:
            group = [
                r
                for r in core
                if r["task"] == "pd"
                and r["model"] == model
                and r["cooperate_label"] == letter
            ]
            labels.append(
                rate_row(
                    model,
                    letter,
                    sum(int(r["cooperation_count"]) for r in group),
                    sum(int(r["completed_rounds"]) for r in group),
                )
            )
    grouped_rates(
        "label_mapping",
        "What happens when the labels swap?",
        "Exploratory check · all three conditions pooled · 540 decisions per bar",
        {
            "A": "A means cooperate\nB means defect",
            "B": "B means cooperate\nA means defect",
        },
        labels,
    )

    wins = []
    for model in MODELS:
        group = [r for r in core if r["task"] == "bandit" and r["model"] == model]
        wins.append(
            rate_row(model, "wins", sum(int(r["win"]) for r in group), len(group))
        )
    assert sum(int(r["tie"]) for r in core if r["task"] == "bandit") == 0
    fig, ax = plt.subplots(figsize=(8.5, 3.5))
    for i, row in enumerate(wins):
        ax.barh(i, row["numerator"], height=0.42, color=COLORS[row["model"]], zorder=3)
        ax.text(
            row["numerator"] + 0.2,
            i,
            f"{row['numerator']} wins / {row['denominator']} games",
            va="center",
            fontsize=13,
            fontweight="bold",
            color="#17323d",
        )
    ax.set(
        xlim=(0, 12),
        ylim=(1.6, -0.6),
        yticks=[0, 1],
        yticklabels=[NAMES[m] for m in MODELS],
        xticks=[0, 3, 6, 9, 12],
        xlabel="Games won",
    )
    ax.grid(axis="x", color="#e2e8e5", linewidth=0.8, zorder=0)
    ax.tick_params(axis="y", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.text(
        0.035,
        0.92,
        "Bandit games ended 6–6",
        fontsize=17,
        fontweight="bold",
        color="#17323d",
    )
    fig.text(
        0.035,
        0.835,
        "12 games · 60 choices per model in each game · no ties",
        fontsize=10.5,
        color="#61737a",
    )
    fig.subplots_adjust(left=0.20, right=0.96, top=0.73, bottom=0.19)
    save(fig, "bandit_wins", wins)

    # Derive exact post-switch counts from logged committed actions, not rounded rates.
    stress_trace = json.loads(
        (ROOT / "results" / "pilot_stress_trace.json").read_text()
    )
    specs = {
        e["id"]: e["config"]
        for e in stress_trace["episodes"]
        if e["status"] == "complete"
    }
    stress = []
    for condition in ("neutral", "promise"):
        for model in MODELS:
            eligible = []
            for entry in stress_trace["rounds"]:
                ep = specs.get(entry["episode_id"])
                row = entry["result"]
                if (
                    ep
                    and ep["condition"] == condition
                    and ep["players"][0] == model
                    and 11 <= row["trial"] <= 30
                ):
                    eligible.append(row["actions"][0] == ep["cooperate_label"])
            stress.append(rate_row(model, condition, sum(eligible), len(eligible)))
    grouped_rates(
        "scripted_messages",
        "Cooperation after the opponent starts defecting",
        "Rounds 11–30 · 4 games per model and message condition",
        {"neutral": "Neutral messages", "promise": "Promises to cooperate"},
        stress,
    )

    followup = json.loads((ROOT / "results" / "followups" / "report.json").read_text())
    accuracy = [
        rate_row(r["model"], r["study"], r["correct"], r["planned"])
        for r in followup["summaries"]
        if r["group_by"] == "study+model"
    ]
    grouped_rates(
        "followup_accuracy",
        "Choosing the better payoff in one decision",
        "Known rewards: 120 questions per model · fixed-opponent game: 80",
        {
            "known_reward": "Known rewards\n10 points or 1 point",
            "fixed_opponent_pd": "Fixed-opponent game\nRead the payoff table",
        },
        accuracy,
    )
    print(
        json.dumps(
            {
                "out": str(OUT),
                "pd": pd,
                "labels": labels,
                "bandit": wins,
                "messages": stress,
                "followup": accuracy,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
