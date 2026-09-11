"""What does guaranteeing every hospital cost, and is the reported equity real?

Two questions the aggregate formulation raises.

First, the resilience target bounds total unmet demand and says nothing about
its distribution. Replacing it with a per-hospital bound closes that hole. This
measures the extra investment that costs.

Second, the equity we report comes from whichever optimal routing the solver
returned. If several routings tie on cost but differ on the worst-served
hospital, the reported figure is a solver artifact rather than a property of
the plan. This re-solves each scenario maximising the worst fill rate subject
to keeping the optimal cost, which gives the best equity any optimal routing
can reach.

    python run_equity.py
"""

import csv
import sys
from pathlib import Path

import pulp

from src.experiment import fail_nodes
from src.model import solve
from src.network import base_network
from src.robust import min_spend_plan
from src.scenarios import single_node_failures

TARGETS = [0.75, 0.80, 0.85, 0.90, 0.95, 1.00]


def _cost_optimal_program(network, tolerance, shipping_slack=0.0):
    """A flow program constrained to cost no more than the optimum, with no
    objective yet. Callers attach one.

    With `shipping_slack` > 0 the program instead holds total delivery at its
    optimum and lets shipping cost exceed its optimum by that fraction, which
    admits routings that are nearly, rather than exactly, cost-optimal."""
    base = solve(network)
    arcs = network["arc_cost"]
    hospitals = network["hospitals"]
    demand = network["demand"]

    prob = pulp.LpProblem("bound_fill", pulp.LpMinimize)
    flow = {a: pulp.LpVariable(f"x_{a[0]}_{a[1]}", lowBound=0) for a in arcs}
    unmet = {h: pulp.LpVariable(f"u_{h}", lowBound=0, upBound=demand[h])
             for h in hospitals}

    def inflow(node):
        return pulp.lpSum(flow[a] for a in arcs if a[1] == node)

    def outflow(node):
        return pulp.lpSum(flow[a] for a in arcs if a[0] == node)

    for s in network["suppliers"]:
        prob += outflow(s) <= network["capacity"][s]
    for n in network["factories"] + network["warehouses"]:
        prob += inflow(n) == outflow(n)
        prob += inflow(n) <= network["capacity"][n]
    for h in hospitals:
        prob += inflow(h) + unmet[h] == demand[h]

    shipping = pulp.lpSum(cost * flow[a] for a, cost in arcs.items())
    if shipping_slack > 0:
        prob += pulp.lpSum(unmet.values()) <= sum(base["unmet"].values()) + tolerance
        prob += shipping <= (1 + shipping_slack) * base["shipping_cost"] + tolerance
    else:
        prob += shipping + network["penalty"] * pulp.lpSum(unmet.values()) \
            <= base["cost"] + tolerance
    return prob, unmet


def equity_at_optimal_cost(network, sense, tolerance=1e-6, shipping_slack=0.0):
    """The worst-hospital fill rate at the best (LpMaximize) or worst
    (LpMinimize) end of the cost-optimal routings. With `shipping_slack` the
    set widens to routings within that fraction of the optimal shipping cost
    at optimal delivery.

    The two directions need different programs. The best end is a max-min:
    raise an auxiliary q subject to q <= fill_h for every h. The worst end is
    not the same program minimised. Minimising that q lets the solver set
    q = 0 without moving a unit of flow, which is the bug the first version of
    this function had and which put a zero in every lower bound. Instead,
    minimise each hospital's own fill rate in turn and take the smallest. Every
    value returned here is read off the flows, never off an auxiliary."""
    hospitals = network["hospitals"]
    demand = network["demand"]

    if sense == pulp.LpMaximize:
        prob, unmet = _cost_optimal_program(network, tolerance, shipping_slack)
        worst = pulp.LpVariable("worst", lowBound=0, upBound=1)
        prob.sense = pulp.LpMaximize
        prob.setObjective(worst)
        for h in hospitals:
            prob += worst <= 1 - unmet[h] / demand[h]
        prob.solve(pulp.PULP_CBC_CMD(msg=0))
        if pulp.LpStatus[prob.status] != "Optimal":
            return None
        return min(1 - unmet[h].value() / demand[h] for h in hospitals)

    lowest = None
    for target in hospitals:
        prob, unmet = _cost_optimal_program(network, tolerance, shipping_slack)
        prob.setObjective(-unmet[target])      # push this hospital's fill down
        prob.solve(pulp.PULP_CBC_CMD(msg=0))
        if pulp.LpStatus[prob.status] != "Optimal":
            return None
        fill = 1 - unmet[target].value() / demand[target]
        lowest = fill if lowest is None else min(lowest, fill)
    return lowest


def main(out_dir="results"):
    net = base_network()
    scenarios = single_node_failures(net)

    print("what a per-hospital guarantee costs, on the benchmark instance")
    print("  %-8s %12s %14s %10s" % ("target", "aggregate", "per-hospital", "extra"))
    cost_rows = []
    for t in TARGETS:
        agg = min_spend_plan(net, scenarios, t)
        per = min_spend_plan(net, scenarios, t, per_hospital=True)
        if agg["status"] != "Optimal" or per["status"] != "Optimal":
            continue
        extra = per["spend"] - agg["spend"]
        cost_rows.append({"target": t, "aggregate": agg["spend"],
                          "per_hospital": per["spend"], "extra": extra})
        print("  %-8.2f %12.1f %14.1f %10.1f" % (t, agg["spend"], per["spend"], extra))

    print()
    print("is the reported equity a property of the plan or of the solver?")
    print("  %-8s %10s %14s %s" % ("scenario", "reported", "best possible", "same?"))
    eq_rows = []
    for nodes in scenarios:
        damaged = fail_nodes(net, nodes)
        reported = solve(damaged)["min_fill_rate"]
        best = equity_at_optimal_cost(damaged, pulp.LpMaximize)
        worst = equity_at_optimal_cost(damaged, pulp.LpMinimize)
        same = best is not None and abs(best - worst) < 1e-6
        eq_rows.append({"scenario": "+".join(nodes), "reported": reported,
                        "worst_at_optimal_cost": worst,
                        "best_at_optimal_cost": best, "determined": same})
        print("  %-8s %10.4f %14.4f %14.4f %s"
              % ("+".join(nodes), reported, worst, best, "yes" if same else "NO"))

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "equity_cost.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(cost_rows[0].keys()))
        w.writeheader()
        w.writerows(cost_rows)
    with open(out / "equity_degeneracy.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(eq_rows[0].keys()))
        w.writeheader()
        w.writerows(eq_rows)
    print()
    print("outputs written to %s/" % out)


if __name__ == "__main__":
    main()
