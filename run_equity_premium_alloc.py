"""Equal investment cost is not the same as the same allocation.

run_equity_premium.py finds that on most generated networks the per-hospital
guarantee costs no more than the aggregate one. That says an equitable plan
can be bought for the same money. It does not say the aggregate-optimal
allocation, once installed, supports an equitable routing. This installs the
aggregate-optimal allocation and asks whether the per-hospital target is then
reachable with zero further investment.

    python run_equity_premium_alloc.py [workers]
"""

import csv
import json
import sys
from multiprocessing import Pool
from pathlib import Path

from src.robust import apply_allocation, min_spend_plan
from src.scenarios import single_node_failures

TARGETS = [0.80, 0.90]


def _load():
    data = json.load(open("results/instances.json"))
    out = []
    for item in data["instances"]:
        net = dict(item["network"])
        net["arc_cost"] = {(a, b): c for a, b, c in net["arc_cost"]}
        out.append((item["index"], net))
    return out


def _instance(args):
    index, net = args
    sc = single_node_failures(net)
    rows = []
    for t in TARGETS:
        agg = min_spend_plan(net, sc, t)
        per = min_spend_plan(net, sc, t, per_hospital=True)
        if agg["extra"] is None or per["spend"] is None:
            continue
        installed = apply_allocation(net, agg["extra"])
        top_up = min_spend_plan(installed, sc, t, per_hospital=True)["spend"]
        rows.append({"instance": index, "target": t,
                     "aggregate": agg["spend"], "per_hospital": per["spend"],
                     "equal_cost": abs(per["spend"] - agg["spend"]) < 1e-6,
                     "top_up_on_installed": top_up,
                     "installed_supports_equity": top_up is not None and top_up < 1e-6})
    return rows


def main(workers=4, out_dir="results"):
    with Pool(workers) as pool:
        rows = [r for batch in pool.imap_unordered(_instance, _load()) for r in batch]
    rows.sort(key=lambda r: (r["target"], r["instance"]))
    out = Path(out_dir)
    with open(out / "equity_premium_alloc.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("  %-6s %10s %14s %22s" % ("target", "networks", "equal cost", "installed supports it"))
    for t in TARGETS:
        rs = [r for r in rows if r["target"] == t]
        eq = [r for r in rs if r["equal_cost"]]
        print("  %-6.2f %10d %14d %22d"
              % (t, len(rs), len(eq), sum(1 for r in eq if r["installed_supports_equity"])))
    print("outputs written to %s/equity_premium_alloc.csv" % out)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4)
