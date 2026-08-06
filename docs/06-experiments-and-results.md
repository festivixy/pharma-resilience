# Chapter 6 — Experiments and results

Nine experiments, seven CSV files, four figures. This chapter documents each
one: how it is generated, what every column means, and how to read a row.

Every number quoted here was regenerated during this documentation pass and
checked against the current code. Where the root `README.md` disagrees with the
code, the difference is recorded in
[Documentation discrepancies](#documentation-discrepancies) rather than resolved
silently.

## Tracked versus generated artifacts

This distinction matters when you clone the repository.

| Artifact | Tracked in git? | Appears after |
|---|---|---|
| `results/network.png` | **Yes** | already present |
| `results/tradeoff.png` | **Yes** | already present |
| `results/frontier.png` | **Yes** | already present |
| `results/sensitivity.png` | **Yes** | already present |
| `results/sweep.csv` | No | `python run.py` |
| `results/sensitivity.csv` | No | `python run.py` |
| `results/frontier.csv` | No | `python run.py` |
| `results/plans.csv` | No | `python run.py` |
| `results/paradox.csv` | No | `python run.py` |
| `results/scaled.csv` | No | `python run_scaled.py` |
| `results/integrality.csv` | No | `python run_integrality.py` |

`.gitignore` line 57 ignores `*.csv` repository-wide, and lines 68-69 ignore
`results/*` except `*.png`. **A fresh clone therefore contains the figures but
none of the underlying data**, and the tables in the root `README.md` cannot be
verified against a tracked file until the scripts are run.

## Experiment 1 — Uniform protection sweep, single failures

**Question.** If you raise every facility's capacity by the same percentage, how
much worst-case delivery does each percentage point buy?

**How.** `protection_sweep(net, LEVELS, single_node_failures(net))` at
[`run.py:23`](../run.py). For each of 11 levels: scale all capacities by $(1+p)$,
solve the intact network once for the recovery-cost baseline, solve each of the 9
single-failure scenarios, and record the worst.

**Results.**

| Level $p$ | Spend | Worst-case satisfaction | Binding failure | Max recovery cost |
|---|---|---|---|---|
| 0.00 | 0 | 72.22% | S1 | 49,760 |
| 0.05 | 33 | 75.83% | S1 | 43,299 |
| 0.10 | 66 | 79.44% | S1 | 36,838 |
| 0.15 | 99 | 83.06% | S1 | 30,377 |
| 0.20 | 132 | 86.67% | S1 | 23,916 |
| 0.25 | 165 | 90.28% | S1 | 17,455 |
| 0.30 | 198 | 93.06% | **W1** | 12,539 |
| 0.35 | 231 | 95.14% | W1 | 8,815.5 |
| 0.40 | 264 | 97.22% | W1 | 5,092 |
| 0.45 | 297 | 99.31% | W1 | 1,368.5 |
| 0.50 | 330 | 100.00% | S1 (tie) | 125 |

**Three findings.**

*Diminishing returns are real but mild.* The satisfaction gain per unit of spend
is roughly $0.036$ per 33 units of spend from $p=0$ to $p=0.25$, then about
$0.021$ per 33 from $p=0.30$ onward. The curve bends, but it is far from flat —
this instance does not exhibit the sharp saturation one might expect.

*The binding failure changes at $p = 0.30$.* Below that, `S1` — the largest
supplier — is the worst case. Above it, `W1` — the largest warehouse. Because
uniform protection multiplies rather than adds, it closes the supplier gap and
the warehouse gap at different absolute rates. The practical implication is
sharp: **a "most critical facility" ranking is only valid at one protection
level.** Rank on the unprotected network and you will over-invest in `S1`.

*Recovery cost collapses.* From 49,760 to 125 across the sweep — but see the
[caveat on what recovery cost measures](#a-caveat-on-recovery-cost) below.

At $p = 0.50$ every scenario reaches satisfaction 1.0, so `worst_case` returns
the first row in list order. The reported `S1` is a **tie-break artefact**, not a
statement that `S1` is still weakest.

## Experiment 2 — Uniform protection sweep, paired failures

**Question.** Does the same money still buy resilience when two facilities fail
at once?

**How.** Identical, with the 36 pair scenarios
([`run.py:24`](../run.py)). 407 LP solves.

**Results.**

| Level $p$ | Spend | Worst-case satisfaction | Binding failure |
|---|---|---|---|
| 0.00 | 0 | 33.33% | S1+S2 |
| 0.05 | 33 | 35.00% | S1+S2 |
| 0.10 | 66 | 36.67% | S1+S2 |
| 0.15 | 99 | 38.33% | S1+S2 |
| 0.20 | 132 | **38.89%** | **W1+W2** |
| 0.25 – 0.50 | 165 – 330 | **38.89%** | **W1+W2** | 

**The finding.** From $p = 0.20$ onward the worst case is frozen at 38.89% and
the binding scenario is permanently `W1+W2`. Spending the remaining 198 units
buys **nothing**.

The mechanism is structural, not economic. `H1` and `H2` are reachable only from
`W1` and `W2` (see
[Chapter 2](02-network-and-data-model.md#structural-bottlenecks)). Losing both
warehouses disconnects $60 + 50 = 110$ of 180 demand units, capping satisfaction
at $70/180 = 0.3889$. Capacity is attached to nodes; the missing resource is an
**arc**. No budget can buy a route that does not exist.

Below $p = 0.20$ the binding scenario is `S1+S2` — a *capacity* bottleneck, which
protection does fix. The transition at $p = 0.20$ is the moment the problem stops
being an investment problem and becomes a network-design problem.

This is also why `min_spend_plan(net, pair_failures(net), 1.0)` returns
`Infeasible`, asserted at
[`tests/test_robust.py:48-51`](../tests/test_robust.py).

## `results/sweep.csv`

**Generated by** [`run.py:27-40`](../run.py), zipping the two sweeps row by row.
**Rows:** 11 (one per level). **Consumed by:** the root `README.md` results
table, and — as the in-memory `singles` and `pairs` lists — by `tradeoff_plot`
and `frontier_plot`.

| Column | Type | Units | Range | Meaning |
|---|---|---|---|---|
| `level` | float | dimensionless | 0.00 – 0.50 | Uniform protection level $p$ |
| `spend` | float | cost | 0 – 330 | $r \cdot p \cdot \sum_n u_n = 660p$ |
| `worst_satisfaction_single` | float | dimensionless | 0 – 1 | Min satisfaction over the 9 single failures |
| `worst_scenario_single` | str | — | node name | Which failure was worst; `+`-joined |
| `max_recovery_cost_single` | float | cost | ≥ 0 | Max over the 9 scenarios of (disrupted cost − intact cost at the same level) |
| `worst_satisfaction_pairs` | float | dimensionless | 0 – 1 | Min satisfaction over the 36 pairs |
| `worst_scenario_pairs` | str | — | `A+B` | Which pair was worst |

**Reading one row.**

```csv
0.3,198.0,0.9305555555555556,W1,12539.0,0.38888888888888884,W1+W2
```

At protection level 0.30 you have spent 198 cost units raising every capacity by
30%. Against single failures the worst outcome is losing `W1`, which still
delivers 93.06% of total demand and costs at most 12,539 more than the intact
protected network. Against paired failures the worst is losing `W1` **and** `W2`
together, which delivers only 38.89% — and that number will not improve however
much more you spend.

**Note the asymmetry:** there is no `max_recovery_cost_pairs` column.
`protection_sweep` computes it for the pair sweep, but
[`run.py:35-40`](../run.py) does not write it.

## Experiment 3 — Sensitivity analysis

**Question.** Do the findings survive getting the input numbers wrong by ±20%?

**How.** `run_sensitivity(net, LEVELS, single_node_failures(net))` at
[`run.py:25`](../run.py). Five variants, each a full 11-level sweep. 550 LP
solves — the most expensive stage of `run.py`.

**Results at the endpoints.**

| Variant | Spend at $p=0$ | Satisfaction at $p=0$ | Spend at $p=0.5$ | Satisfaction at $p=0.5$ |
|---|---|---|---|---|
| `base` | 0 | 72.22% | 330 | 100.00% |
| `cost_x0.8` | 0 | 72.22% | 330 | 100.00% |
| `cost_x1.2` | 0 | 72.22% | 330 | 100.00% |
| `capacity_x0.8` | 0 | 57.78% | 264 | 86.67% |
| `capacity_x1.2` | 0 | 86.67% | 396 | 100.00% |

**Finding 1 — cost variation changes nothing at all.** The two cost variants
produce curves *exactly* equal to the base, at every level. Not approximately —
identically, to the last floating-point bit. That is a **prediction of the
model**, not a coincidence: because the shortage penalty (1000) dominates
shipping costs (1–4), the LP always maximizes delivery first, and scaling all
shipping costs by a constant cannot change which delivery volume is achievable.
See [Chapter 3](03-mathematical-model.md#why-the-penalty-must-be-large).

This exactness is why `coinciding_variants`
([`src/plots.py:167-174`](../src/plots.py)) can use plain `==` on float lists, and
why the sensitivity figure folds those two variants into the base legend entry
rather than drawing three identical lines.

**Finding 2 — capacity variation shifts the curve without changing its
character.** All three capacity variants are concave, all show a binding-failure
switch, all behave the same way qualitatively. Note the shift is in *both* axes:
`capacity_x1.2` starts higher (86.67% versus 72.22%) but its spend axis is
stretched too, because `protection_spend` is computed from the scaled network's
capacities ($1.2 \times 660 \times p = 792p$).

There is a neat identity underneath: scaling capacity by 1.2 and applying
protection $p$ gives the same capacities as the base network at level
$p'$ where $1 + p' = 1.2(1+p)$. At $p = 0$ that is $p' = 0.2$ — and indeed
`capacity_x1.2` at level 0 shows 86.67%, exactly the base network's value at
level 0.20. Capacity scaling is a reparameterisation of the protection axis, not
a new phenomenon.

**Finding 3 — `capacity_x0.8` never reaches full protection.** It tops out at
86.67% at the maximum level. A 20% weaker network cannot be made fully resilient
within the sweep's range.

**Limitation.** This is a one-factor-at-a-time analysis over a single instance.
It shows the results are not knife-edge sensitive to these two parameters. It
does **not** establish robustness to structural changes, to the penalty value, to
the protection cost rate, or to joint perturbations.

## `results/sensitivity.csv`

**Generated by** [`run.py:42-47`](../run.py) in long format.
**Rows:** 55 = 5 variants × 11 levels. **Consumed by:** `sensitivity_plot`
(via the in-memory dict).

| Column | Type | Units | Range | Meaning |
|---|---|---|---|---|
| `variant` | str | — | one of 5 names | Which perturbation |
| `level` | float | dimensionless | 0.00 – 0.50 | Protection level |
| `spend` | float | cost | 0 – 396 | Spend **for that variant's capacities** |
| `worst_satisfaction` | float | dimensionless | 0 – 1 | Min over the 9 single failures |

**Reading one row.**

```csv
capacity_x1.2,0.0,0.0,0.8666666666666667
```

On a network whose every capacity was first multiplied by 1.2, with no further
protection purchased, the worst single failure still delivers 86.67% of demand.

## Experiment 4 — Optimized frontier

**Question.** If an optimizer chooses where the protection goes, what does each
level of guarantee cost?

**How.** For each of six targets $\tau$: `ccg_plan` finds the cheapest
allocation, `apply_allocation` builds the protected network, and
`evaluate_scenarios` **independently re-checks** it against all nine scenarios
([`run.py:49-59`](../run.py)).

**Results.**

| Target $\tau$ | Optimized spend | C&CG iterations | Achieved worst-case | Uniform spend for the same guarantee |
|---|---|---|---|---|
| 0.75 | 5.0 | 2 | 75.00% | ≈ 25 |
| 0.80 | 27.0 | 4 | 80.00% | ≈ 71 |
| 0.85 | 54.0 | 7 | 85.00% | ≈ 117 |
| 0.90 | 89.0 | 8 | 90.00% | ≈ 162 |
| 0.95 | 129.5 | 9 | 95.00% | ≈ 229 |
| 1.00 | 170.0 | 9 | 100.00% | 330 |

The right-hand column is a **linear interpolation of the uniform sweep**, done by
hand for comparison. No code in the repository computes it — see
[discrepancy D7](#documentation-discrepancies).

**Finding.** The achieved worst case equals the target exactly in every row: the
optimizer buys precisely enough and not one unit more. And the optimized frontier
**strictly dominates** the uniform curve everywhere — at $\tau = 1.0$ it costs
170 against 330, a saving of 160 (48%).

**Why optimized wins.** The allocation at $\tau = 1.0$:

| Node | S1 | S2 | S3 | F1 | F2 | F3 | W1 | W2 | W3 |
|---|---|---|---|---|---|---|---|---|---|
| Extra capacity $e_n$ | 10 | 20 | 30 | **0** | 10 | 30 | 25 | 35 | 10 |
| Uniform at $p=0.5$ | 40 | 35 | 30 | 45 | 40 | 30 | 42.5 | 37.5 | 30 |

Uniform buys 45 units at `F1`; the optimizer buys **none**. `F1`'s 90 units are
already sufficient in every scenario where it survives, so every unit uniform
spends there is wasted. The optimizer also *over*-invests relative to uniform
where it matters — 35 at `W2` versus uniform's 37.5 is close, but 30 at `S3`
versus 30 is identical while `S1` gets 10 instead of 40.

**Iteration counts** rise with the target (2, 4, 7, 8, 9, 9). Harder targets make
more scenarios binding, so C&CG must add more of them before it can certify
optimality. That is the algorithm behaving exactly as its theory predicts: **the
work depends on the number of binding scenarios, not on the size of the
uncertainty set.**

## `results/frontier.csv`

**Generated by** [`run.py:61-67`](../run.py). **Rows:** 6.
**Consumed by:** `frontier_plot`, the root `README.md` table.

| Column | Type | Units | Range | Meaning |
|---|---|---|---|---|
| `target` | float | dimensionless | 0.75 – 1.00 | Requested worst-case satisfaction $\tau$ |
| `spend` | float | cost | ≥ 0 | $r \sum_n e_n$ for the C&CG allocation |
| `iterations` | int | count | ≥ 1 | C&CG iterations, including the final confirming pass |
| `worst_satisfaction` | float | dimensionless | 0 – 1 | Independently re-measured worst case |

**Reading one row.**

```csv
0.9,89.0,8,0.9
```

To guarantee that no single facility failure drops delivery below 90%, buy 89
units of extra capacity. C&CG found this in 8 iterations — meaning it added 7 of
the 9 scenarios to its master problem. Re-evaluating the resulting network
against all nine failures confirms the worst is exactly 90%.

The equality of `target` and `worst_satisfaction` in every row is the check that
matters: it confirms the plan delivers what it promised, measured by a code path
independent of the one that produced it.

## Experiment 5 — Normal versus robust plan comparison

**Question.** What does a cost-only plan actually cost a hospital, scenario by
scenario, and what does full robust protection change?

**How.** [`run.py:69-72`](../run.py). Evaluate all nine single failures twice:
once on the unprotected network, once on the network with the $\tau = 1.0$ C&CG
allocation applied.

**Results.**

| Scenario | Satisfaction (cost-only) | Equity (cost-only) | Recovery cost (cost-only) | Satisfaction (robust) | Equity (robust) | Recovery cost (robust) |
|---|---|---|---|---|---|---|
| S1 | 72.22% | 16.67% | 49,760 | 100% | 100% | 60 |
| S2 | 77.78% | 40.00% | 39,810 | 100% | 100% | 70 |
| S3 | 83.33% | **0.00%** | 29,870 | 100% | 100% | 60 |
| F1 | 77.78% | 58.33% | 39,835 | 100% | 100% | 60 |
| F2 | 83.33% | 60.00% | 29,905 | 100% | 100% | 70 |
| F3 | 94.44% | 75.00% | 10,035 | 100% | 100% | 60 |
| W1 | 75.00% | 25.00% | 44,810 | 100% | 100% | 160 |
| W2 | 80.56% | 50.00% | 34,850 | 100% | 100% | 70 |
| W3 | 88.89% | 62.50% | 19,950 | 100% | 100% | 60 |

**The finding that matters is row `S3`.** Satisfaction is 83.33% — the third-best
outcome in the table, and a number a dashboard would render green. Equity is
**0.00**: one hospital receives nothing whatsoever. Averages conceal
distributional collapse, and the max-min metric is what exposes it.

Under the robust plan every scenario reaches 100% on both metrics, and recovery
costs fall into the range 60–160.

### A caveat on recovery cost

The cost-only recovery costs (10,035 to 49,760) look like enormous operational
losses. They are not. Recovery cost is
$\text{disrupted cost} - \text{intact cost}$, and disrupted cost is dominated by
the **artificial shortage penalty** of 1000 per unit. For scenario `S1`:

$$\underbrace{50{,}700}_{\text{disrupted}} - \underbrace{940}_{\text{intact}} = 49{,}760, \quad\text{of which}\quad \underbrace{50{,}000}_{\text{penalty}} \text{ is } 100.5\%.$$

The genuine rerouting cost is $700 - 940 = -240$ — shipping actually got
*cheaper*, because 50 units simply were not shipped.

So **recovery cost should be read as a penalty-weighted severity index, not as a
monetary figure.** It is monotone in the shortage, which makes it a valid ranking
of how bad a scenario is; it is not a forecast of anything. Under the robust plan
there is no shortage, so the robust recovery costs (60–160) *are* genuine
rerouting costs.

## `results/plans.csv`

**Generated by** [`run.py:74-88`](../run.py). **Rows:** 9, in scenario order.
**Consumed by:** the root `README.md` table and
[`tests/test_run.py:31-37`](../tests/test_run.py).

| Column | Type | Units | Range | Meaning |
|---|---|---|---|---|
| `scenario` | str | — | node name | The failed node |
| `cost_normal` | float | cost | > 0 | LP objective, unprotected |
| `satisfaction_normal` | float | — | 0 – 1 | Fraction of demand delivered |
| `equity_normal` | float | — | 0 – 1 | `min_fill_rate` — note the **column is named `equity`** |
| `recovery_cost_normal` | float | cost | ≥ 0 | Disrupted minus intact, unprotected |
| `cost_robust` … `recovery_cost_robust` | | | | The same four under the $\tau = 1.0$ plan |

**Reading one row.**

```csv
S3,30810.0,0.8333333333333334,0.0,29870.0,1000.0,1.0,1.0,60.0
```

When supplier `S3` fails on the unprotected network, the LP objective is 30,810 —
of which 29,870 is the excess over the intact cost of 940, and almost all of that
excess is the penalty on 30 undelivered units. 83.3% of total demand is met, but
the worst-served hospital gets **zero**. Under the robust plan the same failure
costs 1,000 (all shipping), meets 100% of demand, and leaves every hospital fully
served.

## Experiment 6 — The equity paradox

**Question.** Can optimizing worst-case satisfaction make the distribution of
service *worse*?

**Answer: yes, provably, on a six-arc network.**

**How.** [`run.py:90-96`](../run.py) on `equity_paradox_network()`. A single
scenario `[("W2",)]` and a target of 0.55. `min_spend_plan` is used directly —
with one scenario there is nothing for C&CG to select. The two rows evaluate the
network **intact**, before and after the plan is applied: the paradox is about
how a protection plan reshapes the *normal* operating optimum.

**Results.**

| Plan | Spend | Satisfaction | Min fill rate (equity) |
|---|---|---|---|
| unprotected | 0.0 | **50.0%** | **40.0%** |
| protected | 9.0 | **55.0%** ↑ | **10.0%** ↓ |

**Walking through it.** The network has supplier and factory capacity of 10
against total demand of 20, so at most half of demand can ever be met.
`W1` (capacity 4) reaches both hospitals; `W2` (capacity 6) reaches only `H2`.
The route to `H1` costs 3 per unit; the route to `H2` through `W2` costs 7.

*Unprotected*, the cheapest way to move 10 units is 4 through `W1` to `H1` and 6
through `W2` to `H2`. Both hospitals get something: fill rates 0.4 and 0.6, so
equity is 0.4.

*The protection plan* must survive `W2` failing while delivering at least 11
units, so it buys +1 at `S`, +1 at `F`, and +7 at `W1` — spend 9. Now `W1` can
carry 11 units on its own.

*Protected and intact*, the solver has 11 units of throughput and a cheap route
to `H1`. It sends 10 to `H1` — filling it completely — and 1 to `H2`. Fill rates
become 1.0 and 0.1, so equity is **0.1**.

**The mechanism.** The target constraint at
[`src/robust.py:55`](../src/robust.py) bounds *total* unmet demand and says
nothing about its distribution. Adding capacity to `W1` also made the cheap route
to `H1` wider, and the cost-minimizing recourse LP took it. Equity is measured
everywhere in this project and constrained nowhere.

**Scope of the claim.** This is an existence proof on a hand-built instance, not
a statement about frequency. It shows the failure mode is a genuine property of
the formulation. It does not claim the paradox arises often, or that it arises on
the base network — it does not; there, robust protection lifts every hospital to
100%.

## `results/paradox.csv`

**Generated by** [`run.py:98-104`](../run.py). **Rows:** 2.
**Consumed by:** [`tests/test_run.py:39-47`](../tests/test_run.py).

| Column | Type | Units | Range | Meaning |
|---|---|---|---|---|
| `plan` | str | — | `unprotected` / `protected` | Which configuration |
| `spend` | float | cost | ≥ 0 | 0.0 or the plan's spend |
| `satisfaction` | float | — | 0 – 1 | Intact-network satisfaction |
| `min_fill_rate` | float | — | 0 – 1 | Intact-network equity |

**Reading the file.**

```csv
protected,9.0,0.55,0.09999999999999998
```

After spending 9 units on protection, the network's normal operating optimum
delivers 55% of total demand — up from 50% — while the worst-served hospital's
fill rate falls to 10%, down from 40%. The trailing digits are ordinary
floating-point representation of $1/10$; the exact value is 0.1.

## Experiment 7 — Scaling

**Question.** Does the toolchain work on a network an order of magnitude larger,
and how do exhaustive LP and C&CG compare on time?

**How.** [`run_scaled.py`](../run_scaled.py) with default sizes
`(10, 10, 10, 12)` and seed 2026.

**Verified output.**

```text
network (10, 10, 10, 12) seed 2026: 42 nodes, 99 arcs, 30 single-failure scenarios
baseline satisfaction 1.000, worst failure W3 -> 0.971
full LP: spend 24.0 in 0.13s
C&CG:    spend 24.0 in 3.15s (3 iterations)
```

**Finding 1 — the methods agree.** Both return 24.0. This is the correctness
result, and `test_scaled_run_writes_outputs_and_matches_ccg_to_full_lp`
([`tests/test_run_scaled.py:6-11`](../tests/test_run_scaled.py)) asserts it at a
smaller size.

**Finding 2 — C&CG is about 24× slower here.** Its exhaustive oracle re-solves
all 30 scenarios per iteration ($3 \times 30 = 90$ LP solves, plus 2 master LPs)
where the full LP is one solve of one larger model. This is exactly what an
exhaustive-oracle implementation should do; see
[Chapter 3](03-mathematical-model.md#why-this-is-an-educational-implementation).

> **This experiment does not demonstrate that C&CG scales.** It demonstrates
> that C&CG is *correct* at a larger size. Any claim that the repository shows a
> scalability advantage for C&CG would be unsupported by its own measurements.

**Finding 3 — random networks are far less fragile than the hand-built one.**
Only **2 of the 30** single failures cause any shortage at all: `W3` (satisfaction
0.971, equity 0.711) and `W5` (0.975, equity 0.656). The other 28 are absorbed
completely, costing extra shipping but no lost delivery. Contrast the base
network, where *every* one of its 9 single failures causes a shortage by design.

The generator does not enforce the calibration invariant
([Chapter 2](02-network-and-data-model.md#capacities-and-demands)), so a random
network is typically over-provisioned relative to its demand. That is why full
protection costs only 24.0 here against 170.0 on the much smaller base network.
The scaling experiment therefore measures **throughput and algorithmic
agreement**, not resilience economics.

## `results/scaled.csv`

**Generated by** [`run_scaled.py:39-46`](../run_scaled.py). **Rows:** one per
single-failure scenario — 30 at the default size. **Consumed by:** nothing
programmatic; `test_run_scaled.py` checks only that the file exists.

| Column | Type | Units | Range | Meaning |
|---|---|---|---|---|
| `failed` | str | — | node name | The failed node |
| `satisfaction` | float | — | 0 – 1 | Fraction of demand delivered, **unprotected** |
| `min_fill_rate` | float | — | 0 – 1 | Worst hospital's fill rate |
| `recovery_cost` | float | cost | ≥ 0 | Disrupted minus intact cost |

**Reading one row.**

```csv
S8,1.0,1.0,347.0
```

Losing supplier `S8` costs no delivery at all — every hospital is still fully
served — but rerouting around it costs 347 more than the intact optimum. Since
satisfaction is 1.0, that 347 contains no shortage penalty: it is pure extra
shipping cost, and a genuinely interpretable number.

Note the CSV records only the **unprotected** evaluation. The protection plans and
timings appear in the printed summary and the returned dict, not in the file.

## Experiment 8 — Integrality

**Question.** How often does the continuous protection LP return a fractional
plan that whole units of capacity cannot match, and by how much?

**How.** [`run_integrality.py`](../run_integrality.py). For each γ in {1, 2},
generate `count` random networks from the *same* seed, solve the min-spend
problem at target 1.0 both continuously and with integer `extra` variables, and
record the difference.

**Verified output at count 10** (a reduced run; the shipped default is 1000):

```text
gamma=1: 10 instances, 10 feasible, 1 with integrality gap, max gap 1.0
gamma=2: 10 instances, 6 feasible, 1 with integrality gap, max gap 1.0
```

**Finding 1 — gaps are rare and tiny.** One of ten instances at each γ, with a
maximum gap of 1.0 cost unit against LP spends in the hundreds. The pinned
counterexample in `src/network.py` has a gap of 0.5 against a spend of 106.5 —
under half a percent.

This is consistent with the bound derived in
[Chapter 3](03-mathematical-model.md#the-gap-is-bounded): rounding an LP-optimal
plan up gives a feasible integer plan, so $0 \le \text{gap} < r|N|$.

**Finding 2 — Γ = 2 makes instances infeasible, not just expensive.** Four of the
ten instances had no feasible full-protection plan at all against paired
failures, because two simultaneous losses can disconnect a hospital — the same
structural-cut mechanism as `W1+W2` in the base network. Since both γ blocks use
the same seed, this is a **paired** comparison: instance 2 has LP spend 209.0 at
Γ = 1 and is `Infeasible` at Γ = 2.

**Finding 3 — the gaps occur on different instances.** At Γ = 1 the gap appeared
at index 2; at Γ = 2 at index 5. Whether an instance exhibits a gap depends on
the scenario family, not only on the network.

**Scope.** Ten instances is a validation run, not the experiment. The shipped
default of 1000 per γ would give a meaningful frequency estimate; this
documentation deliberately did not run it, and **no frequency claim is made
here** beyond "gaps exist and are small on the instances sampled."

## `results/integrality.csv`

**Generated by** [`run_integrality.py:15-24`](../run_integrality.py). **Rows:**
$2 \times \text{count}$, both γ blocks in one file. **Consumed by:** nothing
programmatic.

| Column | Type | Units | Range | Meaning |
|---|---|---|---|---|
| `gamma` | int | count | 1 or 2 | Uncertainty budget: how many nodes fail at once |
| `index` | int | — | 0 … count−1 | Position in the generated sequence; **comparable across γ** |
| `status` | str | — | `Optimal` / `Infeasible` | The **LP's** status |
| `lp_spend` | float or empty | cost | ≥ 0 | Continuous minimum spend |
| `ip_spend` | float or empty | cost | ≥ 0 | Integer minimum spend |
| `gap` | float or empty | cost | ≥ 0 | `ip_spend − lp_spend` |

The three numeric fields are empty when `status` is not `Optimal`, because
`csv.writer` renders `None` as an empty field.

**Reading two rows.**

```csv
1,2,Optimal,209.0,210.0,1.0
2,2,Infeasible,,,
```

Instance 2 of the generated sequence: if only one facility can fail, guaranteeing
full delivery costs 209.0 with divisible capacity and 210.0 with whole units — a
gap of 1.0, under half a percent. If *two* facilities can fail simultaneously, no
amount of extra capacity suffices on this network, so there is nothing to report.

## The figures

All four are tracked. Each is regenerated by `run.py:106-109`.

### `results/tradeoff.png`

| | |
|---|---|
| **Source data** | `singles` and `pairs` — the same data as `sweep.csv` |
| **x-axis** | Protection spend, 0 – 330, linear |
| **y-axis** | Worst-case demand satisfaction, rendered as a percentage |
| **Series** | Blue: worst single failure. Green: worst pair failure. Grey horizontal reference at 100% |
| **Annotations** | End labels "single" and "pair"; an automatic callout at the first point where the binding scenario changes, reading "binding failure becomes W1" |

**Interpretation.** The blue curve rises steadily to 100%; the green curve
flattens at 38.9% and stops responding to money. The gap between the two is the
cost of the extra failure, and the flat green tail is the topology-driven ceiling.

**Limitations.** The x-axis is spend under *uniform* protection only — the
optimized policy reaches the same guarantees for far less, which this figure does
not show. And the binding-failure annotation marks only the *first* switch; there
is exactly one on this instance, but a different network could have several and
only the earliest would be labelled.

### `results/frontier.png`

| | |
|---|---|
| **Source data** | `singles` (from `sweep.csv`) and `frontier` (from `frontier.csv`) |
| **x-axis** | Protection spend, 0 – 330 |
| **y-axis** | Worst-case demand satisfaction, as a percentage |
| **Series** | Blue: uniform protection. Green: optimized allocation (C&CG) |
| **Annotations** | End labels "uniform" and "optimized", the latter offset downward to avoid collision where the curves converge at 100% |

**Interpretation.** The green curve lies above the blue one at every spend level.
Read horizontally at 100%: optimized reaches it at 170, uniform at 330.

**Limitations.** The two series are **not sampled at comparable x-values** —
uniform is sampled at 11 fixed protection levels, optimized at 6 fixed
satisfaction targets. The visual comparison is valid because both are monotone
frontiers, but no individual pair of markers represents a controlled comparison.
Both curves also describe single failures only; neither can reach 100% against
pairs.

### `results/sensitivity.png`

| | |
|---|---|
| **Source data** | The five sweeps in `sensitivity.csv` |
| **x-axis** | Protection spend, 0 – 396 (the `capacity_x1.2` variant extends furthest) |
| **y-axis** | Worst-case demand satisfaction, as a percentage |
| **Series** | Three drawn: `capacity ×0.8`, `base`, `capacity ×1.2`. The two cost variants are **omitted** because they coincide exactly with the base |
| **Annotations** | The base legend entry reads `base (cost ×0.8, cost ×1.2 coincide)` |

**Interpretation.** The folded legend entry is itself a finding: shipping cost
has literally zero effect on worst-case satisfaction. The three visible curves are
parallel in character — same concavity, same qualitative behaviour — so the
conclusions are properties of the topology rather than of the specific numbers.

**Limitations.** One-factor-at-a-time, on one instance, over two parameters. The
penalty, the protection cost rate, and the network structure were not varied.

### `results/network.png`

| | |
|---|---|
| **Source data** | `base_network()` |
| **Layout** | Four columns, one per tier, laid out by `_node_positions` ([`src/plots.py:210-218`](../src/plots.py)) |
| **Node labels** | Name and value — capacity for S/F/W, demand for H |
| **Node colours** | One per tier, 14% opacity fill with a full-strength border |
| **Arc labels** | Unit shipping cost, staggered along each arc to reduce overlap |
| **Annotations** | Column headers naming each tier and its value type; a caption reading "arc labels: unit shipping cost" |

**Interpretation.** This is the reference figure for every structural claim in the
project. In particular it makes visible that `H1` and `H2` each connect only to
`W1` and `W2` — the cut behind the pair-failure plateau.

**Limitations.** The axis limits are hard-coded for the base network's 3/3/3/4
shape ([`src/plots.py:294-295`](../src/plots.py)), so the function is not usable
for the generated networks without modification. Arcs are drawn as straight lines
with no crossing minimisation.

## Documentation discrepancies

The root `README.md` was written before the generator, integrality, and scaling
work was added, and some of its statements have drifted. **All of its numerical
results tables were re-verified during this pass and match the current code
exactly** — the sweep table, the frontier table, the allocation table, and the
normal-versus-robust table are all correct. The discrepancies below are in the
surrounding prose and inventory.

Each entry states both versions without choosing between them.

### D1 — Test count

| Source | Claim |
|---|---|
| `README.md:339` | "The test suite (42 tests)" |
| Measured | `pytest -q` → **55 passed** in 68.35 s |

The 13 extra tests are in `test_generator.py` (4), `test_integrality.py` (5),
`test_paradox.py` (2), and `test_run_scaled.py` (2) — precisely the modules the
README's repository-layout table also omits (D4). The README figure appears to
predate that work.

### D2 — LP solve count

| Source | Claim |
|---|---|
| `README.md:119`, `README.md:329` | "approximately 1,100 LP solves for the whole pipeline" |
| Measured | **1,623** `LpProblem.solve` calls, counted by patching PuLP and running `main` into a temp directory |

The three sweep stages alone account for $110 + 407 + 550 = 1{,}067$, which does
round to "approximately 1,100". The remaining 556 are the frontier loop (444),
the duplicated `ccg_plan` (89), the normal/robust evaluation (20), and the
paradox (3). The README's figure is consistent with counting only the sweeps.

### D3 — Artifact inventory

| Source | Claim |
|---|---|
| `README.md:331-337` | Lists `sweep.csv`, `frontier.csv`, `plans.csv`, `sensitivity.csv`, and the four PNGs |
| Code | [`run.py:98-104`](../run.py) also writes **`paradox.csv`** |

`paradox.csv` is missing from the table. `scaled.csv` and `integrality.csv` are
also absent, though those come from other scripts the table does not claim to
cover.

### D4 — Repository layout table

| Source | Claim |
|---|---|
| `README.md:351-361` | Lists 9 paths |
| Working tree | Also contains `run_scaled.py`, `run_integrality.py`, `src/generator.py`, `src/integrality.py` |

Four tracked source files are undocumented in that table.

### D5 — C&CG scenario counts

| Source | Claim |
|---|---|
| `README.md:284-286` | "In the case of targets near 100% satisfaction for single-failures, enumeration of all nine scenarios is performed, since all single failures bind the solution." |
| Measured | At $\tau = 1.0$: **9 iterations, but only 8 scenarios added.** `W3` is never added to the master. |

The oracle *evaluates* all nine scenarios on every iteration — so in that sense
enumeration does occur — but eight are added to the master and `W3`'s constraint
turns out to be implied by the others.

A related conflation: `README.md:282-284` says "For medium targets, C&CG needs
2–4 scenarios out of nine" and "for the pairs, only 4 out of 36 scenarios are
needed". Those figures are **iteration counts**, not scenario counts. Since the
final iteration adds nothing, the scenario counts are one lower: targets 0.75 and
0.80 add 1 and 3 scenarios; the pair case at $\tau = 0.35$ runs 4 iterations and
adds **3** of the 36 scenarios (verified directly).

### D6 — Binding failure at $p = 0.50$

| Source | Claim |
|---|---|
| `README.md:204` | Binding failure shown as "—" |
| `sweep.csv` | `worst_scenario_single` records **`S1`** |

At $p = 0.50$ every scenario reaches satisfaction 1.0, so `worst_case`
([`src/experiment.py:39-40`](../src/experiment.py)) returns the first row in list
order. The README's dash is a defensible editorial choice — there is genuinely no
binding failure — but it does not match the generated file, and a reader
comparing the two will see a difference.

### D7 — The "uniform spend for same guarantee" column

| Source | Claim |
|---|---|
| `README.md:228-237` | A column of values ≈25, ≈71, ≈117, ≈162, ≈229, 330, footnoted "Linear interpolation of the uniform protection sweep in `sweep.csv`" |
| Code | **No function computes this.** It is a manual derivation. |

The footnote is honest about the method. Noted here because the column looks like
generated output and is not; it cannot be regenerated by running anything, and it
is not checked by any test.

### D8 — Runtime

| Source | Claim |
|---|---|
| `README.md:328` | "`run.py` regenerates every artifact in `results/` in about two minutes" |
| Measured | **≈36 seconds** on the verification machine (Python 3.14.3, Windows 11) |

Wall-clock time is hardware- and solver-dependent. This is recorded for
completeness, not as an error.

### D9 — Python version

| Source | Claim |
|---|---|
| `README.md:320` | "Requires Python 3.11+" |
| `.github/workflows/ci.yml:15` | Tests only on 3.12 |
| This pass | Full suite passed on 3.14.3 |

Not a contradiction. Noted because the claimed support range is broader than
anything automatically verified: only 3.12 is checked on every commit.

---

Previous: [Chapter 5 — File-by-file guide](05-file-by-file-guide.md) ·
Next: [Chapter 7 — Testing and validation](07-testing-and-validation.md)
