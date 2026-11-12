import random

from src.families import bootstrap_interval, raw_network, tightened_network
from src.model import solve

FULL = 1 - 1e-9


def test_a_tightened_network_serves_everyone_when_intact():
    net = tightened_network(random.Random(1))
    assert net is not None
    assert solve(net)["satisfaction"] >= FULL


def test_a_tightened_network_takes_the_shape_asked_for():
    net = tightened_network(random.Random(2), sizes=(2, 3, 5, 5), min_in_degree=2)
    assert [len(net[k]) for k in ("suppliers", "factories", "warehouses", "hospitals")] \
        == [2, 3, 5, 5]


def test_tightening_does_not_demand_that_every_failure_hurts():
    """The calibrated generator rejects networks that can lose a facility
    without a shortage. This one keeps them, which is the point of it."""
    from src.calibrated import is_calibrated

    rng = random.Random(3)
    nets = [tightened_network(rng) for _ in range(12)]
    assert any(not is_calibrated(n) for n in nets if n is not None)


def test_tightened_networks_repeat_under_the_same_seed():
    a = tightened_network(random.Random(4), sizes=(3, 3, 6, 4), min_in_degree=2)
    b = tightened_network(random.Random(4), sizes=(3, 3, 6, 4), min_in_degree=2)
    assert a == b


def test_a_raw_network_serves_everyone_and_keeps_generator_capacities():
    net = raw_network(random.Random(5))
    assert solve(net)["satisfaction"] >= FULL
    assert all(20 <= c <= 100 for c in net["capacity"].values())


def test_bootstrap_interval_brackets_the_pooled_rate():
    """Three networks with 1 of 4, 2 of 4 and 3 of 4 events pool to one half."""
    clusters = [(1, 4), (2, 4), (3, 4)]
    low, high = bootstrap_interval(clusters, random.Random(6), resamples=500)
    assert low <= 0.5 <= high
    assert 0.25 <= low and high <= 0.75


def test_bootstrap_interval_collapses_when_every_network_agrees():
    low, high = bootstrap_interval([(1, 2), (2, 4), (3, 6)], random.Random(7), resamples=200)
    assert low == high == 0.5


def test_bootstrap_resamples_networks_and_not_states():
    """One network with a single state and no event, one with a hundred states
    that all have the event. Resampling the 101 states would keep the rate near
    0.99. Resampling the two networks draws the small one twice a quarter of
    the time, so the interval has to run from 0 to 1."""
    low, high = bootstrap_interval([(0, 1), (100, 100)], random.Random(8), resamples=400)
    assert low == 0.0
    assert high == 1.0
