"""Plot the saved follow-up accuracy counts; never call models or modify logs."""

import json
import os
from pathlib import Path


def main():
    out = Path(__file__).resolve().parent / "results" / "followups"
    data = json.loads((out / "report.json").read_text())
    if data["phase"] != "followup":
        raise ValueError("Expected the main follow-up report, not smoke data")
    os.environ.setdefault("MPLCONFIGDIR", str(out / ".mplconfig"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    rows = {(r["study"], r["model"]): r for r in data["summaries"] if r["group_by"] == "study+model"}
    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=160)
    studies = ["known_reward", "fixed_opponent_pd"]
    for j, (model, color) in enumerate([("gemma3:4b", "#117d83"), ("qwen3:4b", "#c66a36")]):
        for i, study in enumerate(studies):
            r = rows[(study, model)]
            value = 100 * r["correct"] / r["planned"]
            x = i + (j - .5) * .32
            ax.bar(x, value, width=.30, color=color, label=model if i == 0 else None)
            ax.text(x, value + 2, f"{value:.2f}%\n{r['correct']}/{r['planned']}", ha="center", fontsize=10)
    ax.set(xticks=[0, 1], xticklabels=["Known reward\n120 responses per model", "Fixed-opponent payoff table\n80 responses per model"],
           ylabel="Correct choices / planned responses", ylim=(0, 119), title="Follow-up studies: choosing the higher payoff")
    ax.yaxis.set_major_formatter(PercentFormatter())
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.20), ncol=2, frameon=False)
    fig.text(.5, .025, "20 question texts × 2 answer-format orders × 5 seeds × 2 models. Fresh context for every response.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .12, 1, 1))
    for extension in ("png", "svg"):
        fig.savefig(out / ("accuracy." + extension))
    plt.close(fig)


if __name__ == "__main__":
    main()
