"""The routing that serves the worst-off hospital as well as the network allows.

src/model.py returns the cheapest routing among those that deliver the most.
Nothing in that objective looks at who goes short. The functions here ask what
the same network could have done for its worst-served hospital, and what that
routing costs to ship, so the two can be compared state by state.
"""

import random

import pulp

from src.model import solve


def _flow_program(network: dict, sense: int):
    """The constraints of src/model.py with no objective attached."""
    arcs = network["arc_cost"]
    hospitals = network["hospitals"]
    demand = network["demand"]

    prob = pulp.LpProblem("fair_flow", sense)
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
    return prob, unmet, shipping


def _hold_delivery(prob, unmet, network: dict, tolerance: float) -> None:
    """Keep total unmet demand at the least the network can achieve. CBC
    reports that least to about six decimal places, so the tolerance has to
    sit above that or a feasible routing can be ruled out."""
    least_unmet = sum(solve(network)["unmet"].values())
    prob += pulp.lpSum(unmet.values()) <= least_unmet + tolerance


def fair_equity(network: dict, hold_delivery: bool = True,
                tolerance: float = 1e-5) -> float:
    """The largest worst-hospital fill rate any routing can reach.

    With `hold_delivery` the routing must also deliver the maximum total.
    Megiddo (1974) shows that requirement is free, and a test checks it."""
    prob, unmet, _ = _flow_program(network, pulp.LpMaximize)
    floor = pulp.LpVariable("floor", lowBound=0, upBound=1)
    prob += floor
    for h in network["hospitals"]:
        prob += unmet[h] <= (1 - floor) * network["demand"][h]
    if hold_delivery:
        _hold_delivery(prob, unmet, network, tolerance)
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    return floor.value()


def fair_shipping_cost(network: dict, floor: float,
                       tolerance: float = 1e-5) -> float | None:
    """The cheapest shipping among routings that deliver the maximum total and
    give every hospital at least `floor` of its demand. None when no routing
    does both."""
    prob, unmet, shipping = _flow_program(network, pulp.LpMinimize)
    prob += shipping
    for h in network["hospitals"]:
        prob += unmet[h] <= (1 - floor) * network["demand"][h] + tolerance
    _hold_delivery(prob, unmet, network, tolerance)
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    if pulp.LpStatus[prob.status] != "Optimal":
        return None
    return pulp.value(shipping)


def generic_costs(network: dict, rng: random.Random, band: float = 0.2) -> dict:
    """A copy of the network with every arc cost scaled by its own draw from
    [1 - band, 1 + band]. Integer costs tie often; these do not, so the
    cost-minimising routing is a single routing rather than a set."""
    out = dict(network)
    out["arc_cost"] = {arc: cost * rng.uniform(1 - band, 1 + band)
                       for arc, cost in network["arc_cost"].items()}
    return out
