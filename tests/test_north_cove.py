import pulp
import pytest

from run_equity import equity_at_optimal_cost
from src.experiment import fail_nodes
from src.model import solve
from src.north_cove import north_cove_network


def test_supply_equals_demand_because_the_market_had_no_slack():
    net = north_cove_network()
    plants = sum(net["capacity"][s] for s in net["suppliers"])
    assert plants == 100
    assert sum(net["demand"].values()) == 100


def test_the_intact_network_serves_everyone():
    assert solve(north_cove_network())["satisfaction"] == pytest.approx(1.0)


def test_losing_north_cove_leaves_forty_percent():
    """Baxter's first allocation to direct customers was 40%."""
    net = north_cove_network()
    assert solve(fail_nodes(net, ["NorthCove"]))["satisfaction"] == pytest.approx(0.40)


def test_cost_optimal_routings_span_zero_to_forty_percent_equity():
    """The observed 10% for distributor customers sits inside this range."""
    state = fail_nodes(north_cove_network(), ["NorthCove"])
    low = equity_at_optimal_cost(state, pulp.LpMinimize)
    high = equity_at_optimal_cost(state, pulp.LpMaximize)
    assert low == pytest.approx(0.0, abs=1e-6)
    assert high == pytest.approx(0.40, abs=1e-6)


def test_losing_north_cove_and_b_braun_leaves_seventeen_percent():
    net = north_cove_network()
    assert solve(fail_nodes(net, ["NorthCove", "BBraun"]))["satisfaction"] == \
        pytest.approx(0.17)


def test_three_tiers_and_no_factories():
    net = north_cove_network()
    assert net["factories"] == []
    assert len(net["suppliers"]) == 3
    assert len(net["warehouses"]) == 4
    assert len(net["hospitals"]) == 4


def test_other_channel_shares_and_headroom_replace_the_assumed_ones():
    channels = {"McKesson": 40, "Cencora": 25, "Cardinal": 25, "Direct": 10}
    net = north_cove_network(channels=channels, headroom=1.2)
    assert net["demand"] == {"H_McK": 40, "H_Cen": 25, "H_Car": 25, "H_Dir": 10}
    assert net["capacity"]["McKesson"] == pytest.approx(48.0)
    assert net["capacity"]["NorthCove"] == 60
    assert solve(net)["satisfaction"] == pytest.approx(1.0)


def test_the_default_network_is_unchanged_by_the_new_arguments():
    assert north_cove_network() == north_cove_network(
        channels={"McKesson": 33, "Cencora": 30, "Cardinal": 27, "Direct": 10}, headroom=1.5)


def test_the_fair_routing_exists_on_a_draw_where_solver_rounding_once_hid_it():
    """On this draw CBC reports total unmet demand about 1e-6 below its true
    value. Holding delivery to that figure with a tighter tolerance left the
    equitable routing infeasible, which it is not."""
    import random

    from run_north_cove_assumptions import SEED, draw_network
    from src.fairness import fair_equity, fair_shipping_cost

    net, _, _ = draw_network(random.Random(1000 * SEED + 74))
    state = fail_nodes(net, ["NorthCove"])
    fair = fair_equity(state)
    assert fair == pytest.approx(0.40, abs=1e-4)
    assert fair_shipping_cost(state, fair - 1e-7) is not None
