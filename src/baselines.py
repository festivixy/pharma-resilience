"""Ways of spending a protection budget without solving the robust program.

The sweep of src/experiment.py raises every capacity by the same fraction, so a
facility holding capacity c receives p*c extra units. That is already a
capacity-proportional rule, not an equal one, and it is the only comparison the
optimised plan has been measured against. These are the alternatives a planner
could reach for instead, so that the saving reported for the robust plan can be
split into what the allocation shape earns and what the solver adds.
"""

from src.experiment import fail_nodes
from src.model import solve
from src.robust import _protectable, apply_allocation


def worst_case_satisfaction(network, extra, scenarios):
    """Lowest satisfaction across `scenarios` once `extra` capacity is in place.
    Protection is applied before the failure, so a facility that fails carries
    its extra units down with it."""
    protected = apply_allocation(network, extra)
    return min(solve(fail_nodes(protected, failed))["satisfaction"]
               for failed in scenarios)


def _units(network, budget):
    return budget / network["protection_cost_rate"]


def equal_allocation(network, budget):
    """The same number of extra units at every facility."""
    nodes = _protectable(network)
    share = _units(network, budget) / len(nodes)
    return {n: share for n in nodes}


def proportional_allocation(network, budget):
    """Extra units in proportion to existing capacity. This reproduces the
    uniform sweep, and exists so the comparison can show that."""
    nodes = _protectable(network)
    total = sum(network["capacity"][n] for n in nodes)
    units = _units(network, budget)
    return {n: units * network["capacity"][n] / total for n in nodes}


def _score(network, extra, scenarios):
    """Worst-case satisfaction first, mean satisfaction second. One increment
    rarely moves the worst case on its own, and scoring on the worst case alone
    leaves every candidate tied, which sends the whole budget to whichever node
    happens to sort first. The mean breaks those ties by asking which facility
    is doing the most good across all the scenarios meanwhile."""
    protected = apply_allocation(network, extra)
    rates = [solve(fail_nodes(protected, failed))["satisfaction"]
             for failed in scenarios]
    return min(rates), sum(rates) / len(rates)


def greedy_allocation(network, budget, scenarios, steps=20):
    """The budget spent in `steps` equal increments, each one going to whichever
    facility scores best under `_score`. Remaining ties go to the node holding
    the least so far, so a flat objective spreads the money instead of piling it
    on one facility."""
    nodes = _protectable(network)
    increment = _units(network, budget) / steps
    extra = {n: 0.0 for n in nodes}

    for _ in range(steps):
        def rank(node):
            trial = dict(extra)
            trial[node] += increment
            worst, mean = _score(network, trial, scenarios)
            return (worst, mean, -extra[node])

        extra[max(nodes, key=rank)] += increment

    return extra
