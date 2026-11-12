"""Two panels from results/equity_families.csv, in the palette src/plots.py uses.

Left: how often the cost-minimising routing leaves a hospital with nothing,
against how deep the shortage is, one line per family.
Right: the worst-hospital fill rate the cost-minimising routing delivers next
to the best any routing of the same total could deliver, per family.

    python plot_equity_families.py
"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from src.plots import GRID, INK, MUTED, PAIR_COLOR, SECONDARY_INK, SINGLE_COLOR

EDGES = [0, 1, 1.5, 2, 3, 5, float("inf")]
LABELS = ["< 1", "1 to 1.5", "1.5 to 2", "2 to 3", "3 to 5", "5 or more"]
MIN_STATES = 8
EDGE = 1e-6   # a shortfall exactly on a bin edge belongs to the bin above it


def load(path="results/equity_families.csv"):
    with open(path) as f:
        rows = [r for r in csv.DictReader(f) if r["failures"] == "single"]
    for r in rows:
        for key in ("shortfall_over_smallest_demand", "equity", "fair_equity"):
            r[key] = float(r[key])
    return rows


def stranded_by_depth(rows):
    """Share of states stranded in each depth bin, None where the bin is thin."""
    out = []
    for low, high in zip(EDGES[:-1], EDGES[1:]):
        inside = [r for r in rows
                  if low - EDGE <= r["shortfall_over_smallest_demand"] < high - EDGE]
        out.append(None if len(inside) < MIN_STATES
                   else sum(1 for r in inside if r["equity"] <= 1e-6) / len(inside))
    return out


def main(out_path="results/equity_families.png"):
    rows = load()
    families = list(dict.fromkeys(r["family"] for r in rows))
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.8))

    xs = list(range(len(LABELS)))
    for family in families:
        shares = stranded_by_depth([r for r in rows if r["family"] == family])
        points = [(x, s) for x, s in zip(xs, shares) if s is not None]
        left.plot([p[0] for p in points], [p[1] for p in points], color=MUTED,
                  linewidth=1, alpha=0.8, zorder=2)
    pooled = stranded_by_depth(rows)
    left.plot(xs, pooled, color=SINGLE_COLOR, linewidth=2.4, marker="o", markersize=6,
              markeredgecolor="white", markeredgewidth=1.5, zorder=3,
              label="all nine families pooled")
    left.plot([], [], color=MUTED, linewidth=1, label="one family")
    left.set_xticks(xs)
    left.set_xticklabels(LABELS)
    left.yaxis.set_major_formatter(PercentFormatter(xmax=1))
    left.set_ylim(-0.03, 1.03)
    left.set_xlabel("shortfall, in multiples of the smallest hospital's demand",
                    color=SECONDARY_INK)
    left.set_ylabel("states with a hospital left at zero", color=SECONDARY_INK)
    left.set_title("Stranding follows the depth of the shortage", color=INK, loc="left")
    left.legend(frameon=False, fontsize=9, loc="upper left")

    ys = list(range(len(families)))[::-1]
    for y, family in zip(ys, families):
        mine = [r for r in rows if r["family"] == family]
        got = sum(r["equity"] for r in mine) / len(mine)
        fair = sum(r["fair_equity"] for r in mine) / len(mine)
        right.plot([got, fair], [y, y], color=MUTED, linewidth=1.5, zorder=2)
        right.scatter([got], [y], s=48, color=SINGLE_COLOR, edgecolor="white",
                      linewidth=1.2, zorder=3)
        right.scatter([fair], [y], s=48, color=PAIR_COLOR, edgecolor="white",
                      linewidth=1.2, zorder=3)
    right.scatter([], [], s=48, color=SINGLE_COLOR, label="cost-minimising routing")
    right.scatter([], [], s=48, color=PAIR_COLOR, label="best routing of the same total")
    right.set_yticks(ys)
    right.set_yticklabels(families)
    right.xaxis.set_major_formatter(PercentFormatter(xmax=1))
    right.set_xlim(0, 1)
    right.set_xlabel("mean fill rate of the worst-served hospital", color=SECONDARY_INK)
    right.set_title("What routing by cost leaves on the table", color=INK, loc="left")
    right.legend(frameon=False, fontsize=9, loc="upper center",
                 bbox_to_anchor=(0.5, -0.16), ncol=2)

    for axis in (left, right):
        axis.grid(color=GRID, linewidth=0.8)
        axis.set_axisbelow(True)
        for spine in ("top", "right"):
            axis.spines[spine].set_visible(False)
        axis.tick_params(colors=SECONDARY_INK)

    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    print(f"wrote {out_path}  ({len(rows)} single-failure shortage states, "
          f"{len(families)} families)")


if __name__ == "__main__":
    main()
