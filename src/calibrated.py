from copy import deepcopy
from math import ceil

from src.generator import random_layered_network
from src.model import solve
from src.scenarios import single_node_failures

FULL = 1 - 1e-9


def scale_capacity(network, factor):
    scaled = deepcopy(network)
    for node in scaled["capacity"]:
        scaled["capacity"][node] = ceil(network["capacity"][node] * factor)
    return scaled


def tightest_feasible_factor(network, tolerance=1e-3):
    """Smallest capacity scaling at which the intact network still meets all
    demand. Random layered networks are over-provisioned, so the invariant is
    reached by shrinking capacity rather than by resampling."""
    if solve(network)["satisfaction"] < FULL:
        return None
    low, high = 0.0, 1.0
    while high - low > tolerance:
        mid = (low + high) / 2
        if solve(scale_capacity(network, mid))["satisfaction"] >= FULL:
            high = mid
        else:
            low = mid
    return high


def is_calibrated(network):
    """The invariant the hand-built instance satisfies: every hospital is served
    when the network is intact, and no single facility can be lost without a
    shortage."""
    if solve(network)["satisfaction"] < FULL:
        return False
    for nodes in single_node_failures(network):
        failed = deepcopy(network)
        for node in nodes:
            failed["capacity"][node] = 0
        if solve(failed)["satisfaction"] >= FULL:
            return False
    return True


def calibrated_network(rng, slack_range=(0.02, 0.50), attempts=40, sizes=None):
    """A random layered network tightened until it satisfies the calibration
    invariant. Slack above the tightest feasible capacity is drawn per attempt,
    so the sample spans the family rather than only its tightest members.
    Returns None if no draw within `attempts` can be tightened."""
    for _ in range(attempts):
        base = random_layered_network(rng, sizes)
        factor = tightest_feasible_factor(base)
        if factor is None:
            continue
        slack = rng.uniform(*slack_range)
        candidate = scale_capacity(base, factor * (1 + slack))
        if is_calibrated(candidate):
            candidate["slack"] = slack
            return candidate
    return None


def _reachable_hospitals(network, removed):
    """Hospitals with at least one supplier-to-hospital path avoiding `removed`."""
    alive = set(
        network["suppliers"] + network["factories"]
        + network["warehouses"] + network["hospitals"]
    )
    alive -= set(removed)
    frontier = [s for s in network["suppliers"] if s in alive]
    seen = set(frontier)
    while frontier:
        node = frontier.pop()
        for (i, j) in network["arc_cost"]:
            if i == node and j in alive and j not in seen:
                seen.add(j)
                frontier.append(j)
    return seen & set(network["hospitals"])


def disconnecting_pairs(network):
    """Pairs whose removal severs some hospital from every supplier. Such a
    hospital cannot be served at any capacity, so its demand is a floor on
    worst-case shortfall that no protection budget can lift."""
    from itertools import combinations

    nodes = network["suppliers"] + network["factories"] + network["warehouses"]
    total = sum(network["demand"].values())
    found = []
    for pair in combinations(nodes, 2):
        served = _reachable_hospitals(network, pair)
        cut = [h for h in network["hospitals"] if h not in served]
        if cut:
            lost = sum(network["demand"][h] for h in cut)
            found.append({"pair": pair, "lost": lost, "ceiling": 1 - lost / total})
    return sorted(found, key=lambda row: row["ceiling"])
