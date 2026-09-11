"""Does the warehouse-cut finding survive a change of network shape?

run_generalization.py reports that 29 of 31 disconnecting pairs sit at
warehouses, and attributes that to warehouses being the last tier before
demand. But the generator that produced those networks gives every node
exactly two guaranteed upstream sources and makes every tier the same size,
and both choices affect which pairs can cut a hospital off. This re-runs the
cut analysis under deliberately different shapes.

    python run_shapes.py [instances_per_shape] [seed]
"""

import csv
import random
import sys
from collections import Counter
from pathlib import Path

from src.calibrated import disconnecting_pairs, is_calibrated, scale_capacity, \
    tightest_feasible_factor
from src.shaped import shaped_network

SHAPES = {
    "baseline 3-3-3-4, in-degree 2": ((3, 3, 3, 4), 2),
    "wide warehouses 3-3-6-4": ((3, 3, 6, 4), 2),
    "narrow suppliers 2-4-4-4": ((2, 4, 4, 4), 2),
    "in-degree 3 everywhere": ((4, 4, 4, 4), 3),
    "narrow upstream, wide downstream 2-3-5-5": ((2, 3, 5, 5), 2),
}
COUNT = 25
SEED = 2026


def calibrate(rng, sizes, min_in, why, attempts=30):
    """Returns a calibrated instance, or None after `attempts` tries. Records in
    `why` which of the two filters rejected each attempt: `infeasible` means no
    capacity scaling serves the intact network, `redundant` means some single
    failure leaves every hospital whole."""
    for _ in range(attempts):
        base = shaped_network(rng, sizes, min_in)
        factor = tightest_feasible_factor(base)
        if factor is None:
            why["infeasible"] += 1
            continue
        candidate = scale_capacity(base, factor * (1 + rng.uniform(0.02, 0.50)))
        if is_calibrated(candidate):
            return candidate
        why["redundant"] += 1
    return None


def tier_of(network, node):
    for letter, key in (("S", "suppliers"), ("F", "factories"), ("W", "warehouses")):
        if node in network[key]:
            return letter
    return "?"


def main(count=COUNT, seed=SEED, out_dir="results"):
    rows = []
    for label, (sizes, min_in) in SHAPES.items():
        rng = random.Random(seed)
        made = withcut = tried = 0
        tiers = Counter()
        why = Counter()
        for _ in range(count):
            tried += 1
            net = calibrate(rng, sizes, min_in, why)
            if net is None:
                continue
            made += 1
            cuts = disconnecting_pairs(net)
            if not cuts:
                continue
            withcut += 1
            worst = cuts[0]
            tiers["".join(sorted(tier_of(net, n) for n in worst["pair"]))] += 1
        share = (100.0 * tiers["WW"] / withcut) if withcut else 0.0
        rows.append({"shape": label, "attempted": tried, "instances": made, "with_cut": withcut,
                     "warehouse_pairs": tiers["WW"], "factory_pairs": tiers["FF"],
                     "supplier_pairs": tiers["SS"], "mixed": withcut - tiers["WW"]
                     - tiers["FF"] - tiers["SS"],
                     "warehouse_share": round(share, 1),
                     "rejected_infeasible": why["infeasible"],
                     "rejected_redundant": why["redundant"]})
        print("  %-40s %2d/%2d calibrated, %2d with a cut, tiers %s, rejected %s"
              % (label, made, tried, withcut, dict(tiers), dict(why)), flush=True)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "shapes.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print()
    print("  %-34s %10s %14s" % ("shape", "with a cut", "warehouse share"))
    for r in rows:
        print("  %-34s %10s %13.0f%%"
              % (r["shape"], "%d/%d" % (r["with_cut"], r["instances"]),
                 r["warehouse_share"]))
    print("outputs written to %s/shapes.csv" % out)


if __name__ == "__main__":
    args = sys.argv[1:]
    main(int(args[0]) if args else COUNT, int(args[1]) if len(args) > 1 else SEED)
