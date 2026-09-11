import random

from src.calibrated import (
    calibrated_network,
    disconnecting_pairs,
    is_calibrated,
    scale_capacity,
    tightest_feasible_factor,
)
from src.model import solve
from src.network import base_network
from src.scenarios import single_node_failures


def test_the_hand_built_instance_satisfies_the_invariant():
    assert is_calibrated(base_network())


def test_an_over_provisioned_network_fails_the_invariant():
    net = scale_capacity(base_network(), 10)
    assert solve(net)["satisfaction"] == 1.0
    assert not is_calibrated(net), "no single failure should hurt at ten times capacity"


def test_a_starved_network_fails_the_invariant():
    net = scale_capacity(base_network(), 0.2)
    assert solve(net)["satisfaction"] < 1.0
    assert not is_calibrated(net), "the intact network must serve everyone"


def test_tightest_factor_is_feasible_and_nearly_binding():
    net = base_network()
    factor = tightest_feasible_factor(net)
    assert factor is not None
    assert solve(scale_capacity(net, factor))["satisfaction"] == 1.0
    assert solve(scale_capacity(net, factor * 0.9))["satisfaction"] < 1.0


def test_tightest_factor_reports_an_infeasible_network_rather_than_looping():
    net = scale_capacity(base_network(), 0.1)
    assert tightest_feasible_factor(net) is None


def test_disconnecting_pairs_finds_the_known_cut_on_the_base_instance():
    net = base_network()
    cuts = disconnecting_pairs(net)
    assert len(cuts) == 3
    worst = cuts[0]
    assert set(worst["pair"]) == {"W1", "W2"}
    assert worst["lost"] == 110
    assert abs(worst["ceiling"] - (1 - 110 / 180)) < 1e-12
    assert all(set(cut["pair"]) <= set(net["warehouses"]) for cut in cuts)


def test_the_structural_ceiling_matches_what_the_program_delivers():
    """The reachability argument and the linear program have to agree."""
    net = base_network()
    worst = disconnecting_pairs(net)[0]
    generous = scale_capacity(net, 100)
    for node in worst["pair"]:
        generous["capacity"][node] = 0
    assert abs(solve(generous)["satisfaction"] - worst["ceiling"]) < 1e-9


def test_disconnecting_pairs_is_empty_when_every_hospital_has_a_third_route():
    net = base_network()
    for warehouse in net["warehouses"]:
        for hospital in net["hospitals"]:
            net["arc_cost"].setdefault((warehouse, hospital), 1)
    assert disconnecting_pairs(net) == []


def test_a_partial_third_route_still_leaves_the_pairs_it_does_not_cover():
    """Giving W3 a route to H1 and H2 removes the W1+W2 cut and no other."""
    net = base_network()
    net["arc_cost"][("W3", "H1")] = 1
    net["arc_cost"][("W3", "H2")] = 1
    remaining = {frozenset(cut["pair"]) for cut in disconnecting_pairs(net)}
    assert remaining == {frozenset({"W2", "W3"}), frozenset({"W1", "W3"})}


def test_generated_networks_satisfy_the_invariant_they_are_generated_for():
    rng = random.Random(7)
    net = calibrated_network(rng)
    assert net is not None
    assert is_calibrated(net)
    assert 0.02 <= net["slack"] <= 0.50
    assert len(single_node_failures(net)) == len(
        net["suppliers"] + net["factories"] + net["warehouses"]
    )


def test_generation_is_reproducible_from_the_seed():
    left = calibrated_network(random.Random(7))
    right = calibrated_network(random.Random(7))
    assert left is not None
    assert left["capacity"] == right["capacity"]
    assert left["demand"] == right["demand"]
    assert left["arc_cost"] == right["arc_cost"]
