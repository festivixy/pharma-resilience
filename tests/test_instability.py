import pytest

from src.instability import (
    count_reorderings,
    damage_curves,
    protectability,
    run_instability_experiment,
    scale_demands,
    spearman,
)
from src.network import base_network
from src.scenarios import single_node_failures

LEVELS = [round(i * 0.05, 2) for i in range(11)]


def test_base_network_shows_the_known_ranking_switch():
    net = base_network()
    curves = damage_curves(net, LEVELS, single_node_failures(net))
    assert count_reorderings(curves) >= 1


def test_beta_zero_instance_has_invariant_ranking():
    net = scale_demands(base_network(), 100)
    curves = damage_curves(net, LEVELS, single_node_failures(net))
    assert count_reorderings(curves) == 0


def test_beta_zero_instance_has_protectability_one():
    net = scale_demands(base_network(), 100)
    total_demand = sum(net["demand"].values())
    curves = damage_curves(net, LEVELS, single_node_failures(net))
    for sats in curves.values():
        for pi in protectability(sats, LEVELS, total_demand):
            assert pi == pytest.approx(1.0, abs=1e-6)


def test_protectability_stays_in_unit_interval():
    net = base_network()
    total_demand = sum(net["demand"].values())
    curves = damage_curves(net, LEVELS, single_node_failures(net))
    for sats in curves.values():
        for pi in protectability(sats, LEVELS, total_demand):
            assert -1e-9 <= pi <= 1 + 1e-9


def test_spearman_on_monotone_data_is_one():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)


def test_experiment_is_deterministic_and_well_formed():
    a = run_instability_experiment(count=2, seed=9, levels=LEVELS)
    b = run_instability_experiment(count=2, seed=9, levels=LEVELS)
    assert a == b
    assert len(a["rows"]) == 2
    for row in a["rows"]:
        assert row["reorderings"] >= 0
        assert row["beta_zero_reorderings"] == 0
        assert 0.0 <= row["pi_spread"] <= 1.0
