import pytest

from src.baselines import (
    equal_allocation,
    greedy_allocation,
    proportional_allocation,
    worst_case_satisfaction,
)
from src.experiment import apply_protection, protection_spend
from src.network import base_network
from src.robust import _protectable
from src.scenarios import single_node_failures


def test_equal_allocation_spends_the_whole_budget():
    net = base_network()
    extra = equal_allocation(net, 90.0)
    assert sum(extra.values()) == pytest.approx(90.0)


def test_equal_allocation_gives_every_facility_the_same_amount():
    net = base_network()
    extra = equal_allocation(net, 90.0)
    assert len(set(extra.values())) == 1


def test_proportional_allocation_spends_the_whole_budget():
    net = base_network()
    extra = proportional_allocation(net, 90.0)
    assert sum(extra.values()) == pytest.approx(90.0)


def test_proportional_allocation_reproduces_the_uniform_sweep():
    """The claim the module docstring rests on. Raising every capacity by 10%
    is the same thing as splitting that spend in proportion to capacity."""
    net = base_network()
    level = 0.1
    extra = proportional_allocation(net, protection_spend(net, level))
    uniform = apply_protection(net, level)
    for node in _protectable(net):
        assert net["capacity"][node] + extra[node] == pytest.approx(
            uniform["capacity"][node])


def test_greedy_spends_the_whole_budget():
    net = base_network()
    extra = greedy_allocation(net, 40.0, single_node_failures(net), steps=4)
    assert sum(extra.values()) == pytest.approx(40.0)


def test_greedy_beats_an_equal_split_on_the_benchmark():
    """If the greedy rule were no better than splitting evenly there would be
    nothing to compare against the solver."""
    net = base_network()
    scenarios = single_node_failures(net)
    budget = 40.0
    greedy = worst_case_satisfaction(net, greedy_allocation(net, budget, scenarios, steps=8), scenarios)
    equal = worst_case_satisfaction(net, equal_allocation(net, budget), scenarios)
    assert greedy >= equal


def test_a_zero_budget_changes_nothing():
    net = base_network()
    scenarios = single_node_failures(net)
    nothing = {n: 0.0 for n in _protectable(net)}
    assert worst_case_satisfaction(net, equal_allocation(net, 0.0), scenarios) == \
        pytest.approx(worst_case_satisfaction(net, nothing, scenarios))


def test_protection_does_not_rescue_the_facility_that_fails():
    """Extra capacity at a failed node dies with it, so spending the budget on
    the node that fails buys nothing in that scenario."""
    net = base_network()
    victim = net["warehouses"][0]
    scenario = [(victim,)]
    nothing = {n: 0.0 for n in _protectable(net)}
    on_the_victim = dict(nothing, **{victim: 500.0})
    assert worst_case_satisfaction(net, on_the_victim, scenario) == \
        pytest.approx(worst_case_satisfaction(net, nothing, scenario))
