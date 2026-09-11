"""Is the equity degeneracy a property of the benchmark or of the formulation?

run_equity.py shows that on the benchmark instance every single-failure scenario
admits a range of cost-optimal routings with different worst-served hospitals,
and that every one of those ranges reaches zero. That is nine scenarios of one
hand-built network. This repeats the measurement on the generated family, using
the same seed and count as run_generalization.py so the instances are the same
61 the rest of the paper reports on.

    python run_equity_general.py [count] [seed]
"""

import csv
import random
import statistics
import sys
from pathlib import Path

import pulp

from src.calibrated import calibrated_network
from src.experiment import fail_nodes
from src.model import solve
from src.scenarios import single_node_failures
from run_equity import equity_at_optimal_cost

COUNT = 120
SEED = 2026


def scenario_row(network, failed):
    """Reported equity against the range every cost-optimal routing can reach."""
    state = fail_nodes(network, failed)
    result = solve(state)
    low = equity_at_optimal_cost(state, pulp.LpMinimize)
    high = equity_at_optimal_cost(state, pulp.LpMaximize)
    if low is None or high is None:
        return None
    return {
        "satisfaction": result["satisfaction"],
        "reported": result["min_fill_rate"],
        "low": low,
        "high": high,
        "width": high - low,
    }


def main(count=COUNT, seed=SEED, out_dir="results"):
    rng = random.Random(seed)
    rows = []
    instances = 0

    for index in range(count):
        network = calibrated_network(rng)
        if network is None:
            continue
        instances += 1
        for failed in single_node_failures(network):
            row = scenario_row(network, failed)
            if row is None:
                continue
            rows.append(dict({"instance": index, "failed": "+".join(failed)}, **row))
        print("  instance %d done, %d scenarios so far" % (instances, len(rows)),
              flush=True)

    degenerate = [r for r in rows if r["width"] > 1e-6]
    reaches_zero = [r for r in rows if r["low"] <= 1e-6]
    by_instance = {}
    for r in rows:
        by_instance.setdefault(r["instance"], []).append(r)
    all_degenerate = [i for i, rs in by_instance.items()
                      if all(r["width"] > 1e-6 for r in rs)]

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "equity_general.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print()
    print("  instances                     %d" % instances)
    print("  scenarios                     %d" % len(rows))
    print("  degenerate scenarios          %d (%.1f%%)"
          % (len(degenerate), 100.0 * len(degenerate) / len(rows)))
    print("  ranges reaching zero          %d (%.1f%%)"
          % (len(reaches_zero), 100.0 * len(reaches_zero) / len(rows)))
    print("  instances degenerate in every scenario  %d of %d"
          % (len(all_degenerate), instances))
    print("  median range width            %.4f"
          % statistics.median(r["width"] for r in rows))
    print("  median reported equity        %.4f"
          % statistics.median(r["reported"] for r in rows))
    print("outputs written to %s/equity_general.csv" % out)


if __name__ == "__main__":
    args = sys.argv[1:]
    main(int(args[0]) if args else COUNT,
         int(args[1]) if len(args) > 1 else SEED)
