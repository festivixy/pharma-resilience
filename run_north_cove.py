"""The model against the North Cove failure.

Runs the paper's analyses on the documented IV-solutions network of
src/north_cove.py and prints what the model says next to what happened.

    python run_north_cove.py [out_dir]
"""

import csv
import sys
from pathlib import Path

import pulp

from run_equity import equity_at_optimal_cost
from src.baselines import greedy_allocation, worst_case_satisfaction
from src.experiment import apply_protection, evaluate_scenarios, fail_nodes, \
    protection_spend, worst_case
from src.model import solve
from src.north_cove import north_cove_network
from src.robust import apply_allocation, min_spend_plan
from src.scenarios import pair_failures, single_node_failures

TARGETS = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
BBRAUN_INCREASE = 0.20   # announced 18 Oct 2024


def uniform_level_for(network, scenarios, target, hi=4.0, tolerance=1e-4):
    """Smallest uniform protection level whose worst case reaches `target`."""
    if worst_case(evaluate_scenarios(apply_protection(network, hi), scenarios))[
            "satisfaction"] < target - 1e-9:
        return None
    lo = 0.0
    while hi - lo > tolerance:
        mid = (lo + hi) / 2
        got = worst_case(evaluate_scenarios(apply_protection(network, mid), scenarios))
        if got["satisfaction"] >= target - 1e-9:
            hi = mid
        else:
            lo = mid
    return hi


def main(out_dir="results"):
    net = north_cove_network()
    singles = single_node_failures(net)
    # Only the plants are facilities that can fail as one event. A channel node
    # stands for a wholesaler's 26 to 40 distribution centres, or for Baxter's
    # own direct shipping, so the protection analysis runs over plants alone.
    # The channel rows are still reported in the first table for completeness.
    plants = [(p,) for p in net["suppliers"]]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # --- 1. every single failure, and the equity each one leaves open -------
    print("single failures at zero protection (channel rows are not physical events)")
    rows = []
    for (node,) in singles:
        state = fail_nodes(net, [node])
        r = solve(state)
        low = equity_at_optimal_cost(state, pulp.LpMinimize)
        high = equity_at_optimal_cost(state, pulp.LpMaximize)
        rows.append({"failed": node, "satisfaction": round(r["satisfaction"], 4),
                     "reported_equity": round(r["min_fill_rate"], 4),
                     "equity_low": round(low, 4), "equity_high": round(high, 4)})
        print("  %-10s satisfaction %.3f   equity reported %.3f, range %.3f to %.3f"
              % (node, r["satisfaction"], r["min_fill_rate"], low, high))
    with open(out / "north_cove_singles.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # --- 2. what the documented responses buy --------------------------------
    print("\nNorth Cove down, surviving plants raised")
    nc = ["NorthCove"]
    bb_only = apply_allocation(net, {"BBraun": BBRAUN_INCREASE * net["capacity"]["BBraun"]})
    both = apply_allocation(net, {"BBraun": BBRAUN_INCREASE * net["capacity"]["BBraun"],
                                  "Others": BBRAUN_INCREASE * net["capacity"]["Others"]})
    print("  B. Braun +20%%              satisfaction %.3f" % solve(fail_nodes(bb_only, nc))["satisfaction"])
    print("  all surviving plants +20%%  satisfaction %.3f" % solve(fail_nodes(both, nc))["satisfaction"])

    # --- 3. paired plant failures ---------------------------------------------
    print("\npaired plant failures")
    for pair in pair_failures({**net, "warehouses": []}):
        print("  %-18s satisfaction %.3f" % ("+".join(pair),
                                              solve(fail_nodes(net, pair))["satisfaction"]))

    # --- 4. the frontier: uniform, greedy, optimal, per-hospital -------------
    print("\nprotection needed for each worst-case target over single plant failures")
    print("  target   uniform   greedy   optimal   per-hospital   optimal allocation")
    frontier = []
    for target in TARGETS:
        opt = min_spend_plan(net, plants, target)
        per = min_spend_plan(net, plants, target, per_hospital=True)
        level = uniform_level_for(net, plants, target)
        uniform = protection_spend(net, level) if level is not None else None
        greedy = None
        if opt["spend"] is not None:
            # give greedy the optimal budget and bisect upward until it reaches the target
            lo, hi = opt["spend"], 6 * opt["spend"] + 1
            for _ in range(10):
                mid = (lo + hi) / 2
                got = worst_case_satisfaction(net, greedy_allocation(net, mid, plants, 10), plants)
                if got >= target - 1e-6:
                    hi = mid
                else:
                    lo = mid
            greedy = hi
        alloc = {k: round(v, 1) for k, v in opt["extra"].items() if v > 1e-6} \
            if opt["extra"] else None
        frontier.append({"target": target, "uniform": uniform, "greedy": greedy,
                         "optimal": opt["spend"], "per_hospital": per["spend"]})
        print("  %4.0f%%   %7s   %6s   %7s   %12s   %s"
              % (100 * target,
                 "%.1f" % uniform if uniform is not None else "none",
                 "%.1f" % greedy if greedy is not None else "none",
                 "%.1f" % opt["spend"] if opt["spend"] is not None else "none",
                 "%.1f" % per["spend"] if per["spend"] is not None else "none",
                 alloc))
    with open(out / "north_cove_frontier.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(frontier[0].keys()))
        w.writeheader()
        w.writerows(frontier)
    print("outputs written to %s/north_cove_*.csv" % out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results")
