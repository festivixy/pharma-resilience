"""The US IV-solutions network around the North Cove failure of September 2024.

One unit is one percent of national daily demand for IV solutions, about
25,000 bags a day (North Cove made 1.5 million bags a day and held about 60%
of the market, so the market is near 2.5 million bags a day).

Documented, with sources in docs/real_world_data.md:
  - Baxter North Cove, about 60% of US supply.
  - B. Braun (Irvine CA and Daytona Beach FL together), about 23%.
  - ICU Medical and Fresenius Kabi, the remainder, about 17%.
  - Saline had been on the FDA shortage list since 2018, so the intact market
    ran with no slack. Total capacity therefore equals total demand.
  - McKesson ships one third of US pharmaceutical volume. Three wholesalers
    handle over 90% of wholesale distribution; the rest ships direct.
  - After the failure Baxter allocated direct customers 40% and distributor
    customers 10% of historical purchases.

Assumed, and stated in the paper as assumptions:
  - Cencora 30 and Cardinal 27 of the wholesale share, direct shipments 10.
    Only McKesson's third is documented.
  - Wholesale throughput is 1.5 times each channel's normal volume. The
    constraint in the event was manufacturing, not distribution.
  - Every plant ships to every channel. Each hospital pool draws on its own
    prime wholesaler plus the direct channel, which is how a hospital with a
    single prime-vendor contract gets emergency product.
  - Shipping cost is 1 on every arc. The sensitivity result in the paper says
    costs scaled 0.8 to 1.2 leave the protection frontier unchanged, and the
    real costs are not public.

There is no second manufacturing tier for IV solutions, so `factories` is
empty and the network has three tiers.
"""

PLANTS = {"NorthCove": 60, "BBraun": 23, "Others": 17}
CHANNELS = {"McKesson": 33, "Cencora": 30, "Cardinal": 27, "Direct": 10}
THROUGHPUT_HEADROOM = 1.5
POOL_OF = {"McKesson": "H_McK", "Cencora": "H_Cen", "Cardinal": "H_Car", "Direct": "H_Dir"}


def north_cove_network(penalty=1000, protection_cost_rate=1.0):
    suppliers = list(PLANTS)
    warehouses = list(CHANNELS)
    hospitals = [POOL_OF[c] for c in warehouses]

    capacity = dict(PLANTS)
    capacity.update({c: THROUGHPUT_HEADROOM * share for c, share in CHANNELS.items()})
    demand = {POOL_OF[c]: share for c, share in CHANNELS.items()}

    arc_cost = {}
    for plant in suppliers:
        for channel in warehouses:
            arc_cost[(plant, channel)] = 1
    for channel in warehouses:
        arc_cost[(channel, POOL_OF[channel])] = 1
    for pool in hospitals:
        arc_cost[("Direct", pool)] = 1

    return {
        "suppliers": suppliers,
        "factories": [],
        "warehouses": warehouses,
        "hospitals": hospitals,
        "capacity": capacity,
        "demand": demand,
        "arc_cost": arc_cost,
        "penalty": penalty,
        "protection_cost_rate": protection_cost_rate,
    }
