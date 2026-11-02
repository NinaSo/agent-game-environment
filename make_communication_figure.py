"""Plot saved communication results separately by order; no inference or log edits."""

import json
import os
from pathlib import Path


def main():
    out = Path(__file__).resolve().parent / "results" / "communication"
    report = json.loads((out / "report.json").read_text())
    rows = {(r["model"], r["order"], r["condition"], r["window"]): r for r in report["summary"]}
    os.environ.setdefault("MPLCONFIGDIR", str(out / ".mplconfig"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    orders = ["cooperate / defect", "defect / cooperate"]
    models = [("qwen3:4b", "Qwen"), ("gemma3:4b", "Gemma")]
    styles = {"neutral": ("#117d83", "o-"), "promise": ("#c66a36", "D--")}
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.8), sharey=True)
    for i, (model, name) in enumerate(models):
        for j, order in enumerate(orders):
            ax = axes[i, j]
            rates = {condition: [rows[model, order, condition, window]["rate"]
                                for window in ("before", "after_evidence")]
                     for condition in styles}
            for condition, (color, style) in styles.items():
                other = rates["promise" if condition == "neutral" else "neutral"]
                x = [-.025, .975] if condition == "neutral" else [.025, 1.025]
                ax.plot(x, rates[condition], style, color=color, label=condition.title(), lw=2, ms=6)
                for k, (xi, value) in enumerate(zip(x, rates[condition])):
                    above = value > other[k] or (value == other[k] and condition == "promise")
                    ax.annotate(f"{value:.1%}", (xi, value), xytext=(0, 11 if above else -19),
                                textcoords="offset points", ha="center", color=color, fontsize=10)
            ax.set(title=name, xticks=[0, 1], xticklabels=["Before\nRounds 1–10", "After\nRounds 12–30"],
                   xlim=(-.3, 1.3), ylim=(-.2, 1.22), yticks=[0, .5, 1])
            ax.yaxis.set_major_formatter(PercentFormatter(1))
            ax.grid(axis="y", alpha=.2)
            ax.spines[["top", "right"]].set_visible(False)
            if j == 0:
                ax.set_ylabel("Cooperation rate")
    fig.text(.29, .97, "Cooperate listed first", ha="center", fontsize=14, weight="bold")
    fig.text(.76, .97, "Defect listed first", ha="center", fontsize=14, weight="bold")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(.5, .94), ncol=2, frameon=False)
    fig.subplots_adjust(left=.09, right=.97, top=.84, bottom=.10, wspace=.17, hspace=.52)
    for extension in ("png", "svg"):
        fig.savefig(out / f"before_after_by_order.{extension}", dpi=160, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
