from copy import deepcopy

import pulp

from src.experiment import fail_nodes
from src.model import solve


def _protectable(network):
    return network["suppliers"] + network["factories"] + network["warehouses"]


def apply_allocation(network, extra):
    protected = deepcopy(network)
    for node, amount in extra.items():
        protected["capacity"][node] = network["capacity"][node] + amount
    return protected


def min_spend_plan(network, scenarios, target, integer=False, per_hospital=False):
    nodes = _protectable(network)
    arcs = network["arc_cost"]
    hospitals = network["hospitals"]
    demand = network["demand"]
    total_demand = sum(demand.values())
    category = "Integer" if integer else "Continuous"

    prob = pulp.LpProblem("min_protection_spend", pulp.LpMinimize)
    extra = {n: pulp.LpVariable(f"e_{n}", lowBound=0, cat=category) for n in nodes}
    prob += network["protection_cost_rate"] * pulp.lpSum(extra.values())

    for i, failed in enumerate(scenarios):
        flow = {a: pulp.LpVariable(f"x{i}_{a[0]}_{a[1]}", lowBound=0) for a in arcs}
        unmet = {h: pulp.LpVariable(f"u{i}_{h}", lowBound=0) for h in hospitals}

        def inflow(node):
            return pulp.lpSum(flow[a] for a in arcs if a[1] == node)

        def outflow(node):
            return pulp.lpSum(flow[a] for a in arcs if a[0] == node)

        for s in network["suppliers"]:
            if s in failed:
                prob += outflow(s) <= 0
            else:
                prob += outflow(s) <= network["capacity"][s] + extra[s]
        for n in network["factories"] + network["warehouses"]:
            prob += inflow(n) == outflow(n)
            if n in failed:
                prob += inflow(n) <= 0
            else:
                prob += inflow(n) <= network["capacity"][n] + extra[n]
        for h in hospitals:
            prob += inflow(h) + unmet[h] == demand[h]
        if per_hospital:
            # every hospital must reach the target on its own demand, which is
            # what an aggregate bound does not enforce
            for h in hospitals:
                prob += unmet[h] <= (1 - target) * demand[h]
        else:
            prob += pulp.lpSum(unmet.values()) <= (1 - target) * total_demand

    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    status = pulp.LpStatus[prob.status]
    if status != "Optimal":
        return {"status": status, "spend": None, "extra": None}

    extra_values = {n: extra[n].value() for n in nodes}
    return {
        "status": status,
        "spend": network["protection_cost_rate"] * sum(extra_values.values()),
        "extra": extra_values,
    }


def ccg_plan(network, scenarios, target):
    chosen = []
    extra = {n: 0.0 for n in _protectable(network)}
    iterations = 0
    while True:
        iterations += 1
        protected = apply_allocation(network, extra)
        worst_value, worst_nodes = min(
            (
                (solve(fail_nodes(protected, nodes))["satisfaction"], nodes)
                for nodes in scenarios
            ),
            key=lambda pair: pair[0],
        )
        if worst_value >= target - 1e-6:
            spend = network["protection_cost_rate"] * sum(extra.values())
            return {
                "status": "Optimal",
                "spend": spend,
                "extra": extra,
                "iterations": iterations,
            }
        chosen.append(worst_nodes)
        plan = min_spend_plan(network, chosen, target)
        if plan["status"] != "Optimal":
            return {
                "status": plan["status"],
                "spend": None,
                "extra": None,
                "iterations": iterations,
            }
        extra = plan["extra"]
