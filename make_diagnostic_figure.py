"""Plot saved diagnostic choices by both independent presentation-order factors."""
import json
import os
from pathlib import Path


def main():
    out = Path(__file__).resolve().parent / "results" / "diagnostic"
    data = json.loads((out / "report.json").read_text())
    rows = {(r['model'], r['condition'], r['prompt_order'], r['schema_order']): r
            for r in data['summaries'] if r['group_by'] == 'model+condition+prompt_order+schema_order'}
    os.environ.setdefault('MPLCONFIGDIR', str(out / '.mplconfig'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    conditions = ['full_direct', 'relevant_direct', 'full_extract_choose']
    models = [('qwen3:4b', 'Qwen', '#117d83'), ('gemma3:4b', 'Gemma', '#c66a36')]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.3))
    for prompt in range(2):
        for schema in range(2):
            ax = axes[prompt, schema]
            for index, (model, label, color) in enumerate(models):
                for i, condition in enumerate(conditions):
                    row = rows[model, condition, prompt, schema]
                    y = i + (index-.5)*.34
                    value = 100*row['accuracy_planned']
                    ax.barh(y, value, height=.30, color=color, label=label if i == 0 else None)
                    ax.text(value+1.7, y, f"{row['correct']}/{row['planned']}", va='center', fontsize=9)
            ax.set(yticks=range(3), yticklabels=['Full information', 'Relevant rewards', 'Report + choose'],
                   xlim=(0, 120), xticks=[0, 50, 100], xlabel='Correct choices / planned requests',
                   title=f"Prompt: {'A → B' if prompt == 0 else 'B → A'}  |  Allowed answers: {'A → B' if schema == 0 else 'B → A'}")
            ax.invert_yaxis()
            ax.xaxis.set_major_formatter(PercentFormatter())
            ax.spines[['top', 'right']].set_visible(False)
            ax.set_axisbelow(True)
            ax.grid(axis='x', alpha=.15)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=2, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, .93), w_pad=2.5, h_pad=3)
    for extension in ('png', 'svg'):
        fig.savefig(out / f'accuracy.{extension}', dpi=160, facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    main()
