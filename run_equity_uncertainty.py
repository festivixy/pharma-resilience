"""Vary the shipping costs and optimise again.

A routing within 5% of the optimal cost is not the same thing as the routing
that becomes optimal when costs move by 5%. This measures the second: for each
of the 618 scenarios, draw every arc cost independently from within +-5% (and
+-20%) of nominal, solve the cost-minimising routing under each draw, and
record the worst-hospital fill rate the optimum actually delivers. The spread
of that figure across draws is the sensitivity of equity to the cost inputs.

    python run_equity_uncertainty.py [draws] [workers]
"""

import csv
import json
import random
import sys
from multiprocessing import Pool
from pathlib import Path

from src.experiment import fail_nodes
from src.model import solve
from src.scenarios import single_node_failures

DRAWS = 20
BANDS = {"pm5": 0.05, "pm20": 0.20}


def _load():
    data = json.load(open("results/instances.json"))
    out = []
    for item in data["instances"]:
        net = dict(item["network"])
        net["arc_cost"] = {(a, b): c for a, b, c in net["arc_cost"]}
        out.append((item["index"], net))
    return out


def _instance(args):
    index, net, draws = args
    rows = []
    for position, failed in enumerate(single_node_failures(net)):
        state = fail_nodes(net, failed)
        nominal = solve(state)["min_fill_rate"]
        row = {"instance": index, "failed": "+".join(failed), "nominal": nominal,
               "draws": draws}
        for band_no, (name, band) in enumerate(BANDS.items()):
            # deterministic seed: Python's hash() of a tuple is salted per process
            rng = random.Random(1_000_000 * band_no + 1000 * index + position)
            fills = []
            for _ in range(draws):
                pert = dict(state)
                pert["arc_cost"] = {a: c * rng.uniform(1 - band, 1 + band)
                                    for a, c in state["arc_cost"].items()}
                fills.append(solve(pert)["min_fill_rate"])
            row[name + "_low"], row[name + "_high"] = min(fills), max(fills)
            row[name + "_strand_draws"] = sum(1 for f in fills if f <= 1e-6)
            row[name + "_distinct"] = len({round(f, 6) for f in fills})
        rows.append(row)
    return rows


def main(draws=DRAWS, workers=6, out_dir="results"):
    instances = _load()
    with Pool(workers) as pool:
        rows = [r for batch in pool.imap_unordered(_instance, [(i, n, draws) for i, n in instances])
                for r in batch]
    rows.sort(key=lambda r: (r["instance"], r["failed"]))
    out = Path(out_dir)
    with open(out / "equity_uncertainty.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    n = len(rows)
    print("  %d scenarios, %d draws per band" % (n, draws))
    print("  %-6s %18s %18s %22s" % ("band", "equity varies", "some draw strands", "draws that strand"))
    for name in BANDS:
        varies = sum(1 for r in rows if r[name + "_high"] - r[name + "_low"] > 1e-5)
        zero = sum(1 for r in rows if r[name + "_low"] <= 1e-6)
        strand_draws = sum(r[name + "_strand_draws"] for r in rows)
        total_draws = sum(r["draws"] for r in rows)
        print("  %-6s %8d (%4.1f%%) %8d (%4.1f%%) %10d of %d (%4.1f%%)"
              % (name, varies, 100.0 * varies / n, zero, 100.0 * zero / n,
                 strand_draws, total_draws, 100.0 * strand_draws / total_draws))
    print("outputs written to %s/equity_uncertainty.csv" % out)


if __name__ == "__main__":
    args = sys.argv[1:]
    main(int(args[0]) if args else DRAWS, int(args[1]) if len(args) > 1 else 6)
