import random
from copy import deepcopy

from src.experiment import apply_protection, fail_nodes
from src.generator import random_layered_network
from src.model import solve
from src.scenarios import single_node_failures

SATURATED = 1 - 1e-9


def scale_demands(network, factor):
    scaled = deepcopy(network)
    for h in scaled["demand"]:
        scaled["demand"][h] = network["demand"][h] * factor
    return scaled


def damage_curves(network, levels, scenarios):
    curves = {nodes: [] for nodes in scenarios}
    for level in levels:
        protected = apply_protection(network, level)
        for nodes in scenarios:
            curves[nodes].append(solve(fail_nodes(protected, nodes))["satisfaction"])
    return curves


def _ranking(curves, index):
    return tuple(
        sorted(curves, key=lambda nodes: (round(curves[nodes][index], 9), nodes))
    )


def count_reorderings(curves):
    length = len(next(iter(curves.values())))
    rankings = [_ranking(curves, i) for i in range(length)]
    return sum(1 for prev, cur in zip(rankings, rankings[1:]) if prev != cur)


def protectability(sats, levels, total_demand):
    values = []
    for i in range(len(levels) - 1):
        d1, d2 = sats[i] * total_demand, sats[i + 1] * total_demand
        if sats[i] >= SATURATED and sats[i + 1] >= SATURATED:
            continue
        if d1 <= 1e-9 and d2 <= 1e-9:
            continue
        slope = (d2 - d1) / (levels[i + 1] - levels[i])
        intercept = d1 - slope * (1 + levels[i])
        cut_value = slope + intercept
        if cut_value <= 1e-9:
            continue
        values.append(slope / cut_value)
    return values


def spearman(xs, ys):
    def average_ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            rank = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[order[k]] = rank
            i = j + 1
        return ranks

    rx, ry = average_ranks(xs), average_ranks(ys)
    n = len(rx)
    mean = (n + 1) / 2
    cov = sum((a - mean) * (b - mean) for a, b in zip(rx, ry))
    var_x = sum((a - mean) ** 2 for a in rx)
    var_y = sum((b - mean) ** 2 for b in ry)
    if var_x <= 0 or var_y <= 0:
        return None
    return cov / (var_x * var_y) ** 0.5


def run_instability_experiment(count, seed, levels):
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        network = random_layered_network(rng)
        scenarios = single_node_failures(network)
        total_demand = sum(network["demand"].values())
        curves = damage_curves(network, levels, scenarios)
        pis = [
            pi
            for sats in curves.values()
            for pi in protectability(sats, levels, total_demand)
        ]
        beta_zero = scale_demands(network, 100)
        beta_curves = damage_curves(beta_zero, levels, scenarios)
        reorderings = count_reorderings(curves)
        distinct_pi = len({round(pi, 2) for pi in pis})
        rows.append({
            "index": index,
            "scenarios": len(scenarios),
            "reorderings": reorderings,
            "pi_spread": max(pis) - min(pis) if pis else 0.0,
            "distinct_pi": distinct_pi,
            "bound_holds": reorderings <= distinct_pi,
            "beta_zero_reorderings": count_reorderings(beta_curves),
        })
    return {
        "rows": rows,
        "spearman_spread_vs_reorderings": spearman(
            [row["pi_spread"] for row in rows],
            [row["reorderings"] for row in rows],
        ),
        "bound_fraction": sum(row["bound_holds"] for row in rows) / count,
        "beta_zero_invariant_fraction": sum(
            row["beta_zero_reorderings"] == 0 for row in rows
        ) / count,
    }
