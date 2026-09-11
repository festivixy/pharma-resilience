"""Does the equity range depend on exact ties in shipping cost?

The generated networks draw shipping costs as integers from 1 to 5, so exact
ties between routings are common, and scaling every cost by the same factor
cannot disturb them. This re-measures the equity range on the same 61
instances as run_equity_general.py under three further conditions:

  perturbed   every arc cost multiplied by an independent draw from
              U(0.8, 1.2), which breaks exact ties
  near_1pct   original costs, routings allowed to cost up to 1% more in
              shipping while delivering the optimal total
  near_5pct   the same at 5%

It also writes the generated instances to results/instances.json so the
population results can be reproduced without re-running the generator, and
records the arc-cost distribution across them.

    python run_equity_sensitivity.py [count] [seed] [workers]
"""

import csv
import json
import random
import statistics
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

import pulp

from run_equity import equity_at_optimal_cost
from src.calibrated import calibrated_network
from src.experiment import fail_nodes
from src.model import solve
from src.scenarios import single_node_failures

COUNT = 120
SEED = 2026
PERTURB_SEED = 7
CONDITIONS = {"exact": 0.0, "near_1pct": 0.01, "near_5pct": 0.05}


def _range(state, shipping_slack):
    low = equity_at_optimal_cost(state, pulp.LpMinimize, shipping_slack=shipping_slack)
    high = equity_at_optimal_cost(state, pulp.LpMaximize, shipping_slack=shipping_slack)
    return low, high


def _perturb(network, rng):
    out = dict(network)
    out["arc_cost"] = {a: c * rng.uniform(0.8, 1.2) for a, c in network["arc_cost"].items()}
    return out


def _instance_rows(args):
    index, network = args
    rng = random.Random(PERTURB_SEED + index)
    perturbed = _perturb(network, rng)
    rows = []
    for failed in single_node_failures(network):
        state = fail_nodes(network, failed)
        row = {"instance": index, "failed": "+".join(failed),
               "satisfaction": solve(state)["satisfaction"]}
        for name, slack in CONDITIONS.items():
            low, high = _range(state, slack)
            row[name + "_low"], row[name + "_high"] = low, high
        low, high = _range(fail_nodes(perturbed, failed), 0.0)
        row["perturbed_low"], row["perturbed_high"] = low, high
        rows.append(row)
    return rows


def _serialisable(network):
    out = dict(network)
    out["arc_cost"] = [[a[0], a[1], c] for a, c in network["arc_cost"].items()]
    return out


def main(count=COUNT, seed=SEED, workers=6, out_dir="results"):
    rng = random.Random(seed)
    instances = []
    for index in range(count):
        network = calibrated_network(rng)
        if network is not None:
            instances.append((index, network))
    print("  %d calibrated instances" % len(instances), flush=True)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "instances.json", "w") as f:
        json.dump({"seed": seed, "count": count,
                   "instances": [{"index": i, "network": _serialisable(n)}
                                 for i, n in instances]}, f)

    costs = Counter(c for _, n in instances for c in n["arc_cost"].values())
    print("  arc-cost distribution over %d arcs: %s"
          % (sum(costs.values()), dict(sorted(costs.items()))), flush=True)

    with Pool(workers) as pool:
        rows = [r for batch in pool.imap_unordered(_instance_rows, instances) for r in batch]
    rows.sort(key=lambda r: (r["instance"], r["failed"]))

    with open(out / "equity_sensitivity.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print()
    print("  %-12s %10s %12s %12s" % ("condition", "degenerate", "reach zero", "median width"))
    for name in list(CONDITIONS) + ["perturbed"]:
        deg = [r for r in rows if r[name + "_high"] - r[name + "_low"] > 1e-5]
        zero = [r for r in rows if r[name + "_low"] <= 1e-6]
        width = statistics.median(r[name + "_high"] - r[name + "_low"] for r in deg) if deg else 0.0
        print("  %-12s %4d (%4.1f%%) %4d (%4.1f%%) %12.3f"
              % (name, len(deg), 100.0 * len(deg) / len(rows),
                 len(zero), 100.0 * len(zero) / len(rows), width))
    print("outputs written to %s/equity_sensitivity.csv and instances.json" % out)


if __name__ == "__main__":
    args = sys.argv[1:]
    main(int(args[0]) if args else COUNT,
         int(args[1]) if len(args) > 1 else SEED,
         int(args[2]) if len(args) > 2 else 6)
