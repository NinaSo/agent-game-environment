"""Export the architecture diagram as standalone PNG/SVG, without inference."""

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path("results/.mplconfig").resolve()))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


def main():
    out = Path("results")
    out.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set(xlim=(0, 12), ylim=(0, 6))
    ax.axis("off")
    ink, teal, rust = "#17323d", "#117d83", "#c66a36"
    ax.text(
        0.3,
        5.65,
        "A decision through the environment",
        fontsize=22,
        color=ink,
        weight="bold",
    )
    ax.text(
        0.3,
        5.2,
        "The evaluator stores complete state. Each model receives only its permitted view.",
        fontsize=11,
        color="#61737a",
    )
    boxes = [
        (
            0.3,
            3.5,
            "Frozen configuration",
            "Rules · conditions · seeds\nModel versions · call limits",
        ),
        (3.2, 3.5, "Authoritative state", "Completed rounds\nScores · evaluator truth"),
        (
            6.1,
            3.5,
            "Observation filter",
            "C1 / C2 / C3 / bandit\nFresh permitted history",
        ),
        (9, 3.5, "Local model", "One private JSON choice\nNo tools or file access"),
        (9, 1.0, "Validate and journal", "Every attempt recorded\nOne accepted action"),
        (
            6.1,
            1.0,
            "Atomic round outcome",
            "Wait for both choices\nScore and commit together",
        ),
        (
            3.2,
            1.0,
            "Replay and analyze",
            "Verify snapshots and rewards\nEpisode-level metrics",
        ),
        (
            0.3,
            1.0,
            "Read-only report",
            "Dashboard · figures · tables\nNo new model calls",
        ),
    ]
    for x, y, title, body in boxes:
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                2.5,
                1.2,
                boxstyle="round,pad=.08",
                facecolor="#edf4ef",
                edgecolor=teal,
                linewidth=1.2,
            )
        )
        ax.text(
            x + 1.25,
            y + 0.9,
            title,
            ha="center",
            va="center",
            fontsize=10.3,
            color=ink,
            weight="bold",
        )
        ax.text(
            x + 1.25,
            y + 0.4,
            body,
            ha="center",
            va="center",
            fontsize=9,
            color="#455b65",
            linespacing=1.5,
        )
    for start, end in [
        ((2.9, 4.1), (3.1, 4.1)),
        ((5.8, 4.1), (6, 4.1)),
        ((8.7, 4.1), (8.9, 4.1)),
        ((10.25, 3.4), (10.25, 2.3)),
        ((8.9, 1.6), (8.7, 1.6)),
        ((6, 1.6), (5.8, 1.6)),
        ((3.1, 1.6), (2.9, 1.6)),
    ]:
        ax.add_patch(
            FancyArrowPatch(
                start,
                end,
                arrowstyle="-|>",
                mutation_scale=14,
                color=teal,
                linewidth=1.5,
            )
        )
    ax.annotate(
        "Next round uses the newly committed history",
        xy=(4.45, 3.4),
        xytext=(4.45, 2.8),
        ha="center",
        fontsize=9,
        color=rust,
        arrowprops={"arrowstyle": "->", "color": rust},
    )
    ax.text(
        0.3,
        0.35,
        "Safety boundary: hidden means, future rewards and the opponent’s current choice never enter the observation filter output.",
        fontsize=10,
        color=rust,
    )
    fig.tight_layout()
    fig.savefig(out / "pipeline.png", dpi=180)
    fig.savefig(out / "pipeline.svg")
    plt.close(fig)


if __name__ == "__main__":
    main()
