"""Is the equity shortfall a property of the calibrated family, or of routing
by cost?

The 61 calibrated networks pass a filter that rejects most of what the
generator draws, and they share one shape. This repeats the equity measurement
on families that do not pass through the filter and on other shapes, including
the three shapes that produced no calibrated network at all in run_shapes.py.

Every arc cost is scaled by its own draw from [0.8, 1.2] so that the
cost-minimising routing is unique. Each state in which some demand goes unmet
is then measured three ways:

  equity        the worst-hospital fill rate of the cost-minimising routing
  fair_equity   the best worst-hospital fill rate any routing delivering the
                same total can reach
  fair_shipping the cheapest shipping cost of a routing that reaches it

    python run_equity_families.py [networks_per_family] [workers]
"""

import csv
import json
import random
import statistics
import sys
from multiprocessing import Pool
from pathlib import Path

from src.experiment import fail_nodes
from src.fairness import fair_equity, fair_shipping_cost, generic_costs
from src.families import bootstrap_interval, raw_network, tightened_network
from src.model import solve
from src.scenarios import pair_failures, single_node_failures

COUNT = 60
SEED = 2026
FULL = 1 - 1e-9
STRANDED = 1e-6
GAP = 0.01
# shortfalls and demands are whole numbers, so a shortfall equal to the smallest
# demand is a real case, and solver rounding must not push it under the line
AT_LEAST_ONE = 1 - 1e-6

# name, tier sizes, guaranteed in-degree, failure set
FAMILIES = [
    ("calibrated", None, None, "single"),
    ("calibrated", None, None, "pair"),
    ("tightened", None, None, "single"),
    ("raw", None, None, "single"),
    ("raw", None, None, "pair"),
    ("3-3-6-4", (3, 3, 6, 4), 2, "single"),
    ("2-4-4-4", (2, 4, 4, 4), 2, "single"),
    ("4-4-4-4 in-degree 3", (4, 4, 4, 4), 3, "single"),
    ("2-3-5-5", (2, 3, 5, 5), 2, "single"),
    ("6-6-6-8", (6, 6, 6, 8), 2, "single"),
    ("5-5-5-10 in-degree 3", (5, 5, 5, 10), 3, "single"),
]
FAMILY_NAMES = list(dict.fromkeys(f[0] for f in FAMILIES))


def _calibrated():
    data = json.load(open("results/instances.json"))
    out = []
    for item in data["instances"]:
        net = dict(item["network"])
        net["arc_cost"] = {(a, b): c for a, b, c in net["arc_cost"]}
        out.append(net)
    return out


def networks(name, sizes, min_in_degree, count, seed):
    if name == "calibrated":
        return _calibrated()
    rng = random.Random(seed)
    out = []
    while len(out) < count:
        net = raw_network(rng) if name == "raw" else \
            tightened_network(rng, sizes, min_in_degree)
        if net is not None:
            out.append(net)
    return out


def state_row(state):
    """One network state under tie-free costs, or None if nobody goes short."""
    result = solve(state)
    if result["satisfaction"] >= FULL:
        return None
    demand = state["demand"]
    unmet = result["unmet"]
    fair = fair_equity(state)
    return {
        "satisfaction": result["satisfaction"],
        "shortfall_over_smallest_demand": sum(unmet.values()) / min(demand.values()),
        "equity": result["min_fill_rate"],
        "fair_equity": fair,
        # the same with no requirement to deliver the maximum total; equal to
        # fair_equity whenever fairness costs no delivery
        "fair_equity_any_total": fair_equity(state, hold_delivery=False),
        "shipping": result["shipping_cost"],
        # a hair under the fair value, so solver tolerance cannot make it infeasible
        "fair_shipping": fair_shipping_cost(state, fair - 1e-7),
        "partly_served": sum(1 for h in demand if 1e-6 < unmet[h] < demand[h] - 1e-6),
        "unserved": sum(1 for h in demand if unmet[h] >= demand[h] - 1e-6),
    }


def _instance(args):
    family, failures, index, network, cost_seed = args
    net = generic_costs(network, random.Random(cost_seed))
    scenarios = pair_failures(net) if failures == "pair" else single_node_failures(net)
    rows = []
    for failed in scenarios:
        row = state_row(fail_nodes(net, failed))
        if row is not None:
            rows.append(dict({"family": family, "failures": failures, "instance": index,
                              "failed": "+".join(failed)}, **row))
    return len(scenarios), rows


def _rate(rows_by_instance, test, rng):
    clusters = [(sum(1 for r in rows if test(r)), len(rows))
                for rows in rows_by_instance.values()]
    events = sum(e for e, _ in clusters)
    states = sum(n for _, n in clusters)
    low, high = bootstrap_interval(clusters, rng)
    return events, events / states, low, high


def summarise(family, failures, n_networks, n_states, rows):
    by_instance = {}
    for r in rows:
        by_instance.setdefault(r["instance"], []).append(r)
    rng = random.Random(SEED)
    stranded = _rate(by_instance, lambda r: r["equity"] <= STRANDED, rng)
    avoidable = sum(1 for r in rows
                    if r["equity"] <= STRANDED and r["fair_equity"] > STRANDED)
    short = _rate(by_instance, lambda r: r["fair_equity"] - r["equity"] > GAP, rng)
    gaps = [r["fair_equity"] - r["equity"] for r in rows]
    premium = [(r["fair_shipping"] - r["shipping"]) / r["shipping"] for r in rows
               if r["fair_shipping"] is not None]
    premium.sort()
    return {
        "family": family, "failures": failures, "networks": n_networks,
        "states": n_states, "shortage_states": len(rows),
        "networks_with_shortage": len(by_instance),
        "stranded": stranded[0], "stranded_rate": stranded[1],
        "stranded_low": stranded[2], "stranded_high": stranded[3],
        "stranded_avoidable": avoidable,
        "below_fair": short[0], "below_fair_rate": short[1],
        "below_fair_low": short[2], "below_fair_high": short[3],
        "mean_gap": statistics.mean(gaps), "median_gap": statistics.median(gaps),
        "premium_median": statistics.median(premium),
        "premium_mean": statistics.mean(premium),
        "premium_p90": premium[int(0.9 * len(premium))],
        "premium_max": premium[-1],
    }


def _write(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main(count=COUNT, workers=6, out_dir="results"):
    rows, summary = [], []
    with Pool(workers) as pool:
        for name, sizes, min_in_degree, failures in FAMILIES:
            # the seed depends on the family, not the failure set, so the single
            # and pair rows of one family describe the same networks
            family_seed = SEED + FAMILY_NAMES.index(name)
            nets = networks(name, sizes, min_in_degree, count, family_seed)
            jobs = [(name, failures, i, net, 1000 * family_seed + i)
                    for i, net in enumerate(nets)]
            results = pool.map(_instance, jobs)
            family_rows = [r for _, rs in results for r in rs]
            rows.extend(family_rows)
            line = summarise(name, failures, len(nets),
                             sum(n for n, _ in results), family_rows)
            summary.append(line)
            print("  %-22s %-6s %3d networks, %4d of %4d states short | stranded %5.1f%% "
                  "[%4.1f, %4.1f] | below fair %5.1f%% [%4.1f, %4.1f], mean gap %.3f | "
                  "shipping premium median %4.1f%%, mean %4.1f%%, max %5.1f%%"
                  % (name, failures, line["networks"], line["shortage_states"], line["states"],
                     100 * line["stranded_rate"], 100 * line["stranded_low"],
                     100 * line["stranded_high"], 100 * line["below_fair_rate"],
                     100 * line["below_fair_low"], 100 * line["below_fair_high"],
                     line["mean_gap"], 100 * line["premium_median"],
                     100 * line["premium_mean"], 100 * line["premium_max"]), flush=True)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write(out / "equity_families.csv", rows)
    _write(out / "equity_families_summary.csv", summary)

    single = [r for r in rows if r["failures"] == "single"]
    possible = [r for r in single if r["shortfall_over_smallest_demand"] >= AT_LEAST_ONE]
    print()
    print("  single-failure shortage states, all families: %d" % len(single))
    print("  stranded and avoidable: %d of %d stranded"
          % (sum(1 for r in single if r["equity"] <= STRANDED and r["fair_equity"] > STRANDED),
             sum(1 for r in single if r["equity"] <= STRANDED)))
    print("  shortfall at least the smallest demand: %d, of which stranded %d (%.1f%%)"
          % (len(possible), sum(1 for r in possible if r["equity"] <= STRANDED),
             100.0 * sum(1 for r in possible if r["equity"] <= STRANDED) / len(possible)))
    print("  shortfall below the smallest demand: %d, of which stranded %d"
          % (len(single) - len(possible),
             sum(1 for r in single if r["shortfall_over_smallest_demand"] < AT_LEAST_ONE
                 and r["equity"] <= STRANDED)))
    print("  all %d shortage states: fair equity changes by at most %.1e when the "
          "maximum total is not required"
          % (len(rows), max(abs(r["fair_equity_any_total"] - r["fair_equity"]) for r in rows)))
    print("  states with no equitable routing found, left out of the premium: %d"
          % sum(1 for r in rows if r["fair_shipping"] is None))
    print("outputs written to %s/equity_families.csv and equity_families_summary.csv" % out)


if __name__ == "__main__":
    args = sys.argv[1:]
    main(int(args[0]) if args else COUNT, int(args[1]) if len(args) > 1 else 6)
