"""Two panels from results/generalization.csv, in the palette src/plots.py uses.

Left: what each policy charges for the same guarantee, one point per instance.
Right: where the topological ceiling sits on the instances that have one.

    python plot_generalization.py
"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from src.plots import GRID, INK, MUTED, PAIR_COLOR, SECONDARY_INK, SINGLE_COLOR

BENCHMARK_UNIFORM = 308.1
BENCHMARK_OPTIMIZED = 170.0
BENCHMARK_FLOOR = 1 - 110 / 180


def load(path="results/generalization.csv"):
    with open(path) as f:
        return list(csv.DictReader(f))


def load_dominance(path="results/dominance.csv"):
    """The fixed-target comparison, which sets the guarantee first and asks
    what each policy charges for it."""
    with open(path) as f:
        return list(csv.DictReader(f))


def main(out_path="results/generalization.png"):
    rows = load()
    dom = [r for r in load_dominance() if r["t100_uniform"] and r["t100_optimized"]]
    uniform = [float(r["t100_uniform"]) for r in dom]
    optimized = [float(r["t100_optimized"]) for r in dom]
    floors = [float(r["floor_value"]) for r in rows if r["has_floor"] == "True"]

    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.6))

    top = max(uniform + [BENCHMARK_UNIFORM]) * 1.06
    left.plot([0, top], [0, top], color=MUTED, linewidth=1, zorder=1)
    left.text(top * 0.72, top * 0.75, "equal cost", color=MUTED, fontsize=9, rotation=38)
    left.scatter(uniform, optimized, s=26, color=SINGLE_COLOR, alpha=0.75,
                 edgecolor="none", zorder=3, label="generated instance")
    left.scatter([BENCHMARK_UNIFORM], [BENCHMARK_OPTIMIZED], s=90, marker="D",
                 color=PAIR_COLOR, edgecolor="white", linewidth=1.2, zorder=4,
                 label="benchmark instance")
    left.set_xlim(0, top)
    left.set_ylim(0, top)
    left.set_xlabel("uniform spend to guarantee full delivery", color=SECONDARY_INK)
    left.set_ylabel("optimized spend for the same target", color=SECONDARY_INK)
    left.set_title("Every instance sits below the line", color=INK, loc="left")
    left.legend(frameon=False, fontsize=9, loc="upper left")

    right.hist(floors, bins=12, color=SINGLE_COLOR, alpha=0.8, edgecolor="white")
    right.axvline(BENCHMARK_FLOOR, color=PAIR_COLOR, linewidth=2)
    right.text(BENCHMARK_FLOOR + 0.012, right.get_ylim()[1] * 0.88,
               "benchmark\n38.9%", color=PAIR_COLOR, fontsize=9)
    right.xaxis.set_major_formatter(PercentFormatter(xmax=1))
    right.set_xlabel("ceiling on worst-case satisfaction", color=SECONDARY_INK)
    right.set_ylabel("instances", color=SECONDARY_INK)
    right.set_title(f"Where the ceiling sits, on the {len(floors)} instances "
                    f"that have one", color=INK, loc="left")

    for axis in (left, right):
        axis.grid(color=GRID, linewidth=0.8)
        axis.set_axisbelow(True)
        for spine in ("top", "right"):
            axis.spines[spine].set_visible(False)
        axis.tick_params(colors=SECONDARY_INK)

    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    print(f"wrote {out_path}  ({len(uniform)} instances, {len(floors)} with a ceiling)")


if __name__ == "__main__":
    main()
