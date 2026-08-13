# GOAL.md — `scaffold`

**Coupled population–infrastructure simulation for treatment-dependent viability.**

> Read `THEORY.md` before writing code. It contains the formalism, the prior work this
> must not reinvent, the arithmetic that determines what the model is allowed to claim,
> and the framing constraints that are non-negotiable.

---

## 0. One-paragraph statement of purpose

Modern medicine keeps people alive by making them dependent on engineered systems —
molecules, devices, facilities, supply chains, power. The **genetic** consequences of this
are small and slow, and already well described by 90 years of population genetics. The
**dependency** consequences are large, fast, and barely modeled at all. `scaffold` is a
simulator that couples a demographic-genetic population model to a stochastic
infrastructure reliability model, so that the question *"how much of a population's
viability now rests on artificial scaffolds, and what happens when they fail?"* becomes a
computable quantity with credible intervals and a traceable provenance for every number.

---

## 1. Non-goals

These are listed first because they are the most common ways this project fails.

- **NOT a claim that medicine degrades the gene pool.** The arithmetic in `THEORY.md §3`
  shows allele frequencies barely move. Any module, variable name, log message, docstring,
  or output label implying genetic deterioration is a defect. See `§13 Framing constraints`.
- **NOT a reimplementation of population genetics.** Hardy–Weinberg, Wright–Fisher and
  Leslie matrices are settled. Implement them correctly, test them against closed-form
  solutions, and move on. No novelty is claimed there.
- **NOT an agent-based / LLM system.** No language models in the simulation loop. The only
  machine learning permitted is the calibration surrogate (`§6.6`) and the scenario search
  proposer (`§6.8`), both of which are numerical, not linguistic.
- **NOT a clinical decision tool.** Population-level only. No module may accept or emit an
  identified individual patient record.
- **NOT a forecasting product.** Forward projections are conditional scenarios, always
  labeled as such (`§9 Claim ladder`).

---

## 2. Environment constraints

| Constraint | Value |
|---|---|
| Target hardware | Apple Silicon (M4, 64 GB unified memory) |
| Accelerator | CPU + Metal (MPS). **No CUDA.** Any CUDA-only dependency is disqualified. |
| Python | 3.12 |
| Package manager | `uv` |
| Determinism | Every run reproducible from `(config_hash, seed)`. No unseeded RNG anywhere. |
| Parallelism | `multiprocessing` / `joblib` over cores; vectorize with numpy before parallelizing |

**Permitted core dependencies:** `numpy`, `scipy`, `pandas` or `polars`, `networkx`,
`pydantic` (v2), `numba`, `pyyaml`, `pytest`, `hypothesis`, `matplotlib`, `arviz`,
`sbi` (PyTorch/MPS backend), `SALib`.

**Forbidden:** anything requiring CUDA; anything requiring a network call at simulation
runtime; any dependency without a permissive license.

---

## 3. Repository layout

```
scaffold/
├── GOAL.md                     # this file
├── THEORY.md                   # reference document — read first
├── pyproject.toml
├── src/scaffold/
│   ├── __init__.py
│   ├── provenance.py           # M0  audit + trace layer
│   ├── params.py               # M0  provenance-tagged parameter objects
│   ├── genetics.py             # M1  allele dynamics
│   ├── demography.py           # M2  age-structured population
│   ├── vdg.py                  # M3  viability dependency graph
│   ├── reliability.py          # M3  stochastic failure/repair on infrastructure
│   ├── population.py           # M3  individual-based population coupling M1–M3
│   ├── belief.py               # M4  expert belief network / elicitation ingest
│   ├── ensemble.py             # M5  three-loop Monte Carlo driver
│   ├── inference.py            # M6  simulation-based calibration
│   ├── search.py               # M7  adaptive rare-event scenario search
│   ├── analysis.py             # M8  Sobol, provenance decomposition, EVPPI
│   └── validate.py             # M1+ analytic-limit and retrodiction harness
├── configs/
│   ├── structures/             # alternative DAGs for the structural ensemble
│   ├── elicitation/            # SHELF/Cooke elicitation records
│   └── scenarios/
├── tests/
│   ├── test_analytic_limits.py # THE GATE — see §8
│   ├── test_provenance.py
│   └── ...
├── notebooks/
└── data/
    ├── raw/                    # never modified
    └── derived/
```

---

## 4. Core data contracts

Define these with `pydantic` v2 in `params.py` and `vdg.py` **before** any simulation code.
Everything else depends on them being right.

### 4.1 Provenance classes

Every scalar parameter in the system carries exactly one:

```python
class Provenance(str, Enum):
    TRIAL        = "trial"         # RCT-derived
    REGISTRY     = "registry"      # large administrative/registry dataset
    OBSERVATIONAL= "observational" # cohort / case-control
    MECHANISTIC  = "mechanistic"   # derived from physical/biological first principles
    ELICITED     = "elicited"      # formal expert elicitation (SHELF or Cooke)
    ASSUMED      = "assumed"       # no empirical support; placeholder
```

`ASSUMED` is not a failure state — it is an honest label, and `§8 AT-8.3` requires the
model to report how much output variance it carries.

### 4.2 Parameter

```python
class Parameter(BaseModel):
    name: str
    provenance: Provenance
    distribution: DistributionSpec   # see 4.3
    source: str                      # citation, DOI, dataset+version, or elicitation ID
    elicitation_id: str | None       # required iff provenance == ELICITED
    notes: str = ""
```

Invariant, enforced at construction: `provenance == ELICITED` ⟹ `elicitation_id` resolves
to a record in `configs/elicitation/`.

### 4.3 DistributionSpec

Elicitation yields **quantiles, never moments** (`THEORY.md §6.2`). The spec therefore
accepts quantiles and fits a distribution, rather than accepting a mean and variance.

```python
class DistributionSpec(BaseModel):
    family: Literal["lognormal","beta","gamma","normal","triangular","point","empirical"]
    quantiles: dict[float, float] | None   # e.g. {0.05: 1.2, 0.5: 3.4, 0.95: 9.1}
    fitted_params: dict[str, float] | None
    overconfidence_correction: float = 1.0 # interval-widening factor; see THEORY.md §6.3
```

Requirement: fitting must minimize quantile loss, report fit residual, and **fail loudly**
if the supplied quantiles are inconsistent with the requested family rather than silently
returning a poor fit.

### 4.4 Viability Dependency Graph

```python
class Dependency(BaseModel):
    id: str
    kind: Literal["molecule","device","facility","supply_chain","utility","personnel"]
    substitutable_by: list[str] = []      # partial substitution allowed
    substitution_efficacy: float = 0.0    # 0..1

class InfraNode(BaseModel):
    id: str
    supplies: list[str]                   # Dependency ids
    failure_process: FailureProcess       # 4.5
    upstream: list[str] = []              # shared chokepoints → correlated failure

class VDG(BaseModel):
    dependencies: dict[str, Dependency]
    infrastructure: dict[str, InfraNode]
    # individual → required dependencies is held on the population array, not here
```

**Correlated failure is the whole point.** `upstream` edges are what make individually-rare
failures co-occur. A VDG whose infrastructure nodes are all independent must be
constructible (it is the naive lower-bound structure in the ensemble) but must never be
the default.

### 4.5 Failure and consequence

```python
class FailureProcess(BaseModel):
    hazard: Parameter          # failure rate
    repair: Parameter          # duration distribution
    partial: bool = False      # capacity degradation vs binary outage

class ConsequenceModel(BaseModel):
    # hazard of death as a function of consecutive unmet-dependency time
    tolerance: Parameter       # time to first excess risk
    hazard_curve: Parameter    # shape of escalation past tolerance
```

`ConsequenceModel` is where most `ELICITED` and `ASSUMED` parameters will live. Expect it,
label it, measure its variance contribution.

---

## 5. Milestones

Each milestone ships with its acceptance tests passing. **Do not begin a milestone until
the previous milestone's tests are green in CI.**

| M | Module | Ships |
|---|---|---|
| M0 | `provenance`, `params` | Data contracts, audit trail, config hashing |
| M1 | `genetics` | Single- and multi-locus dynamics, viability/fertility split, screening |
| M2 | `demography` | Leslie matrix, variable reproductive span, lifetime reproductive output |
| M3 | `vdg`, `reliability`, `population` | The coupling. **This is the contribution.** |
| M4 | `belief` | Expert DAG ingest, elicitation records, prior construction |
| M5 | `ensemble` | Three-loop Monte Carlo with QMC + common random numbers |
| M6 | `inference` | SBI calibration; elicited priors → posteriors given data |
| M7 | `search` | Adaptive rare-event scenario search |
| M8 | `analysis` | Sobol indices, provenance-grouped variance, EVPPI |
| M9 | — | Retrodiction study against observed disruption events |

Build order note: **M3 before M4–M8.** The coupling is the novel part; the statistical
machinery is supporting apparatus. If M3 does not work, nothing downstream matters.

---

## 6. Module specifications

### 6.1 `provenance.py` (M0)

Every simulation output must be resolvable backwards to: config hash, git commit, seed,
full parameter set with provenance labels, and dependency versions. Implement as an
append-only run record written before the run starts and finalized after.

Provide `trace(value) -> ProvenanceReport` for any headline number.

### 6.2 `genetics.py` (M1)

Deterministic recursions and Wright–Fisher stochastic mode.

Required capabilities:
- Allele frequency dynamics with **separate viability and fertility fitness components**.
  This split is essential: therapies commonly restore one and not the other
  (`THEORY.md §3.2`). A single scalar fitness is not acceptable.
- Mutation, selection, drift, non-random mating off by default.
- A **screening/selection-at-conception term** representing carrier screening and embryo
  selection with an uptake parameter. Omitting this term produces the wrong sign on
  long-run allele frequency (`THEORY.md §3.4`).
- Multi-locus individual-based mode for mutational load: ≥10⁵ individuals, ≥10³ loci,
  new mutations per generation, tracking mean fitness rather than any single allele.

### 6.3 `demography.py` (M2)

Age-structured Leslie matrix. Age-specific survival and fertility. Configurable
reproductive span. Paternal-age-dependent de novo mutation rate feeding `genetics`.
Expose dominant eigenvalue, stable age distribution, reproductive value, generation time.

The reproductive-span question must be answerable here: changing span changes generation
time, which rescales every genetic process measured in years (`THEORY.md §4`).

### 6.4 `vdg.py` + `reliability.py` + `population.py` (M3) — **the core**

Individuals carry a dependency vector. Infrastructure nodes fail and repair stochastically,
with correlation induced by shared `upstream` nodes. Unmet dependencies accumulate unmet
time; `ConsequenceModel` converts unmet time to excess hazard.

Primary outputs — these are the numbers the whole project exists to produce:

1. **Scaffold-dependent population fraction** over time.
2. **Consequence of failure at time _N_**: people affected and excess deaths if a given
   infrastructure node fails in year _N_, as a function of _N_.
3. **Minimum cut sets**: smallest sets of simultaneous node failures producing outcomes
   above a threshold.

Performance target: 10⁵ individuals × 100 years × 100 stochastic reps in under 60 s on
one M4 core. Vectorize over individuals with numpy; `numba` only where profiling proves
it necessary.

### 6.5 `belief.py` (M4)

- Ingest expert-specified DAGs from `configs/structures/*.yaml`.
- Ingest elicitation records: SHELF group sessions and Cooke's Classical Model, the latter
  including **seed questions with known answers** and the resulting performance weights.
  Implement Cooke aggregation properly — it is the main defense against the
  "this is just opinion" objection (`THEORY.md §6.1`).
- Apply overconfidence correction to elicited intervals; expose the factor, never hide it.
- Emit priors consumable by `inference.py`.

**Hard boundary, enforced in code:** a parameter may not be `ELICITED` if a data source is
registered for it in the parameter registry. Raise on violation. The elicited/data split is
frozen before results are seen (`THEORY.md §6.4`).

### 6.6 `inference.py` (M6)

Simulation-based inference via neural posterior estimation (`sbi`, MPS backend). Elicited
distributions enter as priors; registry and disruption data enter as likelihood; output is
a posterior over parameters.

Must include **simulation-based calibration** diagnostics — rank statistics uniform under
the prior predictive. A posterior that fails SBC is not usable and must be rejected
automatically, not reported with a caveat.

The trained density estimator doubles as the emulator for `ensemble.py`.

### 6.7 `ensemble.py` (M5)

Three nested loops (`THEORY.md §7`):

| Loop | Draws over | Method |
|---|---|---|
| Inner | stochastic events | pseudo-RNG, seeded |
| Outer | parameter sets | **Sobol sequence QMC**, not pseudorandom |
| Ensemble | model structures | enumerate `configs/structures/` |

Required: **common random numbers** across compared scenarios. Provide an API that makes
CRN the default for any paired comparison and makes breaking it explicit.

Report between-structure variance separately from within-structure variance. Structural
uncertainty is expected to dominate; if the code cannot separate them, the ensemble is
pointless.

### 6.8 `search.py` (M7)

Adaptive rare-event search over VDG perturbations, via cross-entropy method or adaptive
importance sampling. Objective: find the **cheapest perturbation producing a
consequence above threshold**, where cost is a configurable function over the perturbation
set.

The fitness signal is the simulator's own deterministic output. There is no judge, no
rubric, no learned reward model, and none may be introduced.

Output: ranked minimum-cut sets with estimated probabilities and consequences, plus the
importance-sampling weights so the rare-event probability estimate is unbiased.

### 6.9 `analysis.py` (M8)

- Sobol first-order and total-order indices (`SALib`), not one-at-a-time sensitivity.
- **Provenance-grouped variance decomposition** — variance attributable to each
  `Provenance` class. The headline figure `"X% of output variance derives from parameters
  with no empirical support"` is a required output of every study run
  (`THEORY.md §6.5`).
- EVPPI per parameter and per parameter group, identifying the single highest-value
  measurement (`THEORY.md §9`).

---

## 7. Study runner

A study is declared in one YAML file and produces one immutable output directory:

```yaml
study: dialysis_scaffold_v1
structures: [expert_a, expert_b, learned, naive_independent]
n_parameter_draws: 1024        # Sobol
n_stochastic_reps: 100
population: {n: 100000, years: 100}
outputs: [scaffold_fraction, failure_consequence_curve, min_cut_sets,
          sobol, provenance_variance, evppi]
```

Output directory contains: run record, resolved parameters with provenance, all results,
figures, and a `PROVENANCE.md` in which every headline number is traced to its sources.

---

## 8. Acceptance tests

`tests/test_analytic_limits.py` is the gate. **If any of AT-1 through AT-4 fails, no other
result from the codebase may be reported anywhere, for any purpose.**

**AT-1 Hardy–Weinberg.** No selection, mutation, drift, or migration ⟹ genotype
frequencies constant to < 1e-12 over 1000 generations.

**AT-2 Selection–mutation balance.** Recessive deleterious allele, selection coefficient
_s_, mutation rate _μ_ ⟹ equilibrium frequency converges to √(μ/s) within 1%.

**AT-3 Wright–Fisher drift.** Variance of allele frequency change matches p(1−p)/(2N)
within Monte Carlo error over ≥10⁴ replicates.

**AT-4 Leslie eigenvalue.** Simulated long-run growth rate equals the dominant eigenvalue
of the projection matrix within 1e-6.

**AT-5 Reliability baseline.** Single node, constant hazard ⟹ simulated time-to-failure is
exponential (KS test, p > 0.05); MTBF within 1% of analytic.

**AT-6 Correlated failure.** Two nodes sharing an upstream node have joint failure
probability strictly greater than the product of their marginals, by the amount implied by
the specified conditional structure.

**AT-7 CF sanity.** Full restoration of viability with unchanged fertility ⟹ allele
frequency **does not increase** relative to its starting value over 20 generations
(`THEORY.md §3.3`). A model that shows the allele rising has a sign error.

**AT-8 Provenance.**
- 8.1 Every output number resolves via `trace()` to a complete parameter set.
- 8.2 `ELICITED` without a resolvable `elicitation_id` raises at construction.
- 8.3 Provenance-grouped variance decomposition sums to total variance within 2%.

**AT-9 Variance reduction.** Common random numbers reduce the variance of a paired scenario
comparison by ≥5× relative to independent streams on the reference test case.

**AT-10 SBC.** Simulation-based calibration rank statistics are uniform (χ², p > 0.05).

**AT-11 Determinism.** Identical `(config_hash, seed)` ⟹ bit-identical outputs across runs
and across machines.

**AT-12 Retrodiction (M9).** With parameters fixed independently of the event, the model
reproduces observed excess mortality from at least one documented scaffold-failure event
within its credible interval. **This is the project's primary kill criterion — see §11.**

---

## 9. Claim ladder

Every reported number is labeled with its tier. Enforce in the output layer.

- **Tier 1 — Analytic.** Follows from the equations; verified against closed form. High
  confidence. *Example: allele frequency does not increase under restored viability.*
- **Tier 2 — Retrodictive.** Reproduces observed historical data with independently-set
  parameters. Moderate confidence.
- **Tier 3 — Projective.** Forward scenarios. **Conditional, not predictive.** Must always
  appear with its provenance-variance figure attached.

A Tier 3 number may never be reported without its Tier 1 and Tier 2 support stated.

---

## 10. Reporting standards

The model description must satisfy the **ODD protocol**. The evaluation documentation must
satisfy **TRACE**. Uncertainty analysis must satisfy the **ISPOR–SMDM** modeling good
research practice for parameter uncertainty. Generate ODD and TRACE skeletons from the
codebase automatically — `scaffold odd` and `scaffold trace` — so documentation cannot
drift from implementation. See `THEORY.md §10`.

---

## 11. Kill criteria

Declared in advance. If met, stop.

1. **AT-12 fails.** If the model cannot retrodict a documented disruption event with
   independently-set parameters, the coupling is not capturing reality and the program
   stops. This is a ~3-month test, not a 3-year one.
2. **Provenance variance > 70%.** If more than 70% of output variance derives from
   `ELICITED` + `ASSUMED` parameters, the model is measuring the elicitation panel, not the
   world. Publish that finding and stop projecting.
3. **Structural spread exceeds the effect.** If between-structure variance exceeds the
   effect size being claimed, no structure-dependent claim may be made.

Commit to publishing each of these outcomes if they occur.

---

## 12. Use cases to support (in priority order)

Full detail in `THEORY.md §11`. The VDG schema must express all of these without
modification — if a new case requires a schema change, the schema is wrong.

1. **Dialysis** — the reference case. Large dependent population, fixed facilities, and
   documented natural experiments in scaffold failure. Build against this first.
2. **Insulin** — supply chain and cost-driven interruption.
3. **Transplant immunosuppression** — device-free, drug-absolute dependency.
4. **CF modulators** — the genetics-coupled case; also where the naive framing is tested.
5. **ART for HIV** — global scale, documented pandemic-era interruptions.
6. **Cold-chain biologics** — utility-coupled failure.
7. **Home oxygen / powered devices** — direct grid dependency.
8. **Non-health generalization** — any population whose viability has migrated onto
   engineered systems. The schema should already cover it.

---

## 13. Framing constraints (non-negotiable)

The eugenic framing of this subject matter is both ethically unacceptable and
**empirically the wrong variable** (`THEORY.md §12`).

- Prohibited in code, comments, docs, variable names, and output labels: "genetic
  deterioration," "degradation of the gene pool," "genetic quality," "dysgenic," "burden"
  applied to people, "defective."
- The measured quantity is **dependency and continuity of care**, not genetic fitness of
  populations.
- Outputs are counts of people at risk of care interruption, never rankings of genetic
  worth.
- The discussion section states this explicitly. It strengthens the work; it is not a
  disclaimer.

If a design decision seems to require the prohibited framing, the design decision is wrong.

---

## 14. Definition of done for v1.0

- AT-1 … AT-11 green in CI on Apple Silicon.
- AT-12 attempted and its outcome reported, whichever way it goes.
- One complete study (dialysis) runs end-to-end from a single YAML to a provenance-traced
  output directory.
- ODD and TRACE documents generated from the codebase.
- Every figure regenerable from `(config_hash, seed)`.
- `THEORY.md` updated with anything learned that contradicts it.
