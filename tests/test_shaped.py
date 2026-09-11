import random

from src.shaped import shaped_network


def test_tier_sizes_come_out_as_asked():
    net = shaped_network(random.Random(1), (2, 3, 5, 4), 2)
    assert len(net["suppliers"]) == 2
    assert len(net["factories"]) == 3
    assert len(net["warehouses"]) == 5
    assert len(net["hospitals"]) == 4


def test_every_downstream_node_gets_the_guaranteed_in_degree():
    net = shaped_network(random.Random(2), (4, 4, 4, 4), 3)
    tiers = [net["suppliers"], net["factories"], net["warehouses"], net["hospitals"]]
    for upstream, downstream in zip(tiers[:-1], tiers[1:]):
        for node in downstream:
            sources = [u for u in upstream if (u, node) in net["arc_cost"]]
            assert len(sources) >= 3, f"{node} has only {len(sources)} sources"


def test_the_in_degree_is_capped_by_the_tier_above():
    """Asking for three sources when only two sit upstream gives two, not an
    error and not a phantom arc."""
    net = shaped_network(random.Random(3), (2, 4, 4, 4), 3)
    for node in net["factories"]:
        sources = [s for s in net["suppliers"] if (s, node) in net["arc_cost"]]
        assert len(sources) == 2


def test_arcs_only_ever_join_neighbouring_tiers():
    net = shaped_network(random.Random(4), (3, 3, 3, 4), 2)
    allowed = set()
    tiers = [net["suppliers"], net["factories"], net["warehouses"], net["hospitals"]]
    for upstream, downstream in zip(tiers[:-1], tiers[1:]):
        allowed.update((u, d) for u in upstream for d in downstream)
    assert set(net["arc_cost"]) <= allowed


def test_the_same_seed_gives_the_same_network():
    a = shaped_network(random.Random(5), (3, 3, 3, 4), 2)
    b = shaped_network(random.Random(5), (3, 3, 3, 4), 2)
    assert a == b


def test_the_baseline_shape_matches_the_hand_built_tier_sizes():
    """run_shapes.py calls 3-3-3-4 the benchmark shape, so it has to be one."""
    net = shaped_network(random.Random(6), (3, 3, 3, 4), 2)
    assert len(net["suppliers"]) == 3
    assert len(net["factories"]) == 3
    assert len(net["warehouses"]) == 3
    assert len(net["hospitals"]) == 4
