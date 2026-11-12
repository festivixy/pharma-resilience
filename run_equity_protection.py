"""Does protection help the worst-served hospital, and does an equitable plan
deliver equity once the cost-minimising router runs on it?

The paradox instance of src/network.py shows protection can raise satisfaction
and lower the worst-hospital fill rate. That is one constructed network. This
counts how often it happens, three ways, under tie-free shipping costs:

  uniform   every capacity raised by the same fraction, in steps of 5%. A step
            is a reversal if the worst-hospital fill rate falls across it.
  plan      the aggregate-target plan of src/robust.py. The program has many
            optimal allocations, so each network is solved once at equal rates
            (the allocation CBC happens to return) and five more times with
            every facility's rate drawn within 1% of nominal, which picks five
            further optimal or near-optimal allocations. A scenario is a
            reversal if the worst-hospital fill rate is lower after protection
            than before it.
  router    the per-hospital plan, which guarantees that a routing giving every
            hospital the target exists, evaluated with the cost-minimising
            router that the rest of the paper uses. A scenario misses if the
            worst-hospital fill rate comes out below the target.

    python run_equity_protection.py [networks_per_family] [workers]
"""

import csv
import random
import sys
from multiprocessing import Pool
from pathlib import Path

from run_equity_families import FAMILY_NAMES, networks
from src.experiment import apply_protection, fail_nodes
from src.fairness import fair_equity, generic_costs
from src.model import solve
from src.robust import apply_allocation, min_spend_plan
from src.scenarios import single_node_failures

COUNT = 60
SEED = 2026
FULL = 1 - 1e-9
DROP = 1e-4
LEVELS = [round(0.05 * i, 2) for i in range(11)]
TARGETS = [0.80, 0.90]
TIE_BREAKS = 5
RATE_BAND = 0.01

# name, tier sizes, guaranteed in-degree; the same networks as run_equity_families.py
FAMILIES = [
    ("calibrated", None, None),
    ("tightened", None, None),
    ("2-3-5-5", (2, 3, 5, 5), 2),
    ("4-4-4-4 in-degree 3", (4, 4, 4, 4), 3),
]


def _fills(state, result):
    return {h: 1 - result["unmet"][h] / state["demand"][h] for h in state["hospitals"]}


def _largest_fall(before, after):
    return max(before[h] - after[h] for h in before)


def uniform_rows(key, net, scenarios):
    rows = []
    for failed in scenarios:
        previous = None
        for level in LEVELS:
            state = fail_nodes(apply_protection(net, level), failed)
            result = solve(state)
            fills = _fills(state, result)
            if previous is not None and previous["satisfaction"] < FULL:
                rows.append(dict(key, failed="+".join(failed), level=level,
                                 satisfaction_before=previous["satisfaction"],
                                 satisfaction_after=result["satisfaction"],
                                 equity_before=previous["equity"],
                                 equity_after=result["min_fill_rate"],
                                 largest_fill_fall=_largest_fall(previous["fills"], fills)))
            previous = {"satisfaction": result["satisfaction"],
                        "equity": result["min_fill_rate"], "fills": fills}
    return rows


def plan_rows(key, net, scenarios, before, target, tie_break, rates):
    plan = min_spend_plan(net, scenarios, target, rates=rates)
    if plan["status"] != "Optimal":
        return []
    protected = apply_allocation(net, plan["extra"])
    rows = []
    for failed in scenarios:
        was = before[failed]
        if was is None:
            continue
        state = fail_nodes(protected, failed)
        result = solve(state)
        rows.append(dict(key, target=target, tie_break=tie_break, failed="+".join(failed),
                         spend=sum(plan["extra"].values()),
                         satisfaction_before=was["satisfaction"],
                         satisfaction_after=result["satisfaction"],
                         equity_before=was["equity"], equity_after=result["min_fill_rate"],
                         fair_before=was["fair"], fair_after=fair_equity(state),
                         largest_fill_fall=_largest_fall(was["fills"], _fills(state, result))))
    return rows


def router_rows(key, net, scenarios, before, target):
    plan = min_spend_plan(net, scenarios, target, per_hospital=True)
    if plan["status"] != "Optimal":
        return []
    protected = apply_allocation(net, plan["extra"])
    rows = []
    for failed in scenarios:
        if before[failed] is None:
            continue
        result = solve(fail_nodes(protected, failed))
        rows.append(dict(key, target=target, failed="+".join(failed),
                         spend=plan["spend"],
                         satisfaction=result["satisfaction"],
                         equity=result["min_fill_rate"],
                         missed=result["min_fill_rate"] < target - 1e-5))
    return rows


def _instance(args):
    family, index, network, cost_seed = args
    key = {"family": family, "instance": index}
    net = generic_costs(network, random.Random(cost_seed))
    scenarios = single_node_failures(net)

    before = {}
    for failed in scenarios:
        state = fail_nodes(net, failed)
        result = solve(state)
        before[failed] = None if result["satisfaction"] >= FULL else {
            "satisfaction": result["satisfaction"], "equity": result["min_fill_rate"],
            "fair": fair_equity(state), "fills": _fills(state, result)}

    rate_rng = random.Random(cost_seed + 1)
    nodes = list(net["capacity"])
    tie_breaks = [None] + [{n: net["protection_cost_rate"]
                            * rate_rng.uniform(1 - RATE_BAND, 1 + RATE_BAND) for n in nodes}
                           for _ in range(TIE_BREAKS)]
    plan, router = [], []
    for target in TARGETS:
        for number, rates in enumerate(tie_breaks):
            plan.extend(plan_rows(key, net, scenarios, before, target, number, rates))
        router.extend(router_rows(key, net, scenarios, before, target))
    return uniform_rows(key, net, scenarios), plan, router


def _write(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _networks_with(rows, test):
    return len({r["instance"] for r in rows if test(r)})


def report(family, count, uniform, plan, router):
    fell = [r for r in uniform if r["equity_before"] - r["equity_after"] > DROP]
    any_fell = [r for r in uniform if r["largest_fill_fall"] > DROP]
    print("  %s, %d networks" % (family, count))
    print("    uniform: %d steps, worst fill falls in %d, some hospital's fill falls in %d"
          % (len(uniform), len(fell), len(any_fell)))
    for target in TARGETS:
        at = [r for r in plan if r["target"] == target]
        if not at:
            continue
        per_break = []
        for number in range(TIE_BREAKS + 1):
            rows = [r for r in at if r["tie_break"] == number]
            rev = [r for r in rows if r["equity_before"] - r["equity_after"] > DROP]
            per_break.append((len(rev), len(rows),
                              _networks_with(rows, lambda r: r["equity_before"] - r["equity_after"] > DROP)))
        ever = _networks_with(at, lambda r: r["equity_before"] - r["equity_after"] > DROP)
        always = set.intersection(*[
            {r["instance"] for r in at if r["tie_break"] == number
             and r["equity_before"] - r["equity_after"] > DROP}
            for number in range(TIE_BREAKS + 1)])
        equal = [r for r in at if r["tie_break"] == 0]
        falls = sorted(r["equity_before"] - r["equity_after"] for r in at
                       if r["equity_before"] - r["equity_after"] > DROP)
        fair_fell = sum(1 for r in at if r["fair_before"] - r["fair_after"] > DROP)
        print("    plan at %.0f%%: reversals per allocation (scenarios, networks): %s"
              % (100 * target, ", ".join("%d of %d, %d" % b for b in per_break)))
        print("      networks with a reversal under some allocation %d, under every allocation %d; "
              "median fall %.3f, largest %.3f; fair equity fell in %d"
              % (ever, len(always), falls[len(falls) // 2] if falls else 0.0,
                 falls[-1] if falls else 0.0, fair_fell))
        print("      equal-rate allocation: mean equity %.3f before, %.3f after, %.3f fair after; "
              "stranded %d before, %d after"
              % (sum(r["equity_before"] for r in equal) / len(equal),
                 sum(r["equity_after"] for r in equal) / len(equal),
                 sum(r["fair_after"] for r in equal) / len(equal),
                 sum(1 for r in equal if r["equity_before"] <= 1e-6),
                 sum(1 for r in equal if r["equity_after"] <= 1e-6)))
        rt = [r for r in router if r["target"] == target]
        if not rt:
            print("      per-hospital plan infeasible on every network")
            continue
        missed = [r for r in rt if r["missed"]]
        gaps = sorted(target - r["equity"] for r in missed)
        print("      per-hospital plan under the cost router: target missed in %d of %d scenarios "
              "(%.1f%%), on %d of %d networks; median miss %.3f; stranded %d"
              % (len(missed), len(rt), 100.0 * len(missed) / len(rt),
                 _networks_with(rt, lambda r: r["missed"]), _networks_with(rt, lambda r: True),
                 gaps[len(gaps) // 2] if gaps else 0.0,
                 sum(1 for r in rt if r["equity"] <= 1e-6)))
        aggregate = {r["instance"]: r["spend"] for r in equal}
        extra = sorted(spend - aggregate[i]
                       for i, spend in {r["instance"]: r["spend"] for r in rt}.items())
        print("      per-hospital plan against the aggregate plan: same spend on %d of %d networks; "
              "largest extra %.1f" % (sum(1 for e in extra if e <= 1e-6), len(extra), extra[-1]))
    sys.stdout.flush()


def main(count=COUNT, workers=6, out_dir="results"):
    uniform, plan, router = [], [], []
    with Pool(workers) as pool:
        for name, sizes, min_in_degree in FAMILIES:
            seed = SEED + FAMILY_NAMES.index(name)
            nets = networks(name, sizes, min_in_degree, count, seed)
            results = pool.map(_instance, [(name, i, net, 1000 * seed + i)
                                           for i, net in enumerate(nets)])
            u = [r for res in results for r in res[0]]
            p = [r for res in results for r in res[1]]
            rt = [r for res in results for r in res[2]]
            report(name, len(nets), u, p, rt)
            uniform.extend(u)
            plan.extend(p)
            router.extend(rt)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write(out / "equity_protection_uniform.csv", uniform)
    _write(out / "equity_protection_plan.csv", plan)
    _write(out / "equity_protection_router.csv", router)
    print("outputs written to %s/equity_protection_*.csv" % out)


if __name__ == "__main__":
    args = sys.argv[1:]
    main(int(args[0]) if args else COUNT, int(args[1]) if len(args) > 1 else 6)
