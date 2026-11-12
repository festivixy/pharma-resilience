"""Network families that do not pass through the calibration invariant.

src/calibrated.py keeps a network only if every single failure causes a
shortage, and that filter rejects most of what the generator draws. Anything
measured on the survivors could be a property of the filter. The two
generators here drop it: one keeps the capacity tightening and nothing else,
the other keeps the generator's own capacities. Both only require that the
intact network serves every hospital.
"""

import random

from src.calibrated import scale_capacity, tightest_feasible_factor
from src.generator import random_layered_network
from src.model import solve
from src.shaped import shaped_network

FULL = 1 - 1e-9


def _draw(rng: random.Random, sizes, min_in_degree) -> dict:
    if min_in_degree is None:
        return random_layered_network(rng, sizes)
    return shaped_network(rng, sizes, min_in_degree)


def tightened_network(rng: random.Random, sizes=None, min_in_degree=None,
                      slack_range=(0.02, 0.50), attempts: int = 40) -> dict | None:
    """A layered network scaled to between 2% and 50% above the tightest
    capacity at which it still serves everyone, exactly as the calibrated
    generator does, but with no condition on what a failure does to it."""
    for _ in range(attempts):
        base = _draw(rng, sizes, min_in_degree)
        factor = tightest_feasible_factor(base)
        if factor is None:
            continue
        candidate = scale_capacity(base, factor * (1 + rng.uniform(*slack_range)))
        if solve(candidate)["satisfaction"] >= FULL:
            return candidate
    return None


def raw_network(rng: random.Random, attempts: int = 40) -> dict | None:
    """A generator draw with its capacities untouched, kept if the intact
    network serves everyone. Most single failures do nothing to these."""
    for _ in range(attempts):
        candidate = random_layered_network(rng)
        if solve(candidate)["satisfaction"] >= FULL:
            return candidate
    return None


def bootstrap_interval(clusters: list[tuple[int, int]], rng: random.Random,
                       resamples: int = 2000, level: float = 0.95) -> tuple[float, float]:
    """A percentile interval for a pooled rate, resampling whole networks.

    `clusters` holds one (events, states) pair per network. States from the
    same network share its arcs and capacities, so they are not independent,
    and an interval that resamples states would be too narrow."""
    rates = []
    for _ in range(resamples):
        sample = [rng.choice(clusters) for _ in clusters]
        states = sum(n for _, n in sample)
        if states:
            rates.append(sum(e for e, _ in sample) / states)
    rates.sort()
    tail = (1 - level) / 2
    return rates[int(tail * len(rates))], rates[min(len(rates) - 1, int((1 - tail) * len(rates)))]
