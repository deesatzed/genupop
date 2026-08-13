# GOAL.md — `stewardsim`

**Version:** 2.0
**Date:** 2026-08-12
**Supersedes:** `ARCHIVE/GOAL-v1-scaffold.md`
**Status:** Active build target
**Scope:** v1 only — single institution, exogenous importation. Roadmap in `THEORY.md §13`.

> Read `THEORY.md` before writing code.
>
> `ARCHIVE/` contains the superseded scaffold-dependency specification. It is historical
> context only. **Nothing in `ARCHIVE/` is a build target.**

---

## 0. Purpose

Empiric antimicrobial prescribing policy is chosen against a pathogen population that
evolves in response to the policy. The choice is made per patient from individual risk
factors; the consequence accrues to the population; the changed population alters the next
clinician's optimal choice.

`stewardsim` models that loop at individual level and searches for **empiric policies that
perform acceptably across all plausible resistance-dynamics mechanisms and under realistic,
non-random guideline adherence** — rather than optimally under one assumed mechanism and
perfect compliance.

Primary output: a **minimum-regret empiric policy under structural uncertainty**, reported
with provenance-weighted uncertainty and an adherence-robustness curve.

---

## 1. Non-goals

- **NOT an individual outcome prediction model.** No P(mortality | features). Saturated
  space, different question.
- **NOT a claim that resistance evolves under selection pressure.** Settled since the 1990s
  (`THEORY.md §3`). Implement it correctly, test against closed form, claim nothing.
- **NOT another cycling-vs-mixing comparison.** Answered, and the answer is unexciting
  (`THEORY.md §3.4`). If the search rediscovers it, that is verification, not a finding.
- **NOT a compartmental SIS remake.** The contribution is individual-level host state with
  endogenous policy feedback. If the model reduces to two compartments without loss, it has
  failed.
- **NOT an LLM or agent system.** No language models in the simulation loop. Permitted ML is
  the calibration surrogate (§6.9) and the search proposer (§6.10), both numerical.
- **NOT clinical decision support.** Population policy only. No module accepts or emits an
  identified patient record.
- **NOT a network model in v1.** The rest of the world is one exogenous importation term.
  See §4.7 — the seam matters more than the term.

---

## 2. Environment constraints

*(Unchanged from v1.)*

| Constraint | Value |
|---|---|
| Target hardware | Apple Silicon (M4, 64 GB) |
| Accelerator | CPU + Metal (MPS). **No CUDA.** |
| Python | 3.12 |
| Package manager | `uv` |
| Determinism | Reproducible from `(config_hash, seed)`. No unseeded RNG. |
| Parallelism | `joblib` / `multiprocessing`; vectorize before parallelizing |

**Permitted:** `numpy`, `scipy`, `pandas`/`polars`, `networkx`, `pydantic` v2, `numba`,
`pyyaml`, `pytest`, `hypothesis`, `matplotlib`, `arviz`, `sbi` (PyTorch/MPS), `SALib`.

**Forbidden:** CUDA-only dependencies; network calls at simulation runtime; non-permissive
licenses.

---

## 3. Repository layout

```
stewardsim/
├── GOAL.md                  # this file  (v2.0)
├── THEORY.md                # reference  (v2.0)
├── DECISIONS.md             # ADR log; entry 001 = the pivot from scaffold
├── ARCHIVE/
│   ├── README.md            # "Superseded. Reference only. Do NOT build from this."
│   ├── GOAL-v1-scaffold.md
│   └── THEORY-v1-scaffold.md
├── pyproject.toml
├── src/stewardsim/
│   ├── provenance.py        # M0  audit trail                [carried from v1]
│   ├── params.py            # M0  provenance-tagged params    [carried from v1]
│   ├── pathogen.py          # M1  resistance determinant dynamics
│   ├── host.py              # M2  individual hosts + exposure history
│   ├── transmission.py      # M3  within-institution transmission + importation
│   ├── feasibility.py       # M4  constraint / guideline-conflict oracle
│   ├── policy.py            # M5  policy representation + adherence model
│   ├── episode.py           # M5  treatment episode, lines of therapy, rounds
│   ├── simulate.py          # M6  the coupling driver
│   ├── belief.py            # M7  elicitation ingest, expert DAGs
│   ├── ensemble.py          # M8  three-loop MC                [carried from v1]
│   ├── inference.py         # M9  SBI calibration              [carried from v1]
│   ├── search.py            # M10 adaptive policy search
│   ├── regret.py            # M10 minimum-regret selection
│   ├── analysis.py          # M11 Sobol, provenance variance, EVPPI [carried]
│   └── validate.py          # analytic limits + retrodiction harness
├── configs/
│   ├── structures/          # competing resistance-dynamics mechanisms
│   ├── elicitation/         # SHELF / Cooke records
│   ├── constraints/         # feasibility rule sets
│   └── studies/
├── tests/
└── data/{raw,derived}/
```

---

## 4. Data contracts

Define in `pydantic` v2 before any simulation code.

### 4.1 Provenance and Parameter — carried from v1 unchanged

The `Provenance` enum (`TRIAL`, `REGISTRY`, `OBSERVATIONAL`, `MECHANISTIC`, `ELICITED`,
`ASSUMED`), `Parameter`, and `DistributionSpec` are reused verbatim from
`ARCHIVE/GOAL-v1-scaffold.md §4.1–4.3`. Quantile-based elicitation, overconfidence
correction, and the `ELICITED ⟹ elicitation_id` invariant all still apply.

This is the reusable spine. **Do not redesign it.**

### 4.2 Resistance determinant

```python
class Determinant(BaseModel):
    id: str
    mechanism: Literal["chromosomal_mutation","plasmid","efflux","enzymatic","target_mod"]
    confers_resistance_to: list[str]        # drug ids — cross-resistance is explicit
    fitness_cost: Parameter                 # in absence of drug; may be ~0
    compensatable: bool
    compensation_rate: Parameter | None
    acquisition: Literal["de_novo","horizontal","imported"]
    hgt_rate: Parameter | None              # required iff acquisition == "horizontal"
```

Fitness cost and compensability determine whether resistance is reversible after
withdrawal, and they are the parameters with the least data. Expect `ELICITED`; measure
their variance contribution (`AT-8.3`).

### 4.3 Host individual

```python
class Host(BaseModel):
    id: int
    demographics: DemographicVector
    comorbidity: ComorbidityVector
    unit_trajectory: list[UnitStay]
    exposure_history: list[Exposure]        # drug, dose-days, timing — per individual
    colonization: dict[str, StrainState]    # organism -> carried determinants
    admission_source: Literal["community","transfer","post_acute","readmission"]
```

**`exposure_history` at individual level is the point of the model.** Compartmental models
cannot represent it. If it is ever collapsed to a population prescribing rate, the
contribution is gone.

### 4.4 Prescribing policy

```python
class Policy(BaseModel):
    id: str
    rules: list[PolicyRule]         # host state -> ordered drug preference
    escalation: EscalationRule
    de_escalation: DeEscalationRule # on culture return
    duration: Parameter
    reserve: list[str] = []         # drugs restricted from empiric use
```

A policy is a *function from host state to an ordered drug preference*, not a fixed
regimen. The search in M10 operates over this object.

### 4.5 Adherence — state-dependent, not noise

```python
class AdherenceModel(BaseModel):
    baseline_fidelity: Parameter
    deviation_drivers: dict[str, Parameter]   # severity, off_hours, atypical, ...
    deviation_target: DeviationTarget          # what clinicians switch TO
```

**Deviation must be a function of host state.** Clinicians deviate more for sicker
patients, at night, and for atypical presentations (`THEORY.md §6`). Modeling
non-adherence as random noise is a specification error, not a simplification — and it
destroys the confounding analysis in §6.7.

### 4.6 Feasibility constraints

```python
class ConstraintSet(BaseModel):
    hard: list[Rule]     # allergy, absolute contraindication, renal cutoff, pregnancy
    soft: list[Rule]     # relative, with penalty weight
    sources: list[str]   # guideline provenance
```

### 4.7 Importation — the v2 seam

```python
class Importation(BaseModel):
    rate: Parameter                       # colonized arrivals per admission
    determinant_mix: dict[str, Parameter]
    source_correlation: Parameter         # temporal clustering of imports
```

**A first-class parameter object with its own provenance and uncertainty — never a
hardcoded constant.** v2 replaces the scalar rate with a network coupling. Get this
interface right now and the extension is a swap; get it wrong and it is a rewrite.

---

## 5. Milestones

Do not begin a milestone until the previous one's tests are green.

| M | Module(s) | Ships |
|---|---|---|
| M0 | `provenance`, `params` | Carried from v1; verify tests still pass |
| M1 | `pathogen` | Determinant dynamics: selection, drift, mutation, HGT, compensation |
| M2 | `host` | Individual population, exposure histories, colonization |
| M3 | `transmission` | Within-institution transmission + exogenous importation |
| M4 | `feasibility` | Constraint oracle — prunes the policy space |
| M5 | `policy`, `episode` | Policy representation, state-dependent adherence, rounds |
| M6 | `simulate` | **The coupling. This is the contribution.** |
| M7 | `belief` | Elicitation ingest, expert DAGs, priors |
| M8 | `ensemble` | Three-loop MC over the structural ensemble |
| M9 | `inference` | SBI calibration with SBC diagnostics |
| M10 | `search`, `regret` | Policy search + minimum-regret selection |
| M11 | `analysis` | Sobol, provenance variance, EVPPI |
| M12 | — | Retrodiction against a documented restriction intervention |

**M6 before M7–M11.** The coupling is the novel object; everything after is apparatus.

---

## 6. Module specifications

### 6.1 `pathogen.py` (M1)

Deterministic recursions plus Wright–Fisher stochastic mode over determinant frequencies.

Required:
- Selection with a **drug-exposure-dependent selection coefficient** — a function of
  realized population drug exposure, not a fixed parameter. This is the channel through
  which policy acts, and it is what makes the model endogenous.
- Fitness cost in absence of drug, with optional compensatory evolution.
- Horizontal gene transfer for plasmid-borne determinants.
- **Cross-resistance explicit** via `confers_resistance_to`. Implicit one-drug-one-
  determinant mappings are forbidden — they are the main reason simple models overstate the
  benefit of drug diversification.

### 6.2 `host.py` (M2)

Individual-based, 10⁴–10⁵ hosts. Each carries §4.3 state including per-individual cumulative
drug exposure in dose-days by agent, with decay.

### 6.3 `transmission.py` (M3)

Within-institution transmission with unit structure (shared units, shared staff), plus
importation per §4.7. Colonization pressure derives from the colonized fraction **in the
relevant unit**, not the whole institution. Homogeneous mixing exists only as the naive
lower-bound structure in the ensemble.

### 6.4 `feasibility.py` (M4) — the constraint oracle

Given `(Host, Policy)`, return admissible drugs and the reason for each exclusion. Detect
contradiction: a state where hard constraints admit no drug the policy would select.

Two roles:
1. **Pruning** — reject inadmissible policies before simulation, at zero simulation cost.
2. **Discovery** — log every host state where constraints conflict. That log is a
   deliverable in its own right (`THEORY.md §7`).

Mechanical only. No learned component, no scoring model, no judgment.

### 6.5 `policy.py` + `episode.py` (M5)

An episode proceeds in **lines of therapy**: line 1 empiric per policy, filtered by
feasibility, modulated by adherence; culture returns at a sampled delay; de-escalation or
escalation follows.

**Rounds = lines of therapy to a verified-effective agent.** `rounds_to_effective` is the
primary individual-level fitness quantity. Its population mean is the model's analogue of
time-to-appropriate-therapy, which has an established association with mortality
(`THEORY.md §5`). **Do not invent a composite score to replace it.**

Adherence per §4.5: sample deviation as a function of host state; when deviation occurs,
select the substitute from `deviation_target`, never uniformly at random.

### 6.6 `simulate.py` (M6) — the coupling

```
host states + current determinant frequencies
        │
        ▼
  per-patient empiric choice   ← policy ∘ feasibility ∘ adherence
        │
        ▼
  realized population drug exposure
        │
        ▼
  selection coefficients on determinants
        │
        ▼
  determinant frequencies (t+1)  →  next patient's optimal choice
```

Primary outputs:

1. **Mean rounds-to-effective-therapy** over time, by subgroup.
2. **Determinant frequency trajectories** under each policy.
3. **Reserve-agent useful lifetime** — time until resistance to a reserved agent crosses a
   threshold.
4. **Adherence-robustness curve** — output (1) as a function of `baseline_fidelity`.
5. **Constraint-conflict log** from M4.

Also required: a mode emitting synthetic observational datasets with the deviation
mechanism known, for §6.7.

Performance target: 10⁴ hosts × 5 years × 100 stochastic reps under 120 s on one M4 core.

### 6.7 Confounding-by-indication analysis (M6, secondary)

Generate data under a known state-dependent deviation mechanism, run a standard
observational adherence–outcome analysis on it, report the bias.

Deliverable: **how much of the observed association between guideline non-adherence and
worse outcomes is attributable to informative deviation** (`THEORY.md §6.3`). Keep cleanly
separable — this is a methods contribution independent of stewardship and may be reported
on its own.

### 6.8 `belief.py` (M7)

Carried from v1 §6.5: SHELF and Cooke's Classical Model with seed questions and performance
weights; overconfidence correction; the **frozen elicited/data boundary enforced in code**.

Elicitation targets for v1, declared in advance: `fitness_cost`, `compensation_rate`,
`hgt_rate`, `deviation_drivers`, `source_correlation`, and cross-resistance structure.
Nothing else.

### 6.9 `ensemble.py` (M8) + `inference.py` (M9)

Carried from v1 unchanged in mechanism. Three loops — inner stochastic (seeded), outer
parameter (Sobol QMC), ensemble structural. Common random numbers default for paired
comparisons. NPE with mandatory SBC; a posterior failing SBC is auto-rejected.

**Structural ensemble for v1** — at minimum these four, in `configs/structures/`:

| Structure | Dominant mechanism |
|---|---|
| `mutation_driven` | De novo chromosomal mutation under selection |
| `plasmid_driven` | Horizontal transfer dominates |
| `clonal_expansion` | Transmission of a resistant clone dominates |
| `importation_dominated` | Most resistance arrives from outside |

These imply **different interventions**, the field disagrees about which dominates, and a
policy optimized for the wrong one can be harmful. Reporting between-structure spread is
mandatory.

### 6.10 `search.py` + `regret.py` (M10)

Adaptive search over `Policy` space, feasibility pruning applied first.

`regret.py`: for each candidate policy compute regret against the best achievable policy
**under each structure**, then select the policy minimizing maximum regret across the
ensemble (`THEORY.md §9`).

The objective is the simulator's own computed output. No judge, no learned reward model, no
rubric — and none may be introduced.

### 6.11 `analysis.py` (M11)

Carried from v1. Sobol first- and total-order; **provenance-grouped variance decomposition**
with the headline figure; EVPPI per parameter group.

---

## 7. Study declaration

```yaml
study: empiric_gram_negative_v1
structures: [mutation_driven, plasmid_driven, clonal_expansion, importation_dominated]
n_parameter_draws: 1024          # Sobol
n_stochastic_reps: 100
hosts: {n: 20000, years: 5}
adherence_sweep: [1.0, 0.9, 0.8, 0.7, 0.6]
policies: {search: true, seed_policies: [current_standard, guideline_strict]}
outputs: [rounds_to_effective, determinant_trajectories, reserve_lifetime,
          adherence_curve, conflict_log, minimum_regret_policy,
          sobol, provenance_variance, evppi]
```

One immutable output directory per study: run record, resolved parameters with provenance,
results, figures, and `PROVENANCE.md` tracing every headline number.

---

## 8. Acceptance tests

`tests/test_analytic_limits.py` is the gate. **If AT-1 through AT-5 fail, no result from
this codebase may be reported anywhere, for any purpose.**

**AT-1 Hardy–Weinberg.** Neutral determinant, no selection/mutation/drift ⟹ frequency
constant to < 1e-12 over 1000 generations. *[carried from v1]*

**AT-2 Selection–mutation balance.** Equilibrium converges to √(μ/s) within 1%. *[carried]*

**AT-3 Wright–Fisher drift.** Variance of frequency change matches p(1−p)/(2N) within Monte
Carlo error over ≥10⁴ replicates. *[carried]*

**AT-4 Selection sweep.** Constant selection coefficient _s_ ⟹ resistant fraction follows the
logistic trajectory with rate _s_, within 1e-6. *[new — replaces v1 AT-4]*

**AT-5 SIS equilibrium.** No treatment, homogeneous mixing ⟹ colonization prevalence
converges to the analytic endemic equilibrium (1 − 1/R₀) within 1%. *[new]*

**AT-6 Importation limit.** Zero transmission, constant importation ⟹ prevalence converges
to the importation/clearance ratio within 1%. *[new — guards the v2 seam]*

**AT-7 Resistance reversal.** Withdraw selection ⟹ determinant frequency declines at a rate
bounded above by its fitness cost; **with zero fitness cost it does not decline**. A model
showing costless resistance reverting has a sign error. *[new — replaces v1 AT-7]*

**AT-8 Provenance.** *[carried]*
- 8.1 Every output resolves via `trace()` to a complete parameter set.
- 8.2 `ELICITED` without resolvable `elicitation_id` raises at construction.
- 8.3 Provenance-grouped variance sums to total within 2%.

**AT-9 Variance reduction.** Common random numbers reduce paired-comparison variance ≥5×.
*[carried]*

**AT-10 SBC.** Rank statistics uniform (χ², p > 0.05). *[carried]*

**AT-11 Determinism.** Identical `(config_hash, seed)` ⟹ bit-identical outputs. *[carried]*

**AT-12 Retrodiction.** With parameters fixed independently of the event, the model
reproduces the observed resistance trajectory from a documented restriction intervention
within its credible interval. **Primary kill criterion — §10.** *[new target]*

**AT-13 Feasibility oracle.** *[new]*
- 13.1 No simulated prescription violates a hard constraint, over ≥10⁶ episodes.
- 13.2 The oracle detects a deliberately seeded constraint conflict.

**AT-14 Adherence.** *[new]* At `baseline_fidelity = 1.0` the executed policy equals the
specified policy exactly. Below 1.0, realized deviation frequency matches specification
within Monte Carlo error, **and deviation correlates with the specified drivers** — a model
deviating uniformly at random fails this test.

---

## 9. Claim ladder

*(Carried from v1, unchanged in structure.)*

- **Tier 1 — Analytic.** Verified against closed form. *Example: costless resistance does not
  revert on withdrawal.*
- **Tier 2 — Retrodictive.** Reproduces observed data with independently-set parameters.
- **Tier 3 — Projective.** Conditional scenarios. Must always carry the provenance-variance
  figure and the between-structure spread.

Enforce in the output layer. A Tier 3 number may not be reported without its Tier 1 and
Tier 2 support stated.

---

## 10. Kill criteria

Preregistered. If met, stop and publish the outcome.

1. **AT-12 fails.** The coupling does not reproduce a documented intervention with
   independently-set parameters. ~3-month test.
2. **Provenance variance > 70%** from `ELICITED` + `ASSUMED`. The model is measuring the
   elicitation panel.
3. **Between-structure variance exceeds the effect size.** No structure-dependent claim may
   be made.
4. **No separable recommendation.** If the minimum-regret policy is statistically
   indistinguishable from current standard practice across all four structures, there is no
   recommendation to make. Report that and stop. *[new in v2]*

Commit in advance to publishing each outcome if it occurs.

---

## 11. Reporting standards

ODD for model description, TRACE for evaluation documentation, ISPOR–SMDM for uncertainty
analysis. Generate ODD and TRACE skeletons from the codebase (`stewardsim odd`,
`stewardsim trace`) so documentation cannot drift from implementation. Preregister
predictions and kill criteria before M12. *(Carried from v1.)*

---

## 12. Framing constraints (non-negotiable)

**The v1 eugenics constraint no longer applies. Two different landmines replace it.**

### 12.1 Prescriber blame

"Non-adherence causes resistance" reads as clinicians being the problem, and it is
empirically shaky given informative deviation (`THEORY.md §6.3`).

- Deviation is modeled and reported as a **system property with measurable drivers**, never
  as individual failure.
- Prohibited in code, comments, docs, and outputs: "inappropriate prescribing" as an
  attribute of a clinician, "prescriber error," "compliance" applied to clinicians (use
  *fidelity* or *adherence to policy*), "misuse."
- The confounding analysis (§6.7) is reported alongside any adherence–outcome result, not
  after it.

### 12.2 Stewardship as rationing

Restriction policies are read politically as withholding care.

- **Always report both directions:** resistance trajectory *and* rounds-to-effective-therapy
  by subgroup. A policy that reduces resistance while increasing time-to-effective-therapy
  for a subgroup must show both, in the same figure.
- Never report a resistance-only objective. The tradeoff must be visible, not assumed away.
- Report subgroup effects. Acceptable aggregate performance with concentrated harm in one
  subgroup is a finding, not a rounding error.

If a design decision seems to require either prohibited framing, the design decision is
wrong.

---

## 13. Definition of done for v1.0

- AT-1 … AT-11, AT-13, AT-14 green in CI on Apple Silicon.
- AT-12 attempted and its outcome reported, whichever way it goes.
- One complete study end-to-end from a single YAML to a provenance-traced directory.
- Adherence-robustness curve across the specified fidelity sweep.
- Confounding-by-indication bias quantified and separable.
- Constraint-conflict log produced and clinically reviewed.
- ODD and TRACE generated from the codebase.
- Every figure regenerable from `(config_hash, seed)`.
- `THEORY.md` updated with anything learned that contradicts it.
- `DECISIONS.md` entry for every acceptance test added, changed, or removed.
