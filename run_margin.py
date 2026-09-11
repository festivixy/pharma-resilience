"""Why does the binding facility move on the hand-built instance and not on
generated ones?

Migration needs two scenarios close enough in damage that uniform scaling can
swap their order. This measures that closeness: the gap between the worst and
second-worst scenario at zero protection, as a fraction of total demand. Runs
over the same networks as run_generalization.py, and prints the benchmark
instance alongside for comparison.

    python run_margin.py [count] [seed]
"""

import csv
import random
import sys
from pathlib import Path

from src.calibrated import calibrated_network
from src.experiment import evaluate_scenarios
from src.network import base_network
from src.scenarios import single_node_failures

COUNT = 60
SEED = 2026


def margin(network):
    rows = evaluate_scenarios(network, single_node_failures(network))
    ranked = sorted(rows, key=lambda row: row["satisfaction"])
    worst, second = ranked[0], ranked[1]
    return {
        "worst_scenario": "+".join(worst["failed"]),
        "worst_satisfaction": worst["satisfaction"],
        "second_scenario": "+".join(second["failed"]),
        "second_satisfaction": second["satisfaction"],
        "margin": second["satisfaction"] - worst["satisfaction"],
        "scenarios": len(rows),
    }


def main(count=COUNT, seed=SEED, out_dir="results"):
    base = margin(base_network())
    print("benchmark instance: worst %s %.4f, second %s %.4f, margin %.4f"
          % (base["worst_scenario"], base["worst_satisfaction"],
             base["second_scenario"], base["second_satisfaction"], base["margin"]))

    rng = random.Random(seed)
    rows = []
    for index in range(count):
        network = calibrated_network(rng)
        if network is None:
            continue
        rows.append({"index": index, **margin(network)})
        print("  %3d  margin %.4f  (%s then %s)"
              % (index, rows[-1]["margin"], rows[-1]["worst_scenario"],
                 rows[-1]["second_scenario"]), flush=True)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "margin.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    margins = sorted(row["margin"] for row in rows)
    mid = margins[len(margins) // 2]
    tighter = sum(1 for m in margins if m <= base["margin"])
    print()
    print("instances %d" % len(rows))
    print("  benchmark margin           %.4f" % base["margin"])
    print("  median generated margin    %.4f" % mid)
    print("  generated at or below the benchmark's margin  %d (%.0f%%)"
          % (tighter, 100.0 * tighter / len(rows)))
    print("outputs written to %s/margin.csv" % out)


if __name__ == "__main__":
    args = sys.argv[1:]
    main(int(args[0]) if args else COUNT, int(args[1]) if len(args) > 1 else SEED)
