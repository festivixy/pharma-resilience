"""How much of the robust plan's advantage comes from optimising the allocation?

The paper compares the optimised plan against a uniform protection level, which
raises every capacity by the same fraction and so spends in proportion to
capacity. That is one heuristic among several. This gives each heuristic exactly
the budget the optimised plan needs for a target, and reports the worst-case
satisfaction it reaches on that money. A heuristic that reaches the target is as
good as the solver at that price.

    python run_baselines.py [steps] [out_dir]
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

TARGETS = [0.75, 0.80, 0.85, 0.90, 0.95, 1.00]
STEPS = 20


def main(steps=STEPS, out_dir="results"):
    network = base_network()
    scenarios = single_node_failures(network)
    rows = []

    for target in TARGETS:
        plan = min_spend_plan(network, scenarios, target)
        if plan["extra"] is None:
            print("  target %.2f is unreachable (%s)" % (target, plan["status"]))
            continue
        budget = plan["spend"]

        reached = {
            "optimal": worst_case_satisfaction(network, plan["extra"], scenarios),
            "proportional": worst_case_satisfaction(
                network, proportional_allocation(network, budget), scenarios),
            "equal": worst_case_satisfaction(
                network, equal_allocation(network, budget), scenarios),
            "greedy": worst_case_satisfaction(
                network, greedy_allocation(network, budget, scenarios, steps), scenarios),
        }
        rows.append(dict({"target": target, "budget": round(budget, 1)},
                         **{k: round(v, 4) for k, v in reached.items()}))
        print("  target %.0f%%  budget %6.1f   optimal %.3f  proportional %.3f  "
              "equal %.3f  greedy %.3f"
              % (100 * target, budget, reached["optimal"], reached["proportional"],
                 reached["equal"], reached["greedy"]), flush=True)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "baselines.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print()
    misses = [(r["target"], name) for r in rows
              for name in ("proportional", "equal", "greedy")
              if r[name] < r["target"] - 1e-6]
    print("  heuristic falls short of the target in %d of %d cases"
          % (len(misses), 3 * len(rows)))
    print("outputs written to %s/baselines.csv" % out)


if __name__ == "__main__":
    args = sys.argv[1:]
    main(int(args[0]) if args else STEPS,
         args[1] if len(args) > 1 else "results")
