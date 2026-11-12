import pytest

from src.experiment import fail_nodes
from src.model import solve
from src.network import base_network
from src.robust import apply_allocation, ccg_plan, min_spend_plan
from src.scenarios import pair_failures, single_node_failures


def worst_satisfaction(network, extra, scenarios):
    protected = apply_allocation(network, extra)
    return min(
        solve(fail_nodes(protected, nodes))["satisfaction"] for nodes in scenarios
    )


def test_apply_allocation_adds_extra_capacity_without_mutation():
    net = base_network()
    protected = apply_allocation(net, {"S1": 15})
    assert protected["capacity"]["S1"] == 95
    assert protected["capacity"]["S2"] == net["capacity"]["S2"]
    assert net["capacity"]["S1"] == 80


def test_target_below_unprotected_worst_case_costs_nothing():
    net = base_network()
    plan = min_spend_plan(net, single_node_failures(net), 0.7)
    assert plan["status"] == "Optimal"
    assert plan["spend"] == pytest.approx(0.0)


def test_full_protection_plan_survives_every_single_failure():
    net = base_network()
    scenarios = single_node_failures(net)
    plan = min_spend_plan(net, scenarios, 1.0)
    assert plan["status"] == "Optimal"
    assert plan["spend"] > 0
    assert worst_satisfaction(net, plan["extra"], scenarios) == pytest.approx(1.0)


def test_optimized_allocation_beats_uniform_protection():
    net = base_network()
    plan = min_spend_plan(net, single_node_failures(net), 1.0)
    uniform_spend_at_full_protection = 330.0
    assert plan["spend"] < uniform_spend_at_full_protection


def test_pair_target_above_topology_limit_is_infeasible():
    net = base_network()
    plan = min_spend_plan(net, pair_failures(net), 1.0)
    assert plan["status"] == "Infeasible"


def test_ccg_matches_exhaustive_lp_spend():
    net = base_network()
    scenarios = single_node_failures(net)
    for target in [0.9, 1.0]:
        full = min_spend_plan(net, scenarios, target)
        iterative = ccg_plan(net, scenarios, target)
        assert iterative["status"] == "Optimal"
        assert iterative["spend"] == pytest.approx(full["spend"], abs=1e-4)
        assert worst_satisfaction(net, iterative["extra"], scenarios) >= target - 1e-6


def test_ccg_converges_without_enumerating_all_scenarios():
    net = base_network()
    pairs = pair_failures(net)
    plan = ccg_plan(net, pairs, 0.35)
    assert plan["status"] == "Optimal"
    assert plan["iterations"] <= 5
    assert plan["iterations"] < len(pairs)


def test_unit_node_rates_reproduce_the_default_plan_spend():
    net = base_network()
    scenarios = single_node_failures(net)
    rates = {n: 1.0 for n in net["capacity"]}
    assert min_spend_plan(net, scenarios, 1.0, rates=rates)["spend"] == pytest.approx(
        min_spend_plan(net, scenarios, 1.0)["spend"])


def test_a_dearer_facility_is_avoided_when_a_cheaper_one_serves():
    """Two suppliers feed one chain and hold four units against a demand of
    five. Either can take the missing unit, so the cheaper one should."""
    net = {
        "suppliers": ["S1", "S2"], "factories": ["F"], "warehouses": ["W"],
        "hospitals": ["H"],
        "capacity": {"S1": 2, "S2": 2, "F": 20, "W": 20},
        "demand": {"H": 5},
        "arc_cost": {("S1", "F"): 1, ("S2", "F"): 1, ("F", "W"): 1, ("W", "H"): 1},
        "penalty": 1000, "protection_cost_rate": 1.0,
    }
    intact = [()]
    plan = min_spend_plan(net, intact, 1.0,
                          rates={"S1": 2.0, "S2": 1.0, "F": 1.0, "W": 1.0})
    assert plan["extra"]["S2"] == pytest.approx(1.0)
    assert plan["extra"]["S1"] == pytest.approx(0.0)
    assert plan["spend"] == pytest.approx(1.0)
