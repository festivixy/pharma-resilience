"""A generator whose tier sizes and connectivity can be set deliberately.

src/generator.py fixes both: every tier holds three or four facilities, and
every downstream node is guaranteed two upstream sources. Those two choices
decide which pairs can disconnect a hospital, so any finding about where cuts
appear has to be tested against other choices before it can be attributed to
tier position.
"""

TIER_NAMES = ["S", "F", "W", "H"]


def shaped_network(rng, sizes, min_in_degree, out_degree=(2, 4)):
    """A layered network with the given tier sizes, where every node in a tier
    receives at least `min_in_degree` arcs from the tier above (capped by how
    many nodes are up there)."""
    tiers = [[f"{prefix}{i + 1}" for i in range(size)]
             for prefix, size in zip(TIER_NAMES, sizes)]
    suppliers, factories, warehouses, hospitals = tiers

    capacity = {n: rng.randint(20, 100) for n in suppliers + factories + warehouses}
    demand = {h: rng.randint(10, 60) for h in hospitals}

    arc_cost = {}
    for upstream, downstream in zip(tiers[:-1], tiers[1:]):
        lo, hi = out_degree
        for src in upstream:
            degree = rng.randint(min(lo, len(downstream)), min(hi, len(downstream)))
            for dst in rng.sample(downstream, degree):
                arc_cost[(src, dst)] = rng.randint(1, 5)
        want = min(min_in_degree, len(upstream))
        for dst in downstream:
            have = [u for u in upstream if (u, dst) in arc_cost]
            candidates = [u for u in upstream if (u, dst) not in arc_cost]
            while len(have) < want and candidates:
                src = candidates.pop(rng.randrange(len(candidates)))
                arc_cost[(src, dst)] = rng.randint(1, 5)
                have.append(src)

    return {
        "suppliers": suppliers,
        "factories": factories,
        "warehouses": warehouses,
        "hospitals": hospitals,
        "capacity": capacity,
        "demand": demand,
        "arc_cost": arc_cost,
        "penalty": 1000,
        "protection_cost_rate": 1.0,
    }
