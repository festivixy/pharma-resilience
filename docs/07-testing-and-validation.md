# Chapter 7 — Testing and validation

**55 tests across 12 files, all passing** (`pytest -q` → `55 passed in 66.84s`,
confirmed 2026-08-05 on Python 3.14.3).

Tests for optimization code are harder than ordinary ones, because the
"expected value" returned by a solver call is typically something that cannot be
written down by hand. This chapter outlines the strategy adopted by the suite to
deal with that problem, then goes through the tests by concern.

## How do you test code whose answers come from a solver?

If a test says `solve(net)["cost"] == 940.0`, what has it really verified? A
valid model? Only that CBC behaves just like it did when that number was copied
down? Six techniques have been used to make that difference relevant.

### 1. Hand-computable oracles

The best tests involve inputs that are small enough for the optimum to be
obvious even without a solver. `toy_chain` in
[`tests/test_model.py:9-20`](../tests/test_model.py) is a four-node chain with
**only one path available**:

```python
"capacity": {"S": supplier_cap, "F": 10, "W": 10},
"demand":   {"H": 10},
"arc_cost": {("S","F"): 1, ("F","W"): 2, ("W","H"): 3},
```

One path means no decisions need to be made about how to ship the goods. Ten units
at the cost of $1 + 2 + 3 = 6$ must incur 60 in total. Cap the supplier's
capacity at 4, and 4 units will go through at cost 24, with another 6 going
unsatisfied at a penalty of 1000, meaning the total cost is $24 + 6000 = 6024$ —
and the test `test_toy_chain_shortage_when_supply_capped`
([lines 31-36](../tests/test_model.py)) asserts precisely this breakdown.
Failure here means the model is incorrect, not that an answer drifted.

### 2. Model properties that must be true for any correct solver

Certain relationships hold regardless of which optimum the solver returns.
`test_sweep_worst_case_improves_with_protection`
([`tests/test_experiment.py:77-87`](../tests/test_experiment.py)) asserts

```python
assert satisfactions == sorted(satisfactions)
```

Increased capacity cannot worsen the worst case — the feasible region only grows.
This is a theorem about the model, and it detects a whole class of bugs (sign
error in `apply_protection`, stale network leaking between iterations) without
requiring any particular numeric value.

Others in this category: `min_fill_rate <= satisfaction`
([`tests/test_experiment.py:66`](../tests/test_experiment.py)), non-negative
recovery cost (line 57), pairwise satisfaction cannot exceed single-satisfaction
([`tests/test_run.py:25`](../tests/test_run.py)), and robust satisfaction is
never below normal ([`tests/test_run.py:34-37`](../tests/test_run.py)).

### 3. Cross-validation of a quantity computed by two independent algorithms

`test_ccg_matches_exhaustive_lp_spend`
([`tests/test_robust.py:54-62`](../tests/test_robust.py)) computes the same
quantity by two algorithms — a single huge LP encompassing all nine scenarios,
and an iterative loop that works with up to eight scenarios at a time — and
asserts that both yield the same result to `1e-4`.

Neither of these results is a hard-coded constant. If the model were incorrect,
both algorithms would be affected the same way and the test would pass; however,
if there is a bug in the C&CG *loop* (stopping condition off-by-one, duplicate
scenarios, wrong allocation propagation) — the two will immediately diverge. This
is the test that validates the project's key algorithmic claim.

### 4. Independent verification of the solver's own claim

The suite never takes a solver at its word. `min_spend_plan` claims "this
allocation provides satisfaction $\ge \tau$ for all scenarios". The auxiliary
function `worst_satisfaction` at
[`tests/test_robust.py:10-14`](../tests/test_robust.py) verifies that claim by
feeding the allocation back into `solve` on every scenario separately —
essentially running the same solver on a completely independent model in another
module.

```python
def worst_satisfaction(network, extra, scenarios):
    protected = apply_allocation(network, extra)
    return min(solve(fail_nodes(protected, nodes))["satisfaction"] for nodes in scenarios)
```

Same idea is used in `test_pinned_counterexample_fractional_plan_is_feasible`
([`tests/test_integrality.py:43-49`](../tests/test_integrality.py)) — where the
LP's *fractional* solution plan is fed back through `solve` for every scenario,
so that the 0.5-unit gap can be asserted as a mathematical property, rather than
a numerical one caused by the solver. And `run.py` does this for the C&CG plans
in production — as
[`run.py:53`](../run.py) runs `evaluate_scenarios` on each one.

### 5. Pinned regression values

Several exact numbers are pinned down in: the LP spend 170.0 on the base network
([`tests/test_integrality.py:15`](../tests/test_integrality.py)), 106.5 / 107.0
/ 0.5 on the counterexample (lines 38-40), the uniform spend 330.0, that
the optimizer should beat ([`tests/test_robust.py:44-45`](../tests/test_robust.py)).

They are the weakest individual tests — they will pass if the model is wrong too.
However, their value lies in being **change detectors**: modify any capacity in
`src/network.py` and they will fail loudly — exactly what is desired when
all published figures depend on those values.

### 6. Property-style and determinism checks

[`tests/test_generator.py`](../tests/test_generator.py) does not verify any
particular network. It verifies *properties* over 20 seeds: arcs are only
between adjacent tiers, nodes have required degree, capacities and demands are
positive. This is the proper shape of test for a randomized generator.

Determinism is tested in three places — `test_same_seed_gives_same_network`,
`test_experiment_is_deterministic`, and `test_scaled_run_is_deterministic` —
since reproducibility claims throughout the repo rely on it.

### What the suite does not test

- **Correctness of CBC itself.** That is assumed.
- **Visual aspect of plots.** Only that the files are generated and non-empty.
  There is no visual comparison test, so a plot could have swapped axes and still
  pass.
- **Large-network numerical conditioning.** The largest tested network is
  12/12/12/15 and it is checked only for schema validity, not for a solver run.
- **`run_integrality.py` as a script.** Only the underlying functions are tested.
- **Any Python version except 3.12** (in CI).

## Tests by concern

### Solver correctness — [`tests/test_model.py`](../tests/test_model.py) (7 tests)

**Fixture.** `toy_chain(supplier_cap)` — a 4-node network with only one path
available, so that the optimum can be computed by hand.

| Test | Lines | Verifies | Why it matters | Type |
|---|---|---|---|---|
| `test_toy_chain_exact_cost` | 23-28 | 10 units × 6 = 60, status Optimal, satisfaction 1.0 | Objective computes the shipping cost correctly | Unit |
| `test_toy_chain_shortage_when_supply_capped` | 31-36 | Cost decomposes as $4 \times 6 + 1000 \times 6$ | Both the shipping and the penalty terms are there and have proper weights | Unit |
| `test_baseline_meets_all_demand` | 39-43 | With intact base network → satisfaction 1.0, all `unmet` zero | Calibration invariant: its first part; if the baseline is messed up, everything is messed up | Regression |
| `test_solve_does_not_mutate_input` | 46-50 | Deepcopy of the input equals the input after solve | `solve` is called 1,623 times per run on shared dicts | Unit (purity) |
| `test_destroyed_node_reports_shortage_not_infeasible` | 53-58 | Zeroed capacity → status Optimal, satisfaction < 1 | **The choice of the slack-vs-shortage design.** Without slack this fails and reports `Infeasible`, making the whole project collapse | Unit |
| `test_min_fill_rate_matches_satisfaction_for_single_hospital` | 61-63 | For one hospital the two metrics are equivalent | Sanity anchor for the equity formula | Unit |
| `test_min_fill_rate_is_zero_when_a_hospital_is_disconnected` | 66-72 | Destroy `W1` and `W2` → satisfaction > 0.3 but min fill rate is 0 | **Average vs. minimum metric divergence** in its most extreme form; also probes the `W1`+`W2` structural disconnect | Unit |

### Network calibration — [`tests/test_network.py`](../tests/test_network.py) (7 tests)

They guard the data, not the code. All published figures depend on them.

| Test | Lines | Verifies | Why it matters | Type |
|---|---|---|---|---|
| `test_total_demand_is_180` | 4-6 | $\sum d_h = 180$ | The denominator of every satisfaction figure | Regression |
| `test_arcs_reference_known_nodes` | 9-14 | Arcs reference only existing nodes | Mistyped source node would be an **unlimited free supply**, increasing satisfaction | Unit |
| `test_arcs_only_connect_adjacent_tiers` | 17-26 | Only S→F, F→W, W→H | `solve` does not enforce layering; a shortcut arc would bypass capacity constraints | Unit |
| `test_every_hospital_has_two_sources` | 29-33 | Hospital in-degree is at least 2 | Guarantees that there is no single failure that can disconnect a hospital, so that the single-failure study makes sense | Unit |
| `test_every_non_hospital_node_has_capacity` | 36-39 | Positive capacity for all S/F/W | Prevents a `KeyError` at `src/model.py:23` | Unit |
| `test_each_tier_can_cover_demand_but_not_after_worst_loss` | 42-47 | $\sum u \ge 180$ and $\sum u - \max u < 180$ per tier | **The calibration invariant.** The two parts guarantee a clean baseline *and* an interesting resilience question | Regression |
| `test_base_network_returns_fresh_copies` | 50-54 | Mutating one result does not affect the others | `base_network()` uses shallow `dict()`/`list()`, so this is not obvious | Unit (purity) |

### Transformation purity — distributed over three files

Five functions clone their input. They have a unit test that clones the input and
asserts equality after the function runs.

| Function | Test | Location |
|---|---|---|
| `fail_nodes` | `test_fail_nodes_zeroes_capacity_without_mutating_original` | [`tests/test_experiment.py:25-31`](../tests/test_experiment.py) |
| `apply_protection` | `test_apply_protection_scales_all_capacities` | [`tests/test_experiment.py:34-40`](../tests/test_experiment.py) |
| `apply_allocation` | `test_apply_allocation_adds_extra_capacity_without_mutation` | [`tests/test_robust.py:17-22`](../tests/test_robust.py) |
| `scale_costs` | `test_scale_costs_only_touches_arc_costs` | [`tests/test_sensitivity.py:10-15`](../tests/test_sensitivity.py) |
| `scale_capacities` | `test_scale_capacities_only_touches_capacities` | [`tests/test_sensitivity.py:18-23`](../tests/test_sensitivity.py) |

**Why this is a first-class concern.** These functions run within nested loops
iterating over the *same* base network — 11 protection levels × 37 scenarios × 5
variants. A leaked mutation will not crash anything. It will generate a consistent
set of plausible-looking, monotonic, publishable numbers that are silently wrong,
with level 0.10 contaminated by level 0.05. No output value assertion will detect
it — only purity tests do.

The two sensitivity tests also assert **isolation**: `scale_costs` must not touch
`capacity` and vice versa. Without that, "cost sensitivity" and "capacity
sensitivity" would be confounded and the analysis meaningless.

### Scenario enumeration — [`tests/test_scenarios.py`](../tests/test_scenarios.py) (2 tests)

| Test | Lines | Verifies | Type |
|---|---|---|---|
| `test_single_failures_cover_all_non_hospital_nodes` | 5-11 | Exactly 9, covering S∪F∪W, each a **1-tuple** | Unit |
| `test_pair_failures_are_all_combinations` | 14-21 | Exactly 36, all distinct as frozensets, no hospitals | Unit |

The assertion about 1-tuples is important: the common form of a scenario allows
`fail_nodes` to iterate over them without special case for singles. The
`frozenset` distinctness test ensures `combinations` did not produce ordered
pairs — that `("S1","S2")` and `("S2","S1")` are not both in the list, so that
36 unique pairs are not double-counted into 72.

### Uniform protection and evaluation — [`tests/test_experiment.py`](../tests/test_experiment.py) (8 tests)

| Test | Lines | Verifies | Why it matters | Type |
|---|---|---|---|---|
| `test_calibration_every_single_failure_causes_shortage` | 18-22 | All 9 failures yield satisfaction < 1.0 | **Second part of the calibration invariant.** If any failure would not cause shortages, the resilience question would be vacuous for that node | Regression |
| `test_fail_nodes_...` | 25-31 | Purity of `fail_nodes` | see above | Unit |
| `test_apply_protection_scales_all_capacities` | 34-40 | Purity and correctness of scaling | see above | Unit |
| `test_protection_spend_is_linear_in_level` | 43-49 | Spend(0) = 0 and spend is $r \cdot p \cdot \sum u$ | X axis of all trade-off figures | Unit |
| `test_evaluate_scenarios_reports_nonnegative_recovery_cost` | 52-58 | 9 rows; `recovery_cost >= -1e-6`; `0 <= satisfaction < 1` | The `-1e-6` acknowledges rounding honestly | Unit |
| `test_evaluate_scenarios_reports_cost_and_equity` | 61-66 | `cost > 0`; `min_fill_rate <= satisfaction` | Mathematical relation between average and minimum | Unit |
| `test_worst_case_picks_minimum_satisfaction` | 69-74 | Picks by satisfaction, not by cost | Uses hand-written fixture, without a solver — the only pure-logic test in the suite | Unit |
| `test_sweep_worst_case_improves_with_protection` | 77-87 | Monotonic satisfaction and spend; satisfaction reaches 1.0 at level 0.5 | **Shape of the headline result**, and leak detector across sweep iterations | Integration |

### Robust optimization and C&CG — [`tests/test_robust.py`](../tests/test_robust.py) (7 tests)

**Helper.** `worst_satisfaction(network, extra, scenarios)` at lines 10-14 —
independent verifier as described [above](#4-independent-verification-of-the-solvers-own-claim).

| Test | Lines | Verifies | Why it matters | Type |
|---|---|---|---|---|
| `test_apply_allocation_adds_extra_capacity_without_mutation` | 17-22 | `S1: 80 → 95` with `extra={"S1": 15}`; `S2` unchanged | Allocation is done **additively** (unlike `apply_protection`, which is multiplicative) and only affects named nodes | Unit |
| `test_target_below_unprotected_worst_case_costs_nothing` | 25-29 | Target 0.7 → spend exactly 0.0 | The LP does not pay for protection it does not need — basic optimality sanity check | Unit |
| `test_full_protection_plan_survives_every_single_failure` | 32-38 | Target 1.0 → spend > 0 **and** independently verified satisfaction = 1.0 | Does not take the solver at its word | Integration |
| `test_optimized_allocation_beats_uniform_protection` | 41-45 | Optimized spend < 330.0 | **The headline claim** of the project, stated as an assertion | Regression |
| `test_pair_target_above_topology_limit_is_infeasible` | 48-51 | Pairwise at target 1.0 → status `Infeasible` | **The topology limit.** Ensures the model is capable of reporting an impossible situation, rather than generating an invalid plan | Regression |
| `test_ccg_matches_exhaustive_lp_spend` | 54-62 | C&CG spend = LP spend to `1e-4`, at targets 0.9 and 1.0, with independent verification | **Proof of C&CG correctness** at this network size | Integration |
| `test_ccg_converges_without_enumerating_all_scenarios` | 65-71 | Pairwise at target 0.35 → `iterations <= 5` and `< 36` | **Efficiency of C&CG.** Deliberately loose (the actual value is 4) so that it does not break on a tie break change | Integration |

Note the two parts of the last two tests: the first asserts that C&CG finds the
*right answer*, the other that it does not enumerate all the scenarios in order
to do that. Together they make the whole algorithmic argument.

### Sensitivity transformations — [`tests/test_sensitivity.py`](../tests/test_sensitivity.py) (5 tests)

**Fixture.** `LEVELS = [0.0, 0.25, 0.5]` — a coarse three-point sweep, since the
purpose of these tests is to verify directionality, not resolution.

| Test | Lines | Verifies | Why it matters | Type |
|---|---|---|---|---|
| `test_scale_costs_only_touches_arc_costs` | 10-15 | Costs are scaled, capacities are unchanged | Isolation — see above | Unit |
| `test_scale_capacities_only_touches_capacities` | 18-23 | Capacities are scaled, arc costs are unchanged | Isolation | Unit |
| `test_run_sensitivity_returns_all_variants` | 26-31 | 5 variants, each with correct length | Variant names become legend labels | Unit |
| `test_cost_scaling_leaves_satisfaction_curve_unchanged` | 34-40 | Satisfaction curves for cost variants equal the base curve | **Encodes the penalty-dominance prediction as an executable assertion.** If someone lowers the penalty to 5, this test will fail and explain why | Regression |
| `test_capacity_scaling_shifts_curve_in_right_direction` | 43-48 | Capacity ×1.2 ≥ base ≥ capacity ×0.8 at level 0 | Direction, not magnitude; robust to solver differences | Unit |

### Random generator properties — [`tests/test_generator.py`](../tests/test_generator.py) (4 tests)

| Test | Lines | Verifies | Type |
|---|---|---|---|
| `test_same_seed_gives_same_network` | 8-11 | Two `Random(7)` generate the same networks | Determinism |
| `test_explicit_sizes_control_tier_widths` | 14-19 | `sizes=(6,5,7,9)` generates exactly those widths | Unit |
| `test_large_network_keeps_valid_schema` | 22-28 | At 12/12/12/15: every downstream node has an incoming arc, all capacities ≥ 1 | Property-style |
| `test_generated_network_has_valid_schema` | 31-49 | **Over 20 seeds:** every tier has ≥ 2 nodes, positive capacities and demands, `tier[dst] == tier[src] + 1` for all arcs, all non-sinks have outgoing arc, all non-sources have incoming arc | Property-style |

Test over 20 seeds is the most valuable in the file. It captures all structural
promises of the generator and would detect a regression in two-pass arc
generation logic at
[`src/generator.py:18-30`](../src/generator.py) — specifically, dropping the
repair pass will eventually lead to a downstream node getting stranded and
breaking the in-degree assertion on some seed.

### Equity paradox — [`tests/test_paradox.py`](../tests/test_paradox.py) (2 tests)

| Test | Lines | Verifies | Type |
|---|---|---|---|
| `test_unprotected_instance_splits_delivery_across_hospitals` | 8-12 | Satisfaction 0.5, equity 0.4 | Regression |
| `test_optimal_protection_raises_satisfaction_but_collapses_equity` | 15-21 | `satisfaction > 0.5` **and** `min_fill_rate < 0.4` | Regression |

The latter is unusual and needs explanation: it is a test asserting that the code
makes something **worse**. It pins down the limitation of the model — the
aggregate target constraint at [`src/robust.py:55`](../src/robust.py) bounds the
*total* unmet demand and says nothing about how the shortfall is distributed. If
somebody later adds an equity constraint, this test will fail and force a
conscious decision instead of the finding being silently deleted.

The assertions are directional (`> 0.5`, `< 0.4`) rather than exact, so they
survive solver tie-breaking while still pinning the phenomenon.

### Integrality behaviour — [`tests/test_integrality.py`](../tests/test_integrality.py) (5 tests)

| Test | Lines | Verifies | Why it matters | Type |
|---|---|---|---|---|
| `test_base_instance_has_no_integrality_gap` | 11-16 | LP spend exactly 170.0, gap 0 | Pins the headline optimized-protection figure **and** shows the base network has no gap | Regression |
| `test_experiment_runs_seeded_batch` | 19-26 | 8 instances, `0 <= feasible <= 8`, non-negative gaps | Smoke test of the batch loop, tolerant of infeasible draws | Integration |
| `test_experiment_is_deterministic` | 29-32 | Two identical calls return equal dicts | The reproducibility claim | Determinism |
| `test_pinned_counterexample_has_fractional_gap` | 35-40 | 106.5 / 107.0 / 0.5 exactly | **The existence proof** that a gap can occur | Regression |
| `test_pinned_counterexample_fractional_plan_is_feasible` | 43-49 | The fractional plan gives satisfaction 1.0 on every scenario, verified via `solve` | Proves the gap is a real mathematical property, not a solver artefact | Integration |

The last two work as a pair. The first says the numbers differ; the second says
that the smaller one is genuinely achievable in the LP's world. Without the second, a
sceptic could dismiss 106.5 as CBC noise.

### Plotting — [`tests/test_plots.py`](../tests/test_plots.py) (5 tests)

**Fixtures.** Three hand-built two-row sweeps at lines 10-29 (`SWEEP`,
`PAIR_SWEEP`, `SHIFTED`) and a two-row `FRONTIER` at lines 54-57. They carry
realistic keys and values but require no solver, so the plotting tests run in
milliseconds.

Note `SHIFTED` differs from `SWEEP` in its satisfaction values while `PAIR_SWEEP`
differs in scenario names too — the fixtures are designed to exercise both the
coincidence-folding path and the binding-failure annotation path.

| Test | Lines | Verifies | Type |
|---|---|---|---|
| `test_tradeoff_plot_writes_file` | 32-36 | File exists and is non-empty | Smoke |
| `test_sensitivity_plot_writes_file` | 39-46 | Same, with a coinciding variant present | Smoke |
| `test_coinciding_variants_folds_identical_curves_only` | 49-51 | Returns `["cost_x1.2"]` — the exact duplicate — and **not** `capacity_x0.8` | Unit |
| `test_frontier_plot_writes_file` | 60-64 | Same, mixing sweep and frontier row schemas | Smoke |
| `test_network_diagram_writes_file` | 67-71 | Renders the real base network | Smoke |

The smoke tests cannot detect a wrong-looking figure. What they *can* detect is
the failure mode that actually occurs: a `KeyError` or `IndexError` from a
changed row schema, or a backend crash on a headless machine. The `Agg` backend
line ([`src/plots.py:3`](../src/plots.py)) is what makes them feasible in CI at
all.

`test_coinciding_variants_folds_identical_curves_only` is the only real unit test
here, and it checks both directions: the duplicate is folded, and the merely
*similar* curve is not.

### Runner output — [`tests/test_run.py`](../tests/test_run.py) (1 test)

One test, but the broadest in the suite. `test_main_writes_all_outputs`
([lines 11-47](../tests/test_run.py)) runs the entire pipeline into `tmp_path`
and then asserts across four CSVs.

| Check | Lines | What it establishes |
|---|---|---|
| All 9 artifacts exist | 13-18 | Nothing silently stopped being written |
| `sweep.csv` has `len(LEVELS)` rows | 20-21 | Row count tracks the constant, not a literal |
| First single-failure satisfaction < 1.0, last ≥ 0.999 | 22-23 | The curve starts vulnerable and reaches full protection |
| Pair satisfaction ≤ single satisfaction, every row | 24-25 | **A cross-experiment invariant**: two failures cannot be better than one |
| `frontier.csv` last row ≥ 0.999 and spend < 330.0 | 27-29 | Optimized reaches full protection **and beats uniform** |
| `plans.csv` has 9 rows, robust ≥ normal satisfaction in each | 31-37 | Protection never hurts, scenario by scenario |
| `paradox.csv`: protected satisfaction up, min fill rate down | 39-47 | The paradox survives end to end |

The pair-versus-single check at line 25 is the most interesting: it relates two
independently computed sweeps, so it would catch a mix-up between the `singles`
and `pairs` variables in `run.py` that no single-sweep test could spot.

This test also accounts for roughly 60% of the suite's runtime — it performs all
1,623 LP solves of a complete `run.py`.

### Scaled runner — [`tests/test_run_scaled.py`](../tests/test_run_scaled.py) (2 tests)

**Fixture.** `sizes=(3, 3, 3, 3)` — the smallest size the generator accepts,
keeping the test fast.

| Test | Lines | Verifies | Type |
|---|---|---|---|
| `test_scaled_run_writes_outputs_and_matches_ccg_to_full_lp` | 6-11 | CSV written; `ccg_spend == full_spend` to `1e-4`; satisfaction ≤ 1.0; `iterations >= 1` | Integration |
| `test_scaled_run_is_deterministic` | 14-18 | Two runs at seed 5 agree on four summary keys | Determinism |

The first extends the C&CG-equals-full-LP result from the *hand-built* network to
a *generated* one — evidence the agreement is a property of the algorithms rather
than of the specific instance. `iterations >= 1` is worth mentioning: C&CG always
runs at least one oracle pass, even when zero protection already suffices.

## Running the tests

```bash
pytest                      # full suite, verbose default output
pytest -q                   # quiet: one dot per test, then a summary line
pytest tests/test_model.py  # one file
```

| Command | Output | When |
|---|---|---|
| `pytest` | Per-test names and a summary | Default; readable failures |
| `pytest -q` | `55 passed in 66.84s` | CI-style, minimal noise |
| `pytest tests/test_model.py` | 7 tests, about a second | Iterating on the LP |

Useful additions, none of which are configured in the repository:

```bash
pytest -x                              # stop at the first failure
pytest -k "ccg or integrality"         # select by name substring
pytest --durations=5                   # find the slow tests
pytest tests/ --ignore=tests/test_run.py   # skip the 1,623-solve integration test
```

The last is worth remembering: `test_run.py` alone takes almost 2/3 of the total
suite time. As measured on the verification machine, the full suite is 55 tests
in ~67 s; excluding `test_run.py` it is 54 tests in **~25 s**. That single test
therefore consumes roughly 60% of the wall clock, because it performs all 1,623
LP solves of a complete `run.py`. Excluding it is the right inner loop while
editing `src/`; including it is necessary before committing.

## `pytest.ini`

```ini
[pytest]
filterwarnings =
    ignore:.*PuLP 4.0.*:DeprecationWarning
```

Three lines, two effects.

**The explicit effect** is filtering PuLP 3.3.2's `DeprecationWarning` about
upcoming 4.0 API changes. Across 1,600+ solver calls this would otherwise bury
real output. The filter matches on the *message* text, so if PuLP rewords the
warning the filter stops applying.

**The implicit effect is more important.** The presence of `pytest.ini` at the
repository root is what makes pytest use it as its **rootdir**, which includes
this directory on `sys.path`, which is what makes `from src.model import solve` and
`from run import main` imports possible. There is no `conftest.py`, no `pyproject.toml`,
and no installed package. **Remove `pytest.ini` and the entire suite fails at
import.**

Not configured: coverage thresholds, custom markers, `testpaths`, or parallel
execution.

## Continuous integration

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml), 17 lines:

```yaml
name: ci
on:
  push:
    branches: [main]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: pytest
```

```mermaid
flowchart LR
    accTitle: Continuous Integration Workflow
    accDescr: A push to main or any pull request triggers a job on ubuntu-latest that checks out the repository, sets up Python 3.12, installs pinned requirements, and runs pytest.

    trig["push to main<br/>or any pull request"]
    co["actions/checkout@v4"]
    py["actions/setup-python@v5<br/>version 3.12"]
    dep["pip install -r requirements.txt"]
    test["pytest"]
    res["pass / fail check"]

    trig --> co --> py --> dep --> test --> res

    classDef step fill:#dbeafe,stroke:#2563eb,color:#1e3a5f
    classDef out fill:#dcfce7,stroke:#16a34a,color:#14532d

    class trig,co,py,dep step
    class test,res out
```

**Why it works without a solver install.** PuLP bundles a CBC binary in its
wheel, so `pip install -r requirements.txt` is sufficient. No `apt-get`, no
`conda`, no solver licence.

**Why it works headless.** `matplotlib.use("Agg")` at
[`src/plots.py:3`](../src/plots.py). Without it the plotting tests would fail on
a machine with no display.

**Design choices and their consequences.**

| Choice | Consequence |
|---|---|
| Single OS (`ubuntu-latest`) | Windows and macOS path or line-ending issues would not be caught. This documentation pass ran the suite on Windows 11 — 55 passed |
| Single Python version (3.12) | The README's "3.11+" claim is not verified for 3.11, 3.13, or 3.14 by CI. Verified manually on 3.14.3 here |
| No pip cache | Every run reinstalls matplotlib; slower, but always a clean environment |
| No coverage gate | Nothing enforces a coverage threshold |
| Tests only; no experiment run | CI verifies correctness, not that figures still regenerate. `test_run.py` does run the full pipeline, so this gap is largely covered |
| No artifact upload | Failure diagnosis relies on the log |

---

Previous: [Chapter 6 — Experiments and results](06-experiments-and-results.md) ·
Next: [Chapter 8 — Extension guide](08-extension-guide.md)
