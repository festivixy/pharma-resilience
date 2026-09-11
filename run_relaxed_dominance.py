"""Does the saving over uniform depend on selecting networks where every
single failure hurts?

The calibrated generator keeps a network only if every single failure causes
a shortage. This relaxes that to: the intact network serves everyone and at
least one, but not every, single failure causes a shortage. It then repeats
the fixed-target comparison of run_dominance.py at full delivery.

    python run_relaxed_dominance.py [count] [seed]
"""

import csv
import random
import statistics
import sys
from pathlib import Path

from run_dominance import uniform_cost_for
from src.calibrated import scale_capacity, tightest_feasible_factor
from src.experiment import fail_nodes
from src.generator import random_layered_network
from src.model import solve
from src.robust import min_spend_plan
from src.scenarios import single_node_failures

COUNT = 24
SEED = 2026
FULL = 1 - 1e-9


def relaxed_network(rng, attempts=40):
    for _ in range(attempts):
        base = random_layered_network(rng)
        factor = tightest_feasible_factor(base)
        if factor is None:
            continue
        net = scale_capacity(base, factor * (1 + rng.uniform(0.02, 0.50)))
        if solve(net)["satisfaction"] < FULL:
            continue
        hurt = sum(1 for f in single_node_failures(net)
                   if solve(fail_nodes(net, f))["satisfaction"] < FULL)
        total = len(single_node_failures(net))
        if 0 < hurt < total:
            net["hurt"], net["total"] = hurt, total
            return net
    return None


def main(count=COUNT, seed=SEED, out_dir="results"):
    rng = random.Random(seed)
    rows = []
    made = 0
    while made < count:
        net = relaxed_network(rng)
        if net is None:
            continue
        made += 1
        sc = single_node_failures(net)
        uniform = uniform_cost_for(net, 1.0, sc)
        opt = min_spend_plan(net, sc, 1.0)["spend"]
        saving = None if uniform is None or opt is None or uniform <= 0 else (uniform - opt) / uniform
        rows.append({"instance": made, "hurt": net["hurt"], "total": net["total"],
                     "uniform": uniform, "optimal": opt, "saving": saving})
        print("  %2d  %d of %d failures hurt  uniform %s  optimal %s  saving %s"
              % (made, net["hurt"], net["total"],
                 "none" if uniform is None else "%.1f" % uniform,
                 "none" if opt is None else "%.1f" % opt,
                 "none" if saving is None else "%.1f%%" % (100 * saving)), flush=True)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "relaxed_dominance.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    ok = [r["saving"] for r in rows if r["saving"] is not None]
    print()
    print("  %d instances, %d with both plans feasible" % (len(rows), len(ok)))
    print("  saving at full delivery: median %.1f%%, range %.1f%% to %.1f%%"
          % (100 * statistics.median(ok), 100 * min(ok), 100 * max(ok)))
    print("  median share of single failures that hurt: %.2f"
          % statistics.median(r["hurt"] / r["total"] for r in rows))
    print("outputs written to %s/relaxed_dominance.csv" % out)


if __name__ == "__main__":
    args = sys.argv[1:]
    main(int(args[0]) if args else COUNT, int(args[1]) if len(args) > 1 else SEED)
