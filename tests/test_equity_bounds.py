"""The equity range must be read off flows, not off an auxiliary variable.

A reviewer caught the first version returning zero as the lower bound in every
scenario. Minimising q subject to q <= fill_h lets the solver set q = 0 without
moving any flow. These tests pin the corrected bounds to arithmetic a reader
can check by hand.
"""

import pulp
import pytest

from run_equity import equity_at_optimal_cost
from src.experiment import fail_nodes
from src.model import solve
from src.network import base_network


def _bounds(scenario):
    state = fail_nodes(base_network(), [scenario])
    return (equity_at_optimal_cost(state, pulp.LpMinimize),
            equity_at_optimal_cost(state, pulp.LpMaximize))


def test_lower_bound_respects_total_unmet_demand():
    """Under F3 only 10 units go unmet and the smallest hospital wants 30, so
    no cost-optimal routing can leave any hospital below two thirds."""
    state = fail_nodes(base_network(), ["F3"])
    unmet = sum(solve(state)["unmet"].values())
    assert unmet == pytest.approx(10.0)
    low, _ = _bounds("F3")
    assert low == pytest.approx(2 / 3, abs=1e-6)


def test_only_s3_can_strand_a_hospital():
    zero = [sc for sc in ["S1", "S2", "S3", "F1", "F2", "F3", "W1", "W2", "W3"]
            if _bounds(sc)[0] < 1e-6]
    assert zero == ["S3"]


def test_lower_bound_never_exceeds_upper_bound():
    for sc in ["S1", "S3", "F1", "F3", "W3"]:
        low, high = _bounds(sc)
        assert low <= high + 1e-9


def test_determined_scenarios_have_no_range():
    for sc in ["S2", "F2", "W1", "W2"]:
        low, high = _bounds(sc)
        assert low == pytest.approx(high, abs=1e-6)


def test_near_ties_only_widen_the_range():
    """Allowing routings that cost a little more in shipping, at the same
    delivery, can only move the ends of the range outward."""
    for sc in ["S1", "S3", "F3"]:
        state = fail_nodes(base_network(), [sc])
        low, high = _bounds(sc)
        near_low = equity_at_optimal_cost(state, pulp.LpMinimize, shipping_slack=0.05)
        near_high = equity_at_optimal_cost(state, pulp.LpMaximize, shipping_slack=0.05)
        assert near_low <= low + 1e-6
        assert near_high >= high - 1e-6


def test_shipping_slack_actually_reaches_the_program():
    """The first version accepted the slack argument and dropped it, so the
    near-tie rows came out identical to the exact ones. S2 is a point under
    exact ties and must open up under five percent slack."""
    state = fail_nodes(base_network(), ["S2"])
    low, high = _bounds("S2")
    assert low == pytest.approx(high, abs=1e-6)
    near_low = equity_at_optimal_cost(state, pulp.LpMinimize, shipping_slack=0.05)
    near_high = equity_at_optimal_cost(state, pulp.LpMaximize, shipping_slack=0.05)
    assert near_low < low - 0.05
    assert near_high > high + 0.05


def test_zero_slack_is_the_exact_range():
    state = fail_nodes(base_network(), ["S3"])
    assert equity_at_optimal_cost(state, pulp.LpMinimize, shipping_slack=0.0) == \
        pytest.approx(equity_at_optimal_cost(state, pulp.LpMinimize), abs=1e-6)


def test_every_bound_is_at_least_the_aggregate_floor():
    """fill_h >= max(0, 1 - U / d_h) for every hospital, so the smallest fill
    rate is at least that floor taken at the smallest demand."""
    net = base_network()
    for sc in ["S1", "S2", "S3", "F1", "F2", "F3", "W1", "W2", "W3"]:
        state = fail_nodes(net, [sc])
        unmet = sum(solve(state)["unmet"].values())
        floor = max(0.0, 1 - unmet / min(net["demand"].values()))
        low, _ = _bounds(sc)
        assert low >= floor - 1e-6
