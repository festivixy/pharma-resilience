"""The equitable routing, pinned to networks small enough to check by hand."""

import random

import pytest

from src.experiment import fail_nodes
from src.fairness import fair_equity, fair_shipping_cost, generic_costs
from src.model import solve
from src.network import base_network, equity_paradox_network
from src.robust import apply_allocation
from src.scenarios import single_node_failures


def _shared_bottleneck():
    """Ten units through one chain, two hospitals wanting ten each. H1 is one
    unit cheaper to reach, so the cost-minimising routing gives it everything."""
    return {
        "suppliers": ["S"],
        "factories": ["F"],
        "warehouses": ["W"],
        "hospitals": ["H1", "H2"],
        "capacity": {"S": 10, "F": 10, "W": 10},
        "demand": {"H1": 10, "H2": 10},
        "arc_cost": {("S", "F"): 1, ("F", "W"): 1, ("W", "H1"): 1, ("W", "H2"): 2},
        "penalty": 1000,
        "protection_cost_rate": 1.0,
    }


def test_cost_minimisation_strands_the_dearer_hospital_and_fairness_halves_it():
    net = _shared_bottleneck()
    assert solve(net)["min_fill_rate"] == pytest.approx(0.0)
    assert fair_equity(net) == pytest.approx(0.5, abs=1e-6)


def test_fair_routing_costs_what_the_arithmetic_says():
    """Ten units to H1 cost 10 * 3 = 30. Five each cost 5 * 3 + 5 * 4 = 35."""
    net = _shared_bottleneck()
    assert solve(net)["shipping_cost"] == pytest.approx(30.0)
    assert fair_shipping_cost(net, 0.5) == pytest.approx(35.0, abs=1e-4)


def test_a_floor_of_zero_costs_nothing_extra():
    net = _shared_bottleneck()
    assert fair_shipping_cost(net, 0.0) == pytest.approx(30.0, abs=1e-4)


def test_an_unreachable_floor_has_no_routing():
    assert fair_shipping_cost(_shared_bottleneck(), 0.9) is None


def test_fair_equity_is_never_below_what_the_solver_reports():
    net = base_network()
    for failed in single_node_failures(net):
        state = fail_nodes(net, failed)
        assert fair_equity(state) >= solve(state)["min_fill_rate"] - 1e-6


def test_fairness_never_costs_delivery():
    """Megiddo (1974): some maximum flow is also max-min fair. Dropping the
    requirement to deliver the maximum total must not raise the fair value."""
    net = base_network()
    for failed in single_node_failures(net):
        state = fail_nodes(net, failed)
        assert fair_equity(state, hold_delivery=False) == pytest.approx(
            fair_equity(state), abs=1e-6)


def test_paradox_instance_fair_equity_rises_where_reported_equity_falls():
    net = equity_paradox_network()
    protected = apply_allocation(net, {"S": 1, "F": 1, "W1": 7})
    assert solve(net)["min_fill_rate"] == pytest.approx(0.4)
    assert solve(protected)["min_fill_rate"] == pytest.approx(0.1)
    assert fair_equity(net) == pytest.approx(0.4, abs=1e-6)
    assert fair_equity(protected) == pytest.approx(0.55, abs=1e-6)


def test_generic_costs_stay_in_band_and_leave_the_network_alone():
    net = base_network()
    before = dict(net["arc_cost"])
    out = generic_costs(net, random.Random(1), band=0.2)
    assert net["arc_cost"] == before
    for arc, cost in out["arc_cost"].items():
        assert 0.8 * before[arc] <= cost <= 1.2 * before[arc]
    assert out["arc_cost"] != before


def test_generic_costs_repeat_under_the_same_seed():
    net = base_network()
    assert generic_costs(net, random.Random(5))["arc_cost"] == \
        generic_costs(net, random.Random(5))["arc_cost"]
