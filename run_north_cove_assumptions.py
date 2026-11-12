"""Which North Cove conclusions depend on the numbers we assumed?

The documented instance of src/north_cove.py takes the plant shares from
published sources and assumes the rest: the split of volume across the four
channels, how much more than its normal volume a channel can move, and a
shipping cost of one on every arc. This draws those three assumptions at
random and re-runs the analysis on each draw.

  channel shares   each of the four multiplied by its own draw from [0.5, 1.5],
                   then rescaled to sum to 100
  headroom         one draw from [1.0, 2.0] for all four channels
  shipping costs   each arc multiplied by its own draw from [0.5, 1.5]

The plant shares (60, 23, 17) are documented and are not varied.

    python run_north_cove_assumptions.py [draws] [workers]
"""

import csv
import random
import statistics
import sys
from multiprocessing import Pool
from pathlib import Path

from run_north_cove import uniform_level_for
from src.experiment import fail_nodes, protection_spend
from src.fairness import fair_equity, fair_shipping_cost, generic_costs
from src.model import solve
from src.north_cove import CHANNELS, north_cove_network
from src.robust import min_spend_plan

DRAWS = 500
SEED = 2026
TARGETS = [0.6, 0.8, 1.0]
SHARE_BAND = 0.5
COST_BAND = 0.5
HEADROOM = (1.0, 2.0)


def draw_network(rng):
    scaled = {c: share * rng.uniform(1 - SHARE_BAND, 1 + SHARE_BAND)
              for c, share in CHANNELS.items()}
    total = sum(scaled.values())
    channels = {c: 100.0 * share / total for c, share in scaled.items()}
    headroom = rng.uniform(*HEADROOM)
    net = generic_costs(north_cove_network(channels=channels, headroom=headroom),
                        rng, band=COST_BAND)
    return net, channels, headroom


def _draw(index):
    net, channels, headroom = draw_network(random.Random(1000 * SEED + index))
    plants = [(p,) for p in net["suppliers"]]
    state = fail_nodes(net, ["NorthCove"])
    result = solve(state)
    fair = fair_equity(state)
    fair_ship = fair_shipping_cost(state, fair - 1e-7)
    row = {"draw": index, "headroom": headroom,
           "smallest_pool": min(channels.values()), "largest_pool": max(channels.values()),
           "satisfaction": result["satisfaction"], "equity": result["min_fill_rate"],
           "fair_equity": fair,
           "pools_unserved": sum(1 for h in net["hospitals"]
                                 if result["unmet"][h] >= net["demand"][h] - 1e-6),
           "shipping_premium": (fair_ship - result["shipping_cost"]) / result["shipping_cost"]}
    for target in TARGETS:
        tag = "t%d" % round(100 * target)
        optimal = min_spend_plan(net, plants, target)["spend"]
        per_pool = min_spend_plan(net, plants, target, per_hospital=True)["spend"]
        level = uniform_level_for(net, plants, target)
        row[tag + "_optimal"] = optimal
        row[tag + "_per_pool"] = per_pool
        row[tag + "_uniform"] = None if level is None else protection_spend(net, level)
    return row


def main(draws=DRAWS, workers=6, out_dir="results"):
    with Pool(workers) as pool:
        rows = pool.map(_draw, range(draws))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "north_cove_assumptions.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    n = len(rows)
    print("  %d draws of channel shares, headroom and shipping costs" % n)
    print("  satisfaction after North Cove fails: %.3f to %.3f"
          % (min(r["satisfaction"] for r in rows), max(r["satisfaction"] for r in rows)))
    stranded = [r for r in rows if r["equity"] <= 1e-6]
    print("  cost-minimising routing leaves a pool with nothing: %d of %d (%.1f%%); "
          "pools left with nothing: %s"
          % (len(stranded), n, 100.0 * len(stranded) / n,
             {k: sum(1 for r in rows if r["pools_unserved"] == k) for k in range(5)}))
    print("  fair equity equals satisfaction (every pool can get the same share): %d of %d"
          % (sum(1 for r in rows if abs(r["fair_equity"] - r["satisfaction"]) < 1e-5), n))
    premium = sorted(r["shipping_premium"] for r in rows)
    print("  shipping premium of the equal routing: median %.1f%%, 90th percentile %.1f%%, max %.1f%%"
          % (100 * statistics.median(premium), 100 * premium[int(0.9 * n)], 100 * premium[-1]))
    for target in TARGETS:
        tag = "t%d" % round(100 * target)
        ok = [r for r in rows if r[tag + "_optimal"] is not None and r[tag + "_per_pool"] is not None]
        free = sum(1 for r in ok if r[tag + "_per_pool"] - r[tag + "_optimal"] < 1e-4)
        lost = sum(1 for r in ok if abs(r[tag + "_optimal"] - (100 * target - 40)) < 1e-3)
        ratio = [r[tag + "_uniform"] / r[tag + "_optimal"] for r in ok
                 if r[tag + "_uniform"] is not None]
        extra = [r[tag + "_per_pool"] - r[tag + "_optimal"] for r in ok]
        print("  target %3.0f%%: feasible %d; optimal spend equals the capacity lost in %d; "
              "per-pool guarantee free in %d (largest premium %.2f); "
              "uniform costs %.1f to %.1f times the optimum (median %.1f)"
              % (100 * target, len(ok), lost, free, max(extra),
                 min(ratio), max(ratio), statistics.median(ratio)))
    print("outputs written to %s/north_cove_assumptions.csv" % out)


if __name__ == "__main__":
    args = sys.argv[1:]
    main(int(args[0]) if args else DRAWS, int(args[1]) if len(args) > 1 else 6)
