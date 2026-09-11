"""What the per-hospital guarantee costs across the generated family, and the
exact maximum premium on the benchmark.

    python run_equity_premium.py [workers]
"""

import csv
import json
import statistics
import sys
from multiprocessing import Pool
from pathlib import Path

from src.network import base_network
from src.robust import min_spend_plan
from src.scenarios import single_node_failures

TARGETS = [0.80, 0.90, 1.00]


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
        agg = min_spend_plan(net, sc, t)["spend"]
        per = min_spend_plan(net, sc, t, per_hospital=True)["spend"]
        rows.append({"instance": index, "target": t, "aggregate": agg, "per_hospital": per,
                     "extra": None if agg is None or per is None else per - agg,
                     "relative": None if agg is None or per is None or agg <= 1e-9
                     else (per - agg) / agg})
    return rows


def benchmark_maximum():
    """The premium is piecewise linear in the target, so its maximum sits at a
    breakpoint. Search a 0.0001 grid around the coarse maximum."""
    net = base_network()
    sc = single_node_failures(net)
    best = (0.0, None)
    t = 0.850
    while t <= 0.870 + 1e-12:
        agg = min_spend_plan(net, sc, t)["spend"]
        per = min_spend_plan(net, sc, t, per_hospital=True)["spend"]
        if agg is not None and per is not None and per - agg > best[0]:
            best = (per - agg, t)
        t += 0.0001
    return best


def main(workers=6, out_dir="results"):
    premium, at = benchmark_maximum()
    print("  benchmark: largest premium %.4f at target %.4f" % (premium, at))

    with Pool(workers) as pool:
        rows = [r for batch in pool.imap_unordered(_instance, _load()) for r in batch]
    rows.sort(key=lambda r: (r["target"], r["instance"]))
    out = Path(out_dir)
    with open(out / "equity_premium.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(out / "equity_premium_benchmark_max.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["premium", "target"])
        w.writeheader()
        w.writerow({"premium": round(premium, 4), "target": round(at, 4)})

    print("  %-6s %9s %9s %9s %9s %9s %9s" % ("target", "feasible", "zero", "median", "max", "med rel", "max rel"))
    for t in TARGETS:
        ok = [r for r in rows if r["target"] == t and r["extra"] is not None]
        if not ok:
            print("  %-6.2f none feasible" % t)
            continue
        rel = [r["relative"] for r in ok if r["relative"] is not None]
        print("  %-6.2f %9d %9d %9.2f %9.2f %8.0f%% %8.0f%%"
              % (t, len(ok), sum(1 for r in ok if r["extra"] < 1e-6),
                 statistics.median(r["extra"] for r in ok), max(r["extra"] for r in ok),
                 100 * statistics.median(rel) if rel else 0, 100 * max(rel) if rel else 0))
    print("outputs written to %s/equity_premium*.csv" % out)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
