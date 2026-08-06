# Chapter 5 — File-by-file guide

Every tracked file in the repository, in the order they appear in
`git ls-files`. Source modules and runners get the full treatment; test files
are summarised here and covered in depth in
[Chapter 7](07-testing-and-validation.md).

Line references were recalculated from the working tree and are accurate as of
2026-08-05.

---

## `.github/workflows/ci.yml`

**Purpose.** Run the test suite automatically on GitHub so a broken commit is
caught without anyone running `pytest` locally.

**Responsibilities.** It owns *when* tests run and *in what environment*. It does
not own what the tests check, and it deliberately does not run the experiment
scripts — CI verifies correctness, not reproduction of figures.

**Important symbols.**

| Element | Value | Note |
|---|---|---|
| `name` | `ci` | Workflow display name |
| `on.push.branches` | `[main]` | Runs on every push to `main` |
| `on.pull_request` | (no filter) | Runs on every PR against any branch |
| `runs-on` | `ubuntu-latest` | Single OS; no matrix |
| `python-version` | `"3.12"` | Pinned as a string so YAML does not read it as the float 3.12 |

**Inputs and outputs.** Input: the repository at the pushed commit. Output: a
pass/fail check. No artifacts are uploaded.

**Dependencies.** `actions/checkout@v4`, `actions/setup-python@v5`, then
`pip install -r requirements.txt` and `pytest`.

**Execution role.** Only reached in CI; never during local work.

**Assumptions and edge cases.** Assumes CBC works out of the box on
`ubuntu-latest` — true because PuLP bundles a CBC binary, so no `apt-get` step is
needed. There is no dependency cache, so every run reinstalls matplotlib from
scratch. There is no Python version matrix: the suite is verified on 3.12 in CI
and was verified on 3.14.3 during this documentation pass, but no other version
is checked automatically.

**Related tests.** None — this file *runs* the tests.

---

## `.gitignore`

**Purpose.** Keep generated data, environments, and editor state out of version
control while preserving the figures the research report links to.

**Responsibilities.** It owns which artifacts are tracked. This is a real
modelling decision, not housekeeping: it is why `results/` contains PNGs but no
CSVs.

**Important symbols.** The three rules that matter for this project:

```gitignore
*.csv          # line 57 — no CSV anywhere in the repo is tracked
results/*      # line 68 — ignore everything under results/
!results/*.png # line 69 — except PNG files
```

**Execution role.** Consulted by git, never by Python.

**Assumptions and edge cases.** The consequence is that **`results/*.csv` is
generated, never committed**. A fresh clone has four PNGs and no CSVs, and the
tables in the root `README.md` cannot be checked against a tracked file until
someone runs `python run.py`. The `*.csv` rule at line 57 is repository-wide, so
it would also silently ignore any CSV added under `docs/` or `tests/`.

Line 105 ignores `.claude/`, and line 115 ignores `claude.md` — note that this
rule is lowercase, and on a case-sensitive filesystem it would not match
`CLAUDE.md`.

**Related tests.** None.

---

## `README.md`

**Purpose.** The research report: abstract, model, results, findings,
limitations, references. It argues a conclusion.

**Responsibilities.** It owns the *narrative and the claims*. It does not own
implementation reference material — that is what `docs/` is for.

**Important symbols.** Sections: Overview, Research question, Network instance,
Mathematical model, Disruption model, Protection models,
Column-and-constraint generation, Metrics, Results, Sensitivity analysis,
Limitations and scope, Reproducibility, Repository layout, References.

**Execution role.** Documentation only.

**Assumptions and edge cases.** Several statements have drifted from the code as
the repository grew. They are enumerated with evidence in
[Chapter 6](06-experiments-and-results.md#documentation-discrepancies) — in
summary: the test count, the LP-solve count, the artifact table, and the
repository-layout table all predate the generator, integrality, and scaling work.
The numerical results tables were re-verified during this documentation pass and
**all of them match the current code exactly**.

**Related tests.** None.

---

## `pytest.ini`

**Purpose.** Mark the repository root as the pytest rootdir, and silence one
known-noisy warning.

**Responsibilities.** Owns test discovery configuration. Owns nothing about test
content.

**Important symbols.**

```ini
[pytest]
filterwarnings =
    ignore:.*PuLP 4.0.*:DeprecationWarning
```

**Execution role.** Read once when `pytest` starts.

**Assumptions and edge cases.** Two effects, and the second is the more important
one.

The explicit effect is suppressing a `DeprecationWarning` that PuLP 3.3.2 emits
about upcoming 4.0 API changes. The regex matches the *message*; if PuLP changes
the wording the filter silently stops matching and the warnings return.

The implicit effect is that **the presence of `pytest.ini` at the repository root
sets the rootdir**, which puts the root on `sys.path` and is what makes
`from src.model import solve` and `from run import main` resolve in tests. Delete
this file and the entire suite fails on import. There is no `pyproject.toml`,
`setup.py`, or `conftest.py` doing that job.

There is no coverage configuration, no markers, and no `testpaths` setting.

**Related tests.** Every test depends on it implicitly.

---

## `requirements.txt`

**Purpose.** Pin the three runtime dependencies.

**Important symbols.**

| Package | Version | Used for |
|---|---|---|
| `pulp` | 3.3.2 | LP/MILP modelling; bundles the CBC solver binary |
| `matplotlib` | 3.10.8 | The four figures |
| `pytest` | 9.1.1 | The test suite |

**Execution role.** `pip install -r requirements.txt`, locally and in CI.

**Assumptions and edge cases.** All three are pinned with `==`, so results are
reproducible across machines. `pytest` is a test-only dependency listed alongside
runtime ones — acceptable for a research repository with no packaging, but it
means a deployment install would pull in pytest too. There is no `numpy` or
`pandas`; all data handling uses the standard library `csv` module and plain
dicts.

Notably **no separate solver install is required.** CBC ships inside the PuLP
wheel, which is why CI needs no `apt-get`.

**Related tests.** None directly; the whole suite depends on these versions.

---

## `run.py`

**Purpose.** The main experiment. Regenerates every artifact for the fixed
9-node base network in one command.

**Responsibilities.** Owns experiment *orchestration* and *serialisation*: the
choice of protection levels and targets, the order of stages, and the CSV
schemas. It owns no modelling logic — every computation is delegated to `src/`.

**Important symbols.**

| Symbol | Line | Meaning |
|---|---|---|
| `LEVELS` | 12 | `[0.0, 0.05, …, 0.50]` — 11 uniform protection levels |
| `TARGETS` | 13 | `[0.75, 0.8, 0.85, 0.9, 0.95, 1.0]` — 6 robust targets |
| `PARADOX_TARGET` | 14 | `0.55` |
| `PARADOX_SCENARIOS` | 15 | `[("W2",)]` |
| `main(out_dir="results")` | 18-121 | The whole pipeline |
| `protection_spend_at_full(singles)` | 124-127 | First sweep spend reaching satisfaction ≥ 0.999 |

**Inputs and outputs.** `main` takes one optional `out_dir` (a `str` or
`Path`), returns `None`, and writes 9 files. Full stage-by-stage breakdown in
[Chapter 4](04-execution-flow.md#execution-stages-in-the-actual-order).

**Dependencies.** `csv` and `pathlib` from the standard library; seven project
modules (`experiment`, `model`, `network`, `plots`, `robust`, `scenarios`,
`sensitivity`).

**Execution role.** Top-level entry point. Also imported by
[`tests/test_run.py`](../tests/test_run.py), which calls `main(out_dir=tmp_path)`.

**Assumptions and edge cases.**

- `protection_spend_at_full` uses `next(...)` with **no default**
  ([`run.py:125-127`](../run.py)) and raises `StopIteration` if no level reaches
  0.999. The lookup at line 112 for the same threshold *does* pass a default of
  `None`, so the two behave differently on a network that never reaches full
  protection.
- `ccg_plan(net, single_node_failures(net), 1.0)` is computed twice — once at
  line 51 inside the frontier loop and again at line 69 — costing 89 redundant
  LP solves.
- `frontier` is built by re-evaluating each plan with `evaluate_scenarios` at
  line 53 rather than trusting the plan's own guarantee. That is an intentional
  independent cross-check.
- Writes use `newline=""`, the documented way to stop the `csv` module producing
  `\r\r\n` on Windows.
- The CSVs are written progressively, so a crash during the frontier stage still
  leaves valid `sweep.csv` and `sensitivity.csv` behind.

**Related tests.** [`tests/test_run.py`](../tests/test_run.py) — one integration
test asserting all nine files exist and that the key numerical relationships hold
across four of the five CSVs.

---

## `run_integrality.py`

**Purpose.** Run the LP-versus-integer protection experiment over many random
instances at two uncertainty budgets.

**Responsibilities.** Owns the CSV schema, the γ loop, and the CLI. The
statistics themselves belong to `src/integrality.py`.

**Important symbols.**

| Symbol | Line | Meaning |
|---|---|---|
| `COUNT` | 7 | 1000 instances per γ |
| `SEED` | 8 | 2026 |
| `main(count, seed, out_dir)` | 11-28 | Writes `integrality.csv`, prints two summary lines |

**Inputs and outputs.** Writes `integrality.csv` with columns
`gamma, index, status, lp_spend, ip_spend, gap` and $2 \times \text{count}$ data
rows. Returns `None`; the summaries reach the user only through `print`.

**Dependencies.** `csv`, `sys`, `pathlib`; `src.integrality.run_integrality_experiment`.

**Execution role.** Standalone. Not imported by any test — the tests exercise
`src/integrality.py` directly.

**Assumptions and edge cases.**

- Both γ blocks use the **same seed**, so they see the same network sequence.
  This makes the comparison paired and is a feature, not an oversight.
- The default `count=1000` is very expensive: 4,000 optimization problems, many
  over 36 scenarios. Always pass a small count when validating.
- Only `count` is exposed on the command line ([line 32](../run_integrality.py));
  `seed` and `out_dir` require importing `main` from Python.
- `int(sys.argv[1])` raises `ValueError` on a non-numeric argument with no
  friendly message.
- Infeasible instances write empty strings for the three numeric columns, since
  `csv.writer` renders `None` as an empty field.

**Related tests.** Indirectly via
[`tests/test_integrality.py`](../tests/test_integrality.py), which tests the
underlying functions.

---

## `run_scaled.py`

**Purpose.** Show the toolchain running on an arbitrarily large generated
network, and time exhaustive LP against C&CG.

**Responsibilities.** Owns network sizing, timing instrumentation, the summary
schema, and the CLI. Owns no modelling.

**Important symbols.**

| Symbol | Line | Meaning |
|---|---|---|
| `SIZES` | 13 | `(10, 10, 10, 12)` — default tier widths |
| `SEED` | 14 | 2026 |
| `main(sizes, seed, include_pairs, out_dir)` | 17-77 | Runs the experiment, **returns the summary dict** |

The returned summary has 13 keys: `sizes`, `seed`, `nodes`, `arcs`, `scenarios`,
`baseline_satisfaction`, `worst_scenario`, `worst_satisfaction`, `full_spend`,
`full_seconds`, `ccg_spend`, `ccg_iterations`, `ccg_seconds`,
`pair_worst_satisfaction`.

**Inputs and outputs.** Writes `scaled.csv`
(`failed, satisfaction, min_fill_rate, recovery_cost`, one row per single
failure) and prints five or six summary lines. Returning the dict is what makes
it testable.

**Dependencies.** `csv`, `random`, `sys`, `time`, `pathlib`;
`src.experiment`, `src.generator`, `src.model`, `src.robust`, `src.scenarios`.

**Execution role.** Standalone entry point; also imported by
[`tests/test_run_scaled.py`](../tests/test_run_scaled.py).

**Assumptions and edge cases.**

- Timing uses `time.perf_counter()`, the right monotonic clock for short
  intervals, and covers only the solve calls — not model construction outside
  them.
- `full["spend"]` and `iterative["spend"]` are formatted with `:.1f` at lines
  71-72. If either plan came back infeasible, `spend` is `None` and the f-string
  raises `TypeError`. There is **no infeasibility guard** in this script; it
  assumes the generated instance is protectable to full satisfaction.
- Any tier of size 1 other than the suppliers causes `random_layered_network` to
  raise `ValueError` (see [`src/generator.py`](#srcgeneratorpy) below).
- Passing 1-3 positional arguments silently uses the default sizes.
- `--pairs` affects only the printout and the summary, never `scaled.csv`.

**Related tests.**
[`tests/test_run_scaled.py`](../tests/test_run_scaled.py) — two tests at a small
size (3,3,3,3): one checks that C&CG matches the full LP and the CSV is written;
the other checks determinism across two runs.

---

## `src/__init__.py`

**Purpose.** Empty file, zero bytes. It marks `src/` as a regular Python package
so that `from src.model import solve` works as an absolute import.

**Responsibilities.** Nothing at runtime. It is a namespace marker.

Python 3.3+ supports implicit namespace packages, so imports would technically
resolve without it. Keeping it explicit is deliberate: it makes the package
boundary visible to readers and to tooling, and it avoids the subtle path
resolution differences namespace packages can introduce. There is no re-export
list, no `__all__`, and no package-level state — every import in the project
names its module directly.

**Related tests.** None. Every test depends on it implicitly.

---

## `src/experiment.py`

**Purpose.** The scenario-evaluation layer. Turns "what if this broke?" into
rows of metrics, and runs the uniform protection policy.

**Responsibilities.** Owns network *transformation* under failure and uniform
protection, the definition of recovery cost, the worst-case selection rule, and
the sweep loop. It does not own the LP (that is `src/model.py`), the optimized
allocation (`src/robust.py`), or which scenarios exist (`src/scenarios.py`).

**Important symbols.**

| Symbol | Lines | Signature and behaviour |
|---|---|---|
| `fail_nodes` | 6-10 | `(network, nodes) -> network`. Deep-copies, sets each named node's capacity to 0. |
| `apply_protection` | 13-17 | `(network, level) -> network`. Deep-copies, multiplies **every entry in `capacity`** by `(1 + level)`. |
| `protection_spend` | 20-21 | `(network, level) -> float`. `rate × level × sum(capacity.values())`. |
| `evaluate_scenarios` | 24-36 | `(network, scenarios) -> list[dict]`. One row per scenario. |
| `worst_case` | 39-40 | `(rows) -> dict`. `min` by `satisfaction`; **ties resolve to the first row**. |
| `protection_sweep` | 43-56 | `(base, levels, scenarios) -> list[dict]`. One row per level. |

Row shape from `evaluate_scenarios`:

```python
{"failed": tuple[str, ...], "satisfaction": float, "min_fill_rate": float,
 "cost": float, "recovery_cost": float}
```

Row shape from `protection_sweep`:

```python
{"level": float, "spend": float, "worst_satisfaction": float,
 "worst_scenario": tuple[str, ...], "max_recovery_cost": float}
```

**Dependencies.** `copy.deepcopy`; `src.model.solve`.

**Execution role.** Called by `run.py`, `run_scaled.py`, `src/sensitivity.py`,
and `src/robust.py` (which imports `fail_nodes` for the C&CG oracle).

**Assumptions and edge cases.**

- **Recovery cost is measured against the same protection level.**
  `evaluate_scenarios` computes `intact_cost = solve(network)["cost"]` at line 25
  on the network *as passed in*. Inside a sweep that network is already
  protected, so `recovery_cost` compares a disrupted protected network against an
  intact protected network. Comparing against the unprotected baseline would be a
  different — and less meaningful — quantity.
- **`recovery_cost` can be slightly negative** from LP round-off, which is why
  the test asserts `>= -1e-6` rather than `>= 0`
  ([`tests/test_experiment.py:57`](../tests/test_experiment.py)).
- **`worst_case` on an empty list raises `ValueError`.** No scenario list in the
  repository is empty, so this is latent.
- **`worst_case` ties are resolved by list order.** At uniform level 0.50 every
  single failure reaches satisfaction 1.0, so `worst_scenario` reports `S1`
  simply because it is first. Reading that as "S1 is still the weak point" would
  be wrong.
- `apply_protection` produces **floats**: `80 * 1.25 = 100.0`, and
  `70 * 1.25 = 87.5` is genuinely fractional. Capacities are not required to be
  integral anywhere in the model.
- `protection_spend` is always computed from the **base** network, so it is
  linear in `level` and independent of evaluation order.

**Related tests.** [`tests/test_experiment.py`](../tests/test_experiment.py) —
8 tests covering the calibration invariant, purity of both transformations,
linearity of spend, row shape, the `worst_case` rule, and monotonicity of the
sweep.

---

## `src/generator.py`

**Purpose.** Build random four-tier networks of arbitrary size that satisfy the
same structural contract as the hand-built one.

**Responsibilities.** Owns tier construction, capacity/demand/cost sampling, and
the arc-degree policy. It does **not** own feasibility — nothing guarantees the
generated network can meet its own demand.

**Important symbols.**

| Symbol | Lines | Meaning |
|---|---|---|
| `TIER_NAMES` | 1 | `["S", "F", "W", "H"]` — node-name prefixes |
| `random_layered_network(rng, sizes=None)` | 4-42 | Returns a network dict |

**Inputs and outputs.** `rng` is a `random.Random` instance — passed in, never
created inside, so the caller owns reproducibility. `sizes` is an optional
4-sequence of tier widths; omitted, it draws `randint(3,4)` for each of the
first three tiers and `randint(2,4)` hospitals ([line 6](../src/generator.py)).
Returns the standard 9-key dictionary with `penalty` hard-coded to `1000` and
`protection_cost_rate` to `1.0` at [lines 40-41](../src/generator.py) — note
these are **literals**, not imports from `src/network.py`, so changing the
constants there does not affect generated networks.

**Sampling ranges.**

| Quantity | Range | Line |
|---|---|---|
| Capacity (non-hospital) | `randint(20, 100)` | 15 |
| Demand (hospital) | `randint(10, 60)` | 16 |
| Arc cost | `randint(1, 5)` | 23, 29 |
| Out-degree per upstream node | `randint(2, min(4, len(downstream)))` | 21 |

**The two-pass arc construction** ([lines 18-30](../src/generator.py)) is the
interesting part:

```python
for upstream, downstream in zip(tiers[:-1], tiers[1:]):
    for src in upstream:                       # pass 1: give every source out-arcs
        degree = rng.randint(2, min(4, len(downstream)))
        for dst in rng.sample(downstream, degree):
            arc_cost[(src, dst)] = rng.randint(1, 5)
    for dst in downstream:                     # pass 2: repair thin in-degrees
        have = [s for s in upstream if (s, dst) in arc_cost]
        candidates = [s for s in upstream if (s, dst) not in arc_cost]
        while len(have) < min(2, len(upstream)) and candidates:
            src = candidates.pop(rng.randrange(len(candidates)))
            arc_cost[(src, dst)] = rng.randint(1, 5)
            have.append(src)
```

Pass 1 guarantees every upstream node has at least 2 outgoing arcs. Pass 1 alone
does **not** guarantee every downstream node has an incoming arc — random
sampling can miss one entirely, which would strand a hospital and make the
instance trivially unsolvable. Pass 2 repairs that, topping each downstream node
up to `min(2, |upstream|)` sources. The `min` handles the case of a single-node
upstream tier, where in-degree 2 is impossible.

**Dependencies.** None — not even `random` is imported, because the generator
receives an `rng` rather than creating one.

**Execution role.** Called by `run_scaled.py:21` and
`src/integrality.py:24`.

**Assumptions and edge cases.**

- **A downstream tier of size 1 raises `ValueError: empty range in
  randint(2, 1)`** at line 21, because out-degree 2 needs at least 2 candidates.
  A *supplier* tier of size 1 is fine. Verified directly: `sizes=(1,3,3,3)`
  succeeds, `sizes=(3,3,3,1)` raises.
- **Feasibility is not guaranteed.** Capacity may fall short of demand, so
  protection targets can be `Infeasible`. This is why 4 of 10 instances were
  infeasible at Γ = 2 in the reduced integrality run.
- **The calibration invariant does not hold.** Unlike the base network, generated
  instances often have failures that cost nothing — at the default scaled size,
  only 2 of 30 single failures caused any shortage at all.
- Arcs connect adjacent tiers only, by construction.
- Node names are per-tier (`S1`, `F1`, `W1`, `H1`), so they are unique across
  tiers because the prefixes differ.

**Related tests.** [`tests/test_generator.py`](../tests/test_generator.py) — 4
property-style tests: same-seed determinism, explicit sizing, large-network
schema validity, and a 20-seed sweep checking tier adjacency, degrees, and
positive capacities.

---

## `src/integrality.py`

**Purpose.** Measure the gap between the continuous protection LP and its
integer counterpart, on one instance and in batches.

**Responsibilities.** Owns the definition of "gap", the batch loop, and the
aggregation. It owns neither the optimization (`src/robust.py`) nor the network
generation (`src/generator.py`).

**Important symbols.**

| Symbol | Lines | Behaviour |
|---|---|---|
| `integrality_gap(network, scenarios, target)` | 8-18 | Solves LP then MILP; returns `{status, lp_spend, ip_spend, gap}` |
| `run_integrality_experiment(count, seed, gamma)` | 21-39 | Returns `{instances, feasible, rows, gap_count, max_gap}` |

**Inputs and outputs.** `gamma` selects the scenario family: `1` →
`single_node_failures`, anything else → `pair_failures`
([line 27](../src/integrality.py)). Note the branch is `if gamma == 1 else`, so
`gamma=3` silently means pairs. The protection target is **hard-coded to 1.0** at
[line 29](../src/integrality.py).

`rows` entries are `{"index": int, "status": str, "lp_spend": float|None,
"ip_spend": float|None, "gap": float|None}`.

**Dependencies.** `random`; `src.generator`, `src.robust.min_spend_plan`,
`src.scenarios`.

**Execution role.** Called by `run_integrality.py:19`.

**Assumptions and edge cases.**

- **Only the LP's status is checked** ([lines 10-12](../src/integrality.py)).
  This is mathematically justified: adding capacity never shrinks the recourse
  LP's feasible region, so rounding an LP-feasible plan up to integers is always
  MILP-feasible. If the LP is `Optimal`, the MILP must be too. Should CBC ever
  return a non-optimal status for the MILP anyway (a time limit, say), line 17
  would raise `TypeError` on `None - float`.
- `gaps` filters on `> 1e-6` ([line 32](../src/integrality.py)) to exclude
  round-off, so `gap_count` counts genuine gaps only.
- `max(gaps, default=0.0)` handles an empty gap list.
- One `rng` is threaded through the whole batch, so instance $i$ depends on all
  its predecessors. Reproducible, but you cannot regenerate instance 500 without
  generating the 500 before it.
- The gap is bounded: $0 \le \text{gap} < r\,|N|$, by the rounding-up argument
  above.

**Related tests.** [`tests/test_integrality.py`](../tests/test_integrality.py) —
5 tests: no gap on the base network (LP spend pinned at 170.0), a seeded batch
runs, determinism, the pinned counterexample (106.5 / 107.0 / 0.5), and
feasibility of the fractional plan.

---

## `src/model.py`

**Purpose.** The mathematical core. Build and solve the min-cost-flow LP with
shortage slack for one network, and report cost and resilience metrics.

**Responsibilities.** Owns the LP formulation and the metric definitions. It
knows nothing about disruptions, protection, sweeps, or scenarios — it just
solves whatever network it is handed. That narrowness is why every other module
can be expressed in terms of it.

**Important symbols.** One public function.

```python
def solve(network) -> dict
```

Returns:

| Key | Type | Meaning |
|---|---|---|
| `status` | `str` | `"Optimal"`, `"Infeasible"`, … from `pulp.LpStatus` |
| `cost` | `float` | Objective value: shipping + shortage penalty |
| `shipping_cost` | `float` | Shipping component alone |
| `flows` | `dict[tuple[str,str], float]` | Optimal flow per arc |
| `unmet` | `dict[str, float]` | Shortage per hospital |
| `satisfaction` | `float` | $1 - \sum s_h / D$ |
| `min_fill_rate` | `float` | $\min_h (1 - s_h/d_h)$ |

**Dependencies.** `pulp` only. This is the sole module that constructs the base
LP; `src/robust.py` builds its own, larger model independently.

**Execution role.** Called from `src/experiment.py:28` (per scenario),
`src/robust.py:79` (the C&CG oracle), `run.py:94-95`, and `run_scaled.py:23`.
It is the innermost loop of the entire project — 1,623 calls in one `run.py`.

**Assumptions and edge cases.**

- **Does not mutate its input** — it only reads. Pinned by
  `test_solve_does_not_mutate_input`
  ([`tests/test_model.py:46-50`](../tests/test_model.py)).
- **`msg=0`** on `PULP_CBC_CMD` ([line 30](../src/model.py)) suppresses CBC's
  stdout. Without it, 1,623 solves would flood the terminal.
- **The returned `status` is not checked internally.** On an infeasible model
  `pulp.value(prob.objective)` may be `None` and `.value()` on variables may
  return `None`, so the arithmetic at lines 33 and 42-43 would raise
  `TypeError`. In practice the slack makes the model always feasible — but a
  caller that hands in a network with zero total demand, or no hospitals, will
  hit a `ZeroDivisionError` or `ValueError` first.
- **Requires `demand[h] > 0` for every hospital** (divisor at line 43) and
  `sum(demand.values()) > 0` (divisor at line 42).
- **Model construction is $O(|N| \cdot |A|)$** because `inflow`/`outflow` scan
  every arc key per node ([lines 16-20](../src/model.py)). Irrelevant at these
  sizes; the dominant fix if it ever mattered is to pre-index arcs by endpoint.
- The `inflow`/`outflow` closures capture `flow` and `arcs` from the enclosing
  scope; they are defined inside `solve` so each call gets fresh bindings.

**Related tests.** [`tests/test_model.py`](../tests/test_model.py) — 7 tests,
including two on a 4-node `toy_chain` fixture whose optimum is computable by
hand, which is what anchors the LP's correctness independently of the solver.

---

## `src/network.py`

**Purpose.** Hold every numeric parameter in the project, and build the four
fixed network instances.

**Responsibilities.** Owns *all* the data for the fixed experiments. If a number
appears in a result and was not randomly generated, it came from here.

**Important symbols.**

| Symbol | Lines | Meaning |
|---|---|---|
| `SUPPLIERS`, `FACTORIES`, `WAREHOUSES`, `HOSPITALS` | 1-4 | Node name lists |
| `CAPACITY` | 6-10 | 9 capacities, 210/230/220 per tier |
| `DEMAND` | 12 | 4 demands totalling 180 |
| `ARC_COST` | 14-24 | 20 arcs, unit costs 1-4 |
| `SHORTAGE_PENALTY` | 26 | `1000` |
| `PROTECTION_COST_RATE` | 27 | `1.0` |
| `equity_paradox_network()` | 30-46 | 1/1/2/2 instance, 6 arcs |
| `integrality_gap_network()` | 49-76 | 3/4/4/4 instance, 29 arcs |
| `base_network()` | 79-90 | The main 3/3/3/4 instance |

**Inputs and outputs.** All four builders take no arguments and return a fresh
9-key dictionary.

**Dependencies.** None. Pure data.

**Execution role.** Called at the start of every experiment and by most tests.

**Assumptions and edge cases.**

- **`base_network()` returns a fresh copy** each call via `list(...)` and
  `dict(...)` ([lines 81-87](../src/network.py)). These are *shallow* copies,
  which suffices because the inner values are immutable scalars. Pinned by
  `test_base_network_returns_fresh_copies`
  ([`tests/test_network.py:50-54`](../tests/test_network.py)).
- The other two builders construct their literals inline on every call, so they
  are trivially fresh.
- **The base network satisfies a calibration invariant** — every tier can cover
  demand, but not after losing its largest node. See
  [Chapter 2](02-network-and-data-model.md#capacities-and-demands). Change any
  capacity and this may break, silently changing every downstream result.
- `equity_paradox_network` is **deliberately under-supplied** (capacity 10
  against demand 20), so it does *not* satisfy that invariant. That is the point.
- `integrality_gap_network` has supplier capacity 103 against demand 115, so it
  cannot meet demand intact either — full protection requires buying supplier
  capacity.
- The two special networks import `SHORTAGE_PENALTY` and
  `PROTECTION_COST_RATE` from module scope, so they track those constants.
  `src/generator.py` does **not** — it hard-codes `1000` and `1.0`.

**Related tests.** [`tests/test_network.py`](../tests/test_network.py) — 7 tests
pinning total demand, arc validity, tier adjacency, hospital redundancy, capacity
presence, the calibration invariant, and freshness.

---

## `src/plots.py`

**Purpose.** Produce the four publication figures.

**Responsibilities.** Owns all visual styling and figure layout. It performs no
optimization and reads no files — every function takes an already-computed data
structure and an output path.

### The non-interactive backend

```python
import matplotlib
matplotlib.use("Agg")          # line 3
import matplotlib.pyplot as plt  # line 4
```

`matplotlib.use("Agg")` **must** come before `import matplotlib.pyplot`, which is
why the imports are in this unusual order and why linters would flag line 4 as an
import-not-at-top. `Agg` is a raster backend that writes files and never opens a
window. Without it, matplotlib would try to select a GUI backend, which fails or
hangs on a headless CI machine. This one line is what lets
[`tests/test_plots.py`](../tests/test_plots.py) run in GitHub Actions.

### Shared visual styling

A palette of module constants at [lines 8-29](../src/plots.py):

| Constant | Value | Role |
|---|---|---|
| `INK` | `#0b0b0b` | Titles |
| `SECONDARY_INK` | `#52514e` | Axis labels, annotations, legend text |
| `MUTED` | `#898781` | Tick labels, arc cost labels |
| `GRID` | `#e1e0d9` | Grid lines |
| `BASELINE` | `#c3c2b7` | Spines, reference lines, network arcs |
| `SINGLE_COLOR` | `#2a78d6` | Single-failure and uniform-protection series |
| `PAIR_COLOR` | `#1baf7a` | Pair-failure and optimized series |
| `VARIANT_ORDER` | list | Legend ordering for the sensitivity plot |
| `VARIANT_COLORS` | dict | Per-variant colours; capacity variants share a blue ramp, cost variants get distinct hues |
| `TIER_COLORS` | dict | One colour per tier in the network diagram |

`_styled_axes(figsize)` ([lines 32-43](../src/plots.py)) applies the house style
to a new figure: white background, soft grid drawn *below* the data
(`set_axisbelow(True)`), top and right spines removed, muted tick labels, 200 dpi.
`_line(ax, sweep, color, label)` ([lines 46-58](../src/plots.py)) draws a sweep as
a 2 pt line with white-edged circular markers — the white edge is what stops
markers merging where points cluster.

`_end_label(ax, sweep, text)` ([lines 61-71](../src/plots.py)) writes a label 8
points to the right of a series' last point, so curves are identifiable without
tracing back to the legend.

### `tradeoff_plot(singles, pairs, path)` — lines 74-116

Worst-case satisfaction against protection spend, one line for single failures
and one for pairs, with a reference line at 100%.

**The annotation logic** at [lines 81-98](../src/plots.py) is the most
interesting part:

```python
switch = next(
    (row for prev, row in zip(singles, singles[1:])
     if row["worst_scenario"] != prev["worst_scenario"]),
    None,
)
```

It scans consecutive pairs of sweep rows for the **first** change in the binding
scenario and, if found, annotates that point with "binding failure becomes …".
This surfaces automatically the finding that the critical facility changes as
protection rises — the plot discovers it rather than having it hard-coded. The
`None` default means the annotation is simply skipped if the binding scenario
never changes.

The y-limit is data-driven: `floor - 0.08` to `1.06` where `floor` is the minimum
across both series ([lines 109-112](../src/plots.py)), so the interesting range
fills the axes regardless of how bad the worst case is.
`PercentFormatter(xmax=1, decimals=0)` renders the 0–1 satisfaction values as
percentages.

### `frontier_plot(uniform_sweep, frontier, path)` — lines 119-164

Uniform protection against the optimized C&CG frontier. Note it does **not** use
`_line` for the frontier series — it repeats the plotting call inline at
[lines 123-134](../src/plots.py), because the frontier rows have a different
schema (`target`/`iterations` rather than `level`/`max_recovery_cost`) even
though both expose `spend` and `worst_satisfaction`. The optimized label is
offset `(8, -12)` rather than `(8, 0)` so it does not collide with the uniform
label where the two curves converge at 100%.

### `coinciding_variants(variants)` — lines 167-174

A small pure function, and the only one in `plots.py` with its own unit test.

```python
base_curve = [row["worst_satisfaction"] for row in variants["base"]]
return [name for name, sweep in variants.items()
        if name != "base"
        and [row["worst_satisfaction"] for row in sweep] == base_curve]
```

It returns the names of variants whose satisfaction curve is **exactly** equal to
the base curve. The comparison is exact float equality — deliberately, not
sloppily. The cost variants coincide with the base *identically*, not
approximately, because scaling arc costs cannot change the optimal delivery
volume at all when the penalty dominates (see
[Chapter 3](03-mathematical-model.md#why-the-penalty-must-be-large)). An
approximate comparison would risk folding curves that genuinely differ by a
little.

### `sensitivity_plot(variants, path)` — lines 177-207

Draws the five sweeps, but **skips any variant that coincides with the base**
and instead folds their names into the base curve's legend entry:

```python
label = f"base ({folded} coincide)"
```

Without this, `cost_x0.8` and `cost_x1.2` would be drawn exactly on top of
`base`, and the reader would see one line and three legend entries with no
explanation. Folding turns an invisible plotting artefact into an explicit
statement of the finding. Series are drawn in `VARIANT_ORDER` — lowest capacity
first — so the legend reads bottom-to-top in the same order as the curves.

### `network_diagram(network, path)` — lines 221-304

The one figure that draws the network itself. It does not use `_styled_axes`
because it needs a bare canvas (`ax.axis("off")`).

**Node positioning** — `_node_positions` at
[lines 210-218](../src/plots.py):

```python
for col, tier in enumerate(TIERS):
    nodes = network[tier]
    step = 1.2 if len(nodes) == 3 else 1.0
    top = 1.2 + (len(nodes) - 1) * step / 2
    for i, node in enumerate(nodes):
        positions[node] = (col * 1.6, top - i * step)
```

Each tier is a column at $x = 1.6\,\text{col}$; nodes are stacked downward from a
`top` computed so the column is vertically centred on $y = 1.2$. The
`step = 1.2 if len(nodes) == 3 else 1.0` rule gives the three-node tiers slightly
more breathing room than the four-node hospital tier, so all four columns end up
about the same height. This is **tuned for the base network's 3/3/3/4 shape**;
the axis limits are hard-coded to $x \in [-0.6, 5.4]$, $y \in [-1.4, 4.1]$ at
[lines 294-295](../src/plots.py), so a network with more tiers or many more nodes
per tier would overflow the frame. The function is only ever called on the base
network.

**Arc drawing** ([lines 227-247](../src/plots.py)) shortens each line by 0.33 at
both ends so it stops at the node box rather than running under it. The cost
label position uses

```python
t = 0.5 if y0 == y1 else (0.3 if y1 < y0 else 0.7)
```

— a parameter along the arc: mid-way for horizontal arcs, one-third along for
downward arcs, two-thirds for upward ones. Since arcs fan out from each node,
staggering the labels this way keeps them from piling up near the source. Each
label sits in a white rounded box so it stays readable where it crosses another
arc.

**Node drawing** ([lines 248-268](../src/plots.py)) labels each node with its
name and its value, where the value is
`network["demand"].get(node, network["capacity"].get(node))` — demand for
hospitals, capacity for everything else. Node fill is the tier colour at 14%
opacity via `to_rgba(hue, 0.14)` with a full-strength border, giving tier
identity without overwhelming the text. `zorder` is set explicitly (arcs 1,
labels 2, nodes 3) so nodes always draw over arcs.

### Why figures are explicitly closed

Every plotting function ends with:

```python
fig.savefig(path, bbox_inches="tight")
plt.close(fig)
```

`plt.close(fig)` releases the figure from matplotlib's global registry. Without
it, each created figure stays referenced forever — memory grows, and after 20
open figures matplotlib emits a `RuntimeWarning`. The four calls in a single
`run.py` would not hurt, but `pytest` runs the plotting tests repeatedly in one
process, and any future loop over many plots would. Closing explicitly is the
correct discipline for a non-interactive backend.

`bbox_inches="tight"` crops surrounding whitespace, which matters for the network
diagram, where the hard-coded axis limits leave generous margins.

**Dependencies.** `matplotlib` only — `pyplot`, `colors.to_rgba`,
`ticker.PercentFormatter`.

**Execution role.** Called only at `run.py:106-109`, after all computation.

**Assumptions and edge cases.**

- `tradeoff_plot`, `frontier_plot`, and `_end_label` index `sweep[-1]`, so an
  **empty sweep raises `IndexError`**.
- `coinciding_variants` requires a `"base"` key — `KeyError` otherwise.
- `sensitivity_plot` sorts unknown variant names to position 99
  ([line 182](../src/plots.py)), so extra variants render after the known ones
  rather than crashing, and fall back to `MUTED` for colour.
- `network_diagram` requires all four tier keys and assumes every arc endpoint has
  a position — a stray arc raises `KeyError`.
- No function creates its output directory; the caller must.

**Related tests.** [`tests/test_plots.py`](../tests/test_plots.py) — 5 tests. Four
are smoke tests writing to `tmp_path` and asserting a non-empty file; the fifth
unit-tests `coinciding_variants` against a hand-built fixture.

---

## `src/robust.py`

**Purpose.** The two-stage robust optimization layer: decide *where* to buy
protection, and reach the same answer iteratively via C&CG.

**Responsibilities.** Owns the min-spend formulation, the LP/MILP switch, and the
C&CG loop. It builds its own multi-scenario LP rather than reusing
`src/model.py` — the two models have different objectives and cannot share code
without contorting both.

**Important symbols.**

| Symbol | Lines | Behaviour |
|---|---|---|
| `_protectable(network)` | 9-10 | Suppliers + factories + warehouses |
| `apply_allocation(network, extra)` | 13-17 | Deep-copies, **adds** `extra[node]` to each named node's capacity |
| `min_spend_plan(network, scenarios, target, integer=False)` | 20-67 | The extensive-form robust LP or MILP |
| `ccg_plan(network, scenarios, target)` | 70-101 | The C&CG loop |

**Inputs and outputs.**

`min_spend_plan` returns `{"status", "spend", "extra"}`, with `spend` and `extra`
set to `None` when the status is not `"Optimal"`
([lines 59-60](../src/robust.py)). `extra` is `dict[str, float]` over
`_protectable` nodes.

`ccg_plan` returns the same three keys **plus `"iterations"`**. The extra key
matters: `run.py:57` and `run_scaled.py:60` both read it, and a caller that
substitutes `min_spend_plan` for `ccg_plan` would hit a `KeyError`.

**Dependencies.** `copy.deepcopy`, `pulp`; `src.experiment.fail_nodes`,
`src.model.solve`.

**Execution role.** `min_spend_plan` is called by `ccg_plan`, `run.py:91`,
`run_scaled.py:28`, and `src/integrality.py:9, 12`. `ccg_plan` is called by
`run.py:51, 69` and `run_scaled.py:32`.

**Assumptions and edge cases.**

- **`apply_allocation` adds; `apply_protection` multiplies.** The two are easily
  confused and are not interchangeable.
- **`apply_allocation` iterates `extra.items()`**, so a node absent from `extra`
  keeps its base capacity, and a node in `extra` but not in `capacity` raises
  `KeyError`.
- **The target constraint is aggregate** ([line 55](../src/robust.py)):
  `lpSum(unmet) <= (1 - target) * total_demand`. It bounds total shortage, not
  per-hospital fill rate. This is the direct cause of the equity paradox.
- **Failed nodes still get an `extra` variable.** Line 44 writes
  `outflow(s) <= 0` for a failed supplier, ignoring `extra[s]`. Capacity bought
  at a node is simply unavailable in scenarios where that node fails, but still
  counts toward the spend and is still useful in every other scenario.
- **`inflow`/`outflow` are redefined inside the scenario loop**
  ([lines 36-40](../src/robust.py)) so each closes over that scenario's `flow`
  dict. They are used within the same iteration, so the usual late-binding
  closure trap does not bite — but moving those definitions outside the loop
  would break the model silently.
- **`integer=True` makes only `extra` integral.** Flows and shortages stay
  continuous, so the model is a MILP, not an IP.
- **`ccg_plan` always calls `min_spend_plan` with the default
  `integer=False`** ([line 93](../src/robust.py)). There is no integer C&CG.
- **The stopping tolerance is `1e-6`** ([line 84](../src/robust.py)), guarding
  against solver round-off leaving the worst value a hair below target.
- **`ccg_plan` terminates in at most `len(scenarios) + 1` iterations**, because a
  scenario added to the master can never be selected again. See
  [Chapter 3](03-mathematical-model.md#why-it-converges-and-why-it-is-optimal).
- **The oracle is exhaustive** — `len(scenarios)` LP solves per iteration
  ([lines 77-83](../src/robust.py)). Correct, verifiable, and not fast.
- On an infeasible master, `ccg_plan` returns the master's status with `spend`
  and `extra` as `None` but a valid `iterations` count.
- Model size is $|K| \cdot (|A| + |H|) + |N|$ variables — 225 for the base
  network with singles, 873 with pairs.

**Related tests.** [`tests/test_robust.py`](../tests/test_robust.py) — 7 tests:
allocation purity, zero spend for an already-met target, a full-protection plan
that survives every failure, optimized beating uniform, pair infeasibility, C&CG
matching the full LP, and C&CG converging on a small subset of pair scenarios.

---

## `src/scenarios.py`

**Purpose.** Enumerate disruption scenarios.

**Responsibilities.** Owns the definition of *what can fail* and *which
combinations are considered*. Thirteen lines, and the smallest module in the
project.

**Important symbols.**

| Symbol | Lines | Returns |
|---|---|---|
| `_failable_nodes(network)` | 4-5 | `suppliers + factories + warehouses` |
| `single_node_failures(network)` | 8-9 | `[(n,) for n in failable]` — length $|N|$ |
| `pair_failures(network)` | 12-13 | `list(combinations(failable, 2))` — length $\binom{|N|}{2}$ |

**Inputs and outputs.** Both public functions take a network and return a list of
tuples. Single failures return **1-tuples**, not bare strings — that uniformity
is what lets `fail_nodes` iterate over any scenario without special-casing.

**Dependencies.** `itertools.combinations` only.

**Execution role.** Called by `run.py` (lines 23, 24, 25, 51, 69),
`run_scaled.py` (22, 37), and `src/integrality.py:27`.

**Assumptions and edge cases.**

- **Hospitals are excluded by construction.** They cannot fail in this model.
- **Order is deterministic**: tier order, then list order within each tier. That
  determinism is load-bearing — `worst_case` resolves ties by taking the first
  minimum, so a stable scenario order means stable reported `worst_scenario`
  values.
- `pair_failures` returns unordered combinations, so `("S1","S2")` appears and
  `("S2","S1")` does not.
- Growth is quadratic: 9 nodes → 36 pairs, but 30 nodes → 435 pairs. The pair
  sweep is the reason `run_scaled.py` makes them opt-in.
- Neither function is aware of `capacity`, so a node with capacity 0 still
  produces a scenario.

**Related tests.** [`tests/test_scenarios.py`](../tests/test_scenarios.py) — 2
tests: singles cover exactly the non-hospital nodes, and pairs are 36 distinct
unordered combinations excluding hospitals.

---

## `src/sensitivity.py`

**Purpose.** Re-run the uniform sweep under perturbed parameters to test whether
the findings depend on the exact numbers chosen.

**Responsibilities.** Owns the set of perturbations and the ±20% factors. It
reuses `protection_sweep` wholesale and adds no analysis of its own.

**Important symbols.**

| Symbol | Lines | Behaviour |
|---|---|---|
| `scale_costs(network, factor)` | 6-9 | Deep-copies; multiplies **every arc cost** |
| `scale_capacities(network, factor)` | 12-15 | Deep-copies; multiplies **every capacity** |
| `run_sensitivity(base, levels, scenarios)` | 18-29 | Returns `dict[str, sweep]` with 5 keys |

The five variants ([lines 19-25](../src/sensitivity.py)): `base`, `cost_x0.8`,
`cost_x1.2`, `capacity_x0.8`, `capacity_x1.2`. Those strings become the `variant`
column in `sensitivity.csv` and the legend labels in `sensitivity.png`.

**Inputs and outputs.** Output is a dict of 5 sweeps, each the same shape
`protection_sweep` returns.

**Dependencies.** `copy.deepcopy`; `src.experiment.protection_sweep`.

**Execution role.** Called once, at `run.py:25`.

**Assumptions and edge cases.**

- **Each function touches exactly one dictionary.** `scale_costs` leaves
  `capacity` untouched and vice versa — asserted in
  [`tests/test_sensitivity.py:10-23`](../tests/test_sensitivity.py). Without
  that, "cost sensitivity" and "capacity sensitivity" would be confounded.
- **`capacity_x0.8` and `capacity_x1.2` shift the whole curve**, because
  `protection_spend` is computed from the *scaled* network's capacities. So the
  variants differ in both axes, not just the vertical one.
- **The cost variants produce a curve identical to the base**, because the
  shortage penalty dominates. This is a *prediction of the model*, confirmed by
  `test_cost_scaling_leaves_satisfaction_curve_unchanged`
  ([`tests/test_sensitivity.py:34-40`](../tests/test_sensitivity.py)), and it is
  what `coinciding_variants` in `plots.py` exists to render honestly.
- The variant set is hard-coded. Adding one means editing the dict at
  [lines 19-25](../src/sensitivity.py) and probably `VARIANT_ORDER` and
  `VARIANT_COLORS` in `plots.py`.
- `run_sensitivity` costs $5 \times |{\rm levels}| \times (1 + |K|)$ LP solves —
  550 in the default configuration, the single most expensive stage of `run.py`.

**Related tests.** [`tests/test_sensitivity.py`](../tests/test_sensitivity.py) —
5 tests: two isolation checks, one on the variant set, one on cost invariance,
one on the direction of the capacity shift.

---

## `tests/__init__.py`

**Purpose.** Empty file, zero bytes. Makes `tests/` a package.

With `pytest.ini` establishing the rootdir, pytest's default `rootdir`-based
`sys.path` insertion already allows `from src.model import solve`. The
`__init__.py` additionally guarantees that test modules get fully qualified names
(`tests.test_model` rather than `test_model`), which prevents a name collision if
two test files in different directories ever share a basename. There is no shared
fixture code here — the project has no `conftest.py`, and each test file builds
its own fixtures.

---

## Test files

Each is summarised here; [Chapter 7](07-testing-and-validation.md) covers them by
concern, with the reasoning behind individual assertions.

| File | Tests | Verifies | Type |
|---|---|---|---|
| [`tests/test_experiment.py`](../tests/test_experiment.py) | 8 | Calibration invariant, purity of `fail_nodes`/`apply_protection`, spend linearity, row shape, `worst_case` rule, sweep monotonicity | Unit + regression |
| [`tests/test_generator.py`](../tests/test_generator.py) | 4 | Seed determinism, explicit sizing, schema validity over 20 seeds and at size 12/12/12/15 | Property-style |
| [`tests/test_integrality.py`](../tests/test_integrality.py) | 5 | Zero gap on the base network (LP spend 170.0), seeded batches, determinism, the pinned 106.5/107.0/0.5 counterexample, feasibility of the fractional plan | Unit + regression |
| [`tests/test_model.py`](../tests/test_model.py) | 7 | Hand-computable `toy_chain` costs, baseline feasibility, non-mutation, shortage-not-infeasible, `min_fill_rate` semantics | Unit |
| [`tests/test_network.py`](../tests/test_network.py) | 7 | Total demand 180, arc validity, tier adjacency, ≥2 sources per hospital, capacity presence, the calibration invariant, freshness | Unit + regression |
| [`tests/test_paradox.py`](../tests/test_paradox.py) | 2 | Unprotected split (0.5 / 0.4), and that optimal protection raises satisfaction while lowering equity | Regression |
| [`tests/test_plots.py`](../tests/test_plots.py) | 5 | Four figures write non-empty files; `coinciding_variants` folds only exactly-equal curves | Smoke + unit |
| [`tests/test_robust.py`](../tests/test_robust.py) | 7 | Allocation purity, zero-spend targets, full protection, optimized < uniform, pair infeasibility, C&CG = full LP, C&CG subset convergence | Unit + integration |
| [`tests/test_run.py`](../tests/test_run.py) | 1 | End-to-end: all 9 artifacts exist, and cross-CSV relationships hold | Integration |
| [`tests/test_run_scaled.py`](../tests/test_run_scaled.py) | 2 | C&CG matches full LP on a generated 3/3/3/3 network; run determinism | Integration |
| [`tests/test_scenarios.py`](../tests/test_scenarios.py) | 2 | 9 singles covering all non-hospital nodes; 36 distinct pairs | Unit |
| [`tests/test_sensitivity.py`](../tests/test_sensitivity.py) | 5 | Transformation isolation, variant set, cost invariance, capacity shift direction | Unit + regression |

**Total: 55 tests**, all passing (`pytest -q` → `55 passed in 68.35s`).

---

## Tracked artifacts under `results/`

Only PNG files are tracked; `.gitignore` lines 68-69 ignore everything else.
All four are regenerated by `run.py:106-109` and are referenced from the root
`README.md`.

### `results/network.png`

**Produced by** `network_diagram(net, out / "network.png")` — `run.py:109`.
**Source data:** `base_network()`.

A four-column node-link diagram of the base network. Each node is a rounded box
labelled with its name and value — capacity for suppliers, factories, and
warehouses; demand for hospitals — filled with its tier colour at low opacity.
Arcs are thin grey lines labelled with unit shipping cost. Column headers name
each tier and state whether the number is a capacity or a demand, and a caption
below clarifies the arc labels.

**Read it for:** the structural facts that drive every result — in particular
that `H1` and `H2` both connect only to `W1` and `W2`, which is the cut behind
the pair-failure plateau.

### `results/tradeoff.png`

**Produced by** `tradeoff_plot(singles, pairs, ...)` — `run.py:106`.
**Source data:** the two 11-row uniform sweeps, i.e. the same data as
`sweep.csv`.

Two curves of worst-case satisfaction against protection spend, blue for single
failures and green for pairs, with a reference line at 100%. The single-failure
curve is annotated where the binding scenario first changes.

**Read it for:** the shape of the cost–resilience relationship, and the visual
contrast between a curve that reaches 100% and one that flattens well below it.

### `results/frontier.png`

**Produced by** `frontier_plot(singles, frontier, ...)` — `run.py:108`.
**Source data:** the single-failure uniform sweep (`sweep.csv`) and the
C&CG frontier (`frontier.csv`).

Uniform protection in blue against the optimized allocation in green, both as
worst-case satisfaction versus spend.

**Read it for:** the dominance of optimized over uniform protection — the green
curve sits above the blue one everywhere, reaching 100% at spend 170 where
uniform needs 330.

### `results/sensitivity.png`

**Produced by** `sensitivity_plot(sensitivity, ...)` — `run.py:107`.
**Source data:** the five sweeps in `sensitivity.csv`.

Up to five curves of worst-case satisfaction against spend. In practice three are
drawn: the two cost variants coincide exactly with the base and are folded into
its legend entry, which reads `base (cost ×0.8, cost ×1.2 coincide)`.

**Read it for:** the finding that the results are insensitive to shipping cost
and sensitive to capacity — and note that the folded legend entry is itself the
statement of the first half of that finding.

---

Previous: [Chapter 4 — Execution flow](04-execution-flow.md) ·
Next: [Chapter 6 — Experiments and results](06-experiments-and-results.md)
