"""The extra cost of a per-hospital guarantee, on a fine grid of targets.

run_equity.py reports six targets. A reviewer found the premium exceeds nine
units between two of them, so this sweeps the target in steps of 0.005 from
0.75 to 1.00, reports the largest premium and where it sits, and times the
greedy rule against the investment program at full delivery so the paper can
say what each costs to run.

    python run_equity_frontier.py [step]
"""

import csv
import sys
import time
from pathlib import Path

from src.baselines import greedy_allocation
from src.network import base_network
from src.robust import min_spend_plan
from src.scenarios import single_node_failures

STEP = 0.005


def main(step=STEP, out_dir="results"):
    net = base_network()
    scenarios = single_node_failures(net)
    rows = []
    target = 0.75
    while target <= 1.0 + 1e-9:
        agg = min_spend_plan(net, scenarios, target)
        per = min_spend_plan(net, scenarios, target, per_hospital=True)
        if agg["spend"] is not None and per["spend"] is not None:
            rows.append({"target": round(target, 4), "aggregate": round(agg["spend"], 4),
                         "per_hospital": round(per["spend"], 4),
                         "extra": round(per["spend"] - agg["spend"], 4)})
        target += step

    worst = max(rows, key=lambda r: r["extra"])
    print("  %d targets from 0.75 to 1.00 in steps of %g" % (len(rows), step))
    print("  largest premium %.3f units at target %.3f (aggregate %.2f, per-hospital %.2f)"
          % (worst["extra"], worst["target"], worst["aggregate"], worst["per_hospital"]))
    for t in (0.86,):
        r = min(rows, key=lambda r: abs(r["target"] - t))
        print("  at target %.3f: aggregate %.2f, per-hospital %.2f, extra %.3f"
              % (r["target"], r["aggregate"], r["per_hospital"], r["extra"]))

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "equity_frontier.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print()
    print("  runtime at full delivery, benchmark instance, wall clock")
    t0 = time.perf_counter()
    plan = min_spend_plan(net, scenarios, 1.0)
    t_opt = time.perf_counter() - t0
    t0 = time.perf_counter()
    greedy_allocation(net, plan["spend"], scenarios, 20)
    t_greedy = time.perf_counter() - t0
    print("  investment program  %.2f s" % t_opt)
    print("  greedy, 20 steps    %.2f s  (%d candidate evaluations of %d scenarios)"
          % (t_greedy, 20 * 9, len(scenarios)))
    with open(out / "equity_frontier_timing.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["method", "seconds"])
        w.writeheader()
        w.writerows([{"method": "optimal", "seconds": round(t_opt, 3)},
                     {"method": "greedy", "seconds": round(t_greedy, 3)}])
    print("outputs written to %s/equity_frontier*.csv" % out)


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else STEP)
