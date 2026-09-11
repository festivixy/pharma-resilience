"""A fairer comparison of the two protection policies.

run_generalization.py compares them at whatever guarantee uniform protection
happens to reach at p = 0.5. On an instance where uniform does badly that sets
a low bar, which flatters the optimizer. This instead fixes the guarantee
first and asks what each policy charges to deliver it, bisecting on p rather
than sweeping so the uniform side is not capped at 0.5.

    python run_dominance.py [count] [seed]
"""

import csv
import random
import sys
import statistics
import time
from pathlib import Path

from src.calibrated import calibrated_network
from src.experiment import apply_protection, evaluate_scenarios, worst_case
from src.robust import ccg_plan
from src.scenarios import single_node_failures

COUNT = 40
SEED = 2026
TARGETS = [0.80, 0.90, 1.00]
CEILING = 4.0
TOL = 1e-6


def worst_at(network, level, scenarios):
    return worst_case(
        evaluate_scenarios(apply_protection(network, level), scenarios)
    )["satisfaction"]


def uniform_cost_for(network, target, scenarios, tolerance=0.005):
    """Smallest uniform level meeting the target, by bisection on p. Returns
    None when no level up to CEILING reaches it, which happens when a single
    facility is a cut vertex."""
    base = network["protection_cost_rate"] * sum(network["capacity"].values())
    if worst_at(network, CEILING, scenarios) < target - TOL:
        return None
    low, high = 0.0, CEILING
    if worst_at(network, 0.0, scenarios) >= target - TOL:
        return 0.0
    while high - low > tolerance:
        mid = (low + high) / 2
        if worst_at(network, mid, scenarios) >= target - TOL:
            high = mid
        else:
            low = mid
    return base * high


def main(count=COUNT, seed=SEED, out_dir="results"):
    start = time.time()
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        network = calibrated_network(rng)
        if network is None:
            continue
        scenarios = single_node_failures(network)
        row = {"index": index, "nodes": len(scenarios)}
        for target in TARGETS:
            key = "t%d" % round(target * 100)
            uniform = uniform_cost_for(network, target, scenarios)
            plan = ccg_plan(network, scenarios, target)
            optimized = plan["spend"] if plan["status"] == "Optimal" else None
            row["%s_uniform" % key] = uniform
            row["%s_optimized" % key] = optimized
            if uniform is None or optimized is None:
                row["%s_saving" % key] = None
            elif uniform <= 0:
                row["%s_saving" % key] = 0.0
            else:
                row["%s_saving" % key] = (uniform - optimized) / uniform
        rows.append(row)
        print("  %3d  " % index + "  ".join(
            "%s %s" % (k, "n/a" if row["t%d_saving" % round(t * 100)] is None
                       else "%.0f%%" % (100 * row["t%d_saving" % round(t * 100)]))
            for k, t in zip(("80%", "90%", "100%"), TARGETS)), flush=True)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "dominance.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print()
    print("instances %d in %.0fs" % (len(rows), time.time() - start))
    for target in TARGETS:
        key = "t%d" % round(target * 100)
        savings = sorted(r["%s_saving" % key] for r in rows
                         if r["%s_saving" % key] is not None)
        wins = sum(1 for s in savings if s > TOL)
        unreachable = sum(1 for r in rows if r["%s_saving" % key] is None)
        if not savings:
            print("  target %.0f%%: no instance reaches it" % (100 * target))
            continue
        print("  target %3.0f%%: optimized cheaper on %d/%d, median saving %.1f%%, "
              "range %.1f%% to %.1f%%, unreachable on %d"
              % (100 * target, wins, len(savings),
                 100 * statistics.median(savings),
                 100 * savings[0], 100 * savings[-1], unreachable))
    print("outputs written to %s/dominance.csv" % out)


if __name__ == "__main__":
    args = sys.argv[1:]
    main(int(args[0]) if args else COUNT, int(args[1]) if len(args) > 1 else SEED)
