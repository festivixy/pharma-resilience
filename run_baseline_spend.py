"""What each heuristic has to spend to reach full delivery.

run_baselines.py fixes the budget and compares satisfaction. The paper's
headline runs the other way, comparing what the optimised plan spends against
what a uniform level spends for the same guarantee, so this reports the same
quantity for every heuristic. Greedy re-plans at every budget and its result is
not guaranteed monotone in spend, so this scans a grid rather than bisecting.

    python run_baseline_spend.py [target] [steps]
"""

import csv
import sys
from pathlib import Path

from src.baselines import (
    equal_allocation,
    greedy_allocation,
    proportional_allocation,
    worst_case_satisfaction,
)
from src.network import base_network
from src.robust import min_spend_plan
from src.scenarios import single_node_failures

TARGET = 1.00
STEPS = 20
GRID = range(170, 341, 10)


def first_budget_reaching(network, scenarios, target, allocate, label):
    for budget in GRID:
        got = worst_case_satisfaction(network, allocate(budget), scenarios)
        print("    %-13s %5d -> %.4f" % (label, budget, got), flush=True)
        if got >= target - 1e-6:
            return budget, got
    return None, None


def main(target=TARGET, steps=STEPS, out_dir="results"):
    network = base_network()
    scenarios = single_node_failures(network)
    optimal = min_spend_plan(network, scenarios, target)["spend"]
    print("  optimised plan reaches %.0f%% at %.1f" % (100 * target, optimal))

    rows = [{"rule": "optimal", "spend": round(optimal, 1), "premium_pct": 0.0}]
    for label, allocate in (
        ("proportional", lambda b: proportional_allocation(network, b)),
        ("equal", lambda b: equal_allocation(network, b)),
        ("greedy", lambda b: greedy_allocation(network, b, scenarios, steps)),
    ):
        budget, _ = first_budget_reaching(network, scenarios, target, allocate, label)
        rows.append({
            "rule": label,
            "spend": budget,
            "premium_pct": None if budget is None
            else round(100 * (budget - optimal) / optimal, 1),
        })

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "baseline_spend.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["rule", "spend", "premium_pct"])
        w.writeheader()
        w.writerows(rows)

    print()
    for r in rows:
        if r["spend"] is None:
            print("  %-13s never reaches the target inside the grid" % r["rule"])
        else:
            print("  %-13s %5s   %+.1f%% against the optimised plan"
                  % (r["rule"], r["spend"], r["premium_pct"]))
    print("outputs written to %s/baseline_spend.csv" % out)


if __name__ == "__main__":
    args = sys.argv[1:]
    main(float(args[0]) if args else TARGET,
         int(args[1]) if len(args) > 1 else STEPS)
