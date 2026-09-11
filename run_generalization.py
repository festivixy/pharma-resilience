"""Does the base instance generalize?

Draws calibrated random networks and tests, on each, the four findings the
hand-built instance produces. Writes one row per instance to
results/generalization.csv and prints the replication rates.

    python run_generalization.py [count] [seed]
"""

import csv
import random
import sys
import statistics
import time
from pathlib import Path

from src.calibrated import calibrated_network, disconnecting_pairs
from src.experiment import evaluate_scenarios, protection_sweep, worst_case
from src.robust import apply_allocation, ccg_plan
from src.scenarios import single_node_failures

COUNT = 100
SEED = 2026
LEVELS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
FULL = 1 - 1e-9
TOL = 1e-9


def concavity(sweep):
    """Second differences of worst-case satisfaction against spend. Concave
    means every marginal unit of budget buys no more than the one before it."""
    sats = [row["worst_satisfaction"] for row in sweep]
    seconds = [sats[i + 2] - 2 * sats[i + 1] + sats[i] for i in range(len(sats) - 2)]
    first_half = sats[len(sats) // 2] - sats[0]
    second_half = sats[-1] - sats[len(sats) // 2]
    return {
        "concave": all(d <= TOL for d in seconds),
        "front_loaded": first_half >= second_half - TOL,
        "worst_second_difference": max(seconds),
        "gain_first_half": first_half,
        "gain_second_half": second_half,
    }


def migration(sweep):
    """Does the binding scenario change as protection accumulates? Levels at
    which nothing binds carry no information and are dropped."""
    binding = [
        row["worst_scenario"]
        for row in sweep
        if row["worst_satisfaction"] < FULL
    ]
    distinct = sorted({nodes for nodes in binding})
    return {
        "binding_levels": len(binding),
        "distinct_binding": len(distinct),
        "migrates": len(distinct) > 1,
        "first_binding": "+".join(binding[0]) if binding else "",
        "last_binding": "+".join(binding[-1]) if binding else "",
    }


def dominance(network, sweep, scenarios):
    """Uniform protection at the top of the sweep buys some guarantee. What does
    the optimized allocation charge for the same guarantee?"""
    top = sweep[-1]
    target = top["worst_satisfaction"]
    plan = ccg_plan(network, scenarios, target)
    if plan["status"] != "Optimal":
        return {"target": target, "uniform_spend": top["spend"],
                "optimized_spend": None, "dominates": None, "saving": None}
    achieved = worst_case(
        evaluate_scenarios(apply_allocation(network, plan["extra"]), scenarios)
    )["satisfaction"]
    saving = (
        None if top["spend"] <= 0
        else (top["spend"] - plan["spend"]) / top["spend"]
    )
    return {
        "target": target,
        "uniform_spend": top["spend"],
        "optimized_spend": plan["spend"],
        "achieved": achieved,
        "iterations": plan["iterations"],
        "dominates": plan["spend"] < top["spend"] - TOL,
        "saving": saving,
    }


def floor(network):
    """A topological floor is a pair whose removal severs a hospital from every
    supplier. Its demand is then unservable at any capacity, so the pair caps
    worst-case satisfaction no matter what is spent. This is decided by
    reachability rather than inferred from a curve, so the value is exact."""
    cuts = disconnecting_pairs(network)
    if not cuts:
        return {"has_floor": False, "floor_value": None,
                "floor_pair": "", "cut_pairs": 0, "floor_tier": ""}
    worst = cuts[0]
    tiers = {n: t for t in ("S", "F", "W")
             for n in network[{"S": "suppliers", "F": "factories",
                               "W": "warehouses"}[t]]}
    return {
        "has_floor": True,
        "floor_value": worst["ceiling"],
        "floor_pair": "+".join(worst["pair"]),
        "cut_pairs": len(cuts),
        "floor_tier": "".join(sorted(tiers[n] for n in worst["pair"])),
    }


def study(count, seed):
    rng = random.Random(seed)
    rows = []
    skipped = 0
    for index in range(count):
        network = calibrated_network(rng)
        if network is None:
            skipped += 1
            continue
        singles = single_node_failures(network)
        sweep = protection_sweep(network, LEVELS, singles)

        row = {
            "index": index,
            "nodes": len(singles),
            "hospitals": len(network["hospitals"]),
            "arcs": len(network["arc_cost"]),
            "slack": round(network.get("slack", 0.0), 4),
            "demand": sum(network["demand"].values()),
            "capacity": sum(network["capacity"].values()),
            "worst_at_zero": sweep[0]["worst_satisfaction"],
            "worst_at_top": sweep[-1]["worst_satisfaction"],
        }
        row.update(concavity(sweep))
        row.update(migration(sweep))
        row.update(dominance(network, sweep, singles))
        row.update(floor(network))
        rows.append(row)
        print(f"  {index:3d}  nodes {row['nodes']:2d}  "
              f"concave {str(row['concave']):5s}  "
              f"migrates {str(row['migrates']):5s}  "
              f"dominates {str(row['dominates']):5s}  "
              f"floor {str(row['has_floor']):5s}", flush=True)
    return rows, skipped


def rate(rows, key):
    values = [row[key] for row in rows if row[key] is not None]
    return (sum(1 for v in values if v) / len(values), len(values)) if values else (0.0, 0)


def main(count=COUNT, seed=SEED, out_dir="results"):
    start = time.time()
    rows, skipped = study(count, seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    with open(out / "generalization.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f"instances {len(rows)} ({skipped} draws could not be calibrated) "
          f"in {time.time() - start:.0f}s")
    for label, key in [
        ("F1 concave returns", "concave"),
        ("F1 front-loaded returns", "front_loaded"),
        ("F2 binding node migrates", "migrates"),
        ("F3 optimized dominates uniform", "dominates"),
        ("F4 topological floor under pairs", "has_floor"),
    ]:
        fraction, n = rate(rows, key)
        print(f"  {label:34s} {fraction:6.1%}  ({n} instances)")

    savings = [row["saving"] for row in rows if row["saving"] is not None]
    if savings:
        savings.sort()
        mid = statistics.median(savings)
        print(f"  {'median saving over uniform':34s} {mid:6.1%}")
    print(f"outputs written to {out}/generalization.csv")


if __name__ == "__main__":
    args = sys.argv[1:]
    main(int(args[0]) if args else COUNT, int(args[1]) if len(args) > 1 else SEED)
