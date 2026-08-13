# stewardsim Slice-0 Design

**Date:** 2026-08-12  
**Status:** Approved (brainstorming §1–§4)  
**Package:** `stewardsim`  
**Binding specs:** `files/GOAL.md` (install as `./GOAL.md`), `files/THEORY.md`, `files/DECISIONS.md`  
**Superseded:** `scaffold` / `ARCHIVE/` — not a build target  
**Approach:** A — Slice-0 package (restriction-loop on structural fixtures)

This document is the approved design. It is not an implementation plan and not a license to invent AT-12 numbers.

---

## Decisions locked in brainstorming

| ID | Decision |
|----|----------|
| B1 | Session purpose: how to start building `stewardsim` |
| B2 | First product: forced-intervention slice, not GOAL §5 linear milestones |
| B3 | Force the **restriction**; keep the loop (`policy ∘ feasibility ∘ adherence`) |
| B4 | Size the world to AT-12 needs |
| B5 | AT-12 class: single-institution formulary + antibiogram |
| B6 | Event **not chosen** — plug-in interface; no agent-written observed series |
| B7 | “Started” = restriction-loop runs on structural fixtures |
| B8 | Approach A: one package; only modules the loop calls |
| B9 | `GOAL_ABX.md` is a duplicate of `files/GOAL.md`; install as `./GOAL.md` and remove `GOAL_ABX.md` |

ADR-001, ADR-002, ADR-003 in `DECISIONS.md` remain accepted.

---

## 1. Architecture

Repo root is the package root. Name: `stewardsim`.

### Canonical layout (GOAL §3)

| Action | Path |
|--------|------|
| Install | `files/GOAL.md` → `./GOAL.md` |
| Install | `files/THEORY.md` → `./THEORY.md` |
| Install | `files/DECISIONS.md` → `./DECISIONS.md` |
| Install | `files/README.md`, `GOAL-v1-scaffold.md`, `THEORY-v1-scaffold.md` → `./ARCHIVE/` |
| Remove | `./GOAL_ABX.md` (content preserved as `./GOAL.md`) |
| Not build inputs | root `idea_*.md`, `harness_eng.md`, `memidea.md` |
| Do not execute | `artifacts/ironclad/*`, `docs/plans/2026-08-12-scaffold-slice0.md` (retired `scaffold` packet) |

`pyproject.toml`: Python 3.12, `uv`. Default dependencies: `numpy`, `scipy`, `pydantic>=2`, `pyyaml`, `pytest`, `hypothesis`. **Do not** add `sbi`, `torch`, or CUDA-only packages.

### Study kinds

| Kind | Slice-0 | Role |
|------|---------|------|
| `retrodiction` | yes | `ForcedRestriction` tape; AT-12 path when user files exist |
| `genetic_limit` | yes | Pathogen closed forms only (AT-1–4, 7) |
| `projection` | **no** | Stochastic unforced policy comparison — later |

### In Slice-0

- M0: `Provenance`, `Parameter`, `DistributionSpec`, `Claim`, run record
- `Host` with per-individual `exposure_history`
- `Policy` as a function of host state → ordered drugs
- `Feasibility` hard rules
- `AdherenceModel` (fidelity 1.0 required; drivers present so AT-14 is testable)
- `Determinant` with exposure-dependent selection and explicit `confers_resistance_to`
- `Importation` as a typed parameter object (rate may be zero; never a bare float)
- `ForcedRestriction` tape (drug ids × `[t0, t1]`)
- `simulate.py` coupling driver
- CLI: `stewardsim study | validate | odd | trace`

### Not in Slice-0

Units/staff mixing, HGT dynamics, compensation dynamics, ensemble/Sobol, SBI, search/regret, SIS transmission (AT-5/6 `not_run`), multi-structure YAML, any observed antibiogram numbers.

### Success criterion

One fixture YAML → immutable output directory + `PROVENANCE.md`. Restriction changes realized exposure and then determinant frequencies. AT-12 exits non-zero if event files are missing. Fixture output is software proof, not a scientific result.

---

## 2. Components and contracts

### M0 — do not redesign

Reuse `ARCHIVE/GOAL-v1-scaffold.md` §4.1–4.3 verbatim: `Provenance` enum, `Parameter`, `DistributionSpec` (quantiles in; inconsistent quantiles raise; `ELICITED` ⇒ resolvable `elicitation_id`).

`Claim(tier, value, unit, supports, provenance_variance)`. Tier 3 refused without `provenance_variance` and at least one Tier 1 and one Tier 2 support.

`RunRecord` written **before** any step; `config_hash` over canonicalized study + params.

### Hospital objects (Slice-0 fields)

- **Determinant** — `id`, `mechanism`, `confers_resistance_to`, `fitness_cost`, `acquisition`. `compensatable` / `hgt_rate` exist on the type; unused in Slice-0 dynamics.
- **Host** — `id`, typed demographic/comorbidity vectors (may be empty), `exposure_history` (drug, dose-days, time), `colonization`, `admission_source`. No `unit_trajectory` in Slice-0.
- **Policy** — rules: host state → ordered drug list; `reserve[]`; `duration` Parameter. Escalation/de-escalation types exist; Slice-0 uses empiric line 1 + culture delay as a point Parameter.
- **AdherenceModel** — `baseline_fidelity`, `deviation_drivers`, `deviation_target`. Uniform random substitute is forbidden.
- **ConstraintSet** — hard rules only (allergy, contraindication). Soft penalties later.
- **Importation** — `rate`, `determinant_mix`, `source_correlation`.
- **ForcedRestriction** — `{(drug_id, t0, t1)}`. In-window drugs are reserve/inadmissible. No RNG.

### Coupling (`simulate.py`)

1. For each time step and each host needing therapy: `drugs = adherence(feasibility(policy(host), host), host)`
2. Append `Exposure`; update population dose-days
3. `selection_coefficient(det) = f(realized exposure to drugs in confers_resistance_to)`
4. Update determinant frequencies (deterministic recursion or Wright–Fisher)
5. Next host sees updated frequencies when scoring “effective”

Primary fixture outputs: mean `rounds_to_effective`, determinant trajectories, `conflict_log`, adherence diagnostics. Reserve useful lifetime if `reserve` is non-empty. Resistance series and `rounds_to_effective` are always written together.

---

## 3. Data flow, time, AT-12 plug-in

**Clock:** discrete days. Episodes last `duration` days. Determinant update is daily from that day’s institution-wide realized exposure.

**Incidence:** configured `Parameter` (REGISTRY or ASSUMED). Not inferred from missing files.

**Truth ownership**

| State | Owner |
|-------|--------|
| Parameters + lock | immutable for a run |
| Restriction tape | input, no RNG |
| Hosts + `exposure_history` | `simulate.py` |
| Determinant frequencies | `pathogen.py` |
| Run identity | `provenance.py` |

**Planes:** `data/raw` ingest may use the network. `src/stewardsim` never does. `data/derived` hashes enter `config_hash`. `stewardsim study` reads configs + derived only.

**AT-12 plug-in** (event unset). All user-supplied; none invented:

1. `configs/locks/at12_<id>.yaml` — committed **before** derived observed series
2. `data/derived/event_<id>/restriction_tape.csv`
3. `data/derived/event_<id>/observed_series.json` + citation + hash
4. `data/derived/event_<id>/cohort.json` + citation + hash

Missing any file ⇒ AT-12 `BLOCK`, no results directory.

**Fixture study** (`test://shape`): structural hosts/drugs/tape only. Not an observed antibiogram claim.

---

## 4. Errors, framing, tests

### Errors

- Unseeded RNG, CUDA/`sbi`/`torch` in default extra, network inside `stewardsim study` → refuse
- `ELICITED` without id; elicited/data boundary violation → raise
- `retrodiction` without a restriction tape → refuse
- AT-12 without the four plug-in files → `BLOCK`
- Inconsistent quantiles → raise
- Emitted prescription violating a hard constraint → AT-13.1 fail
- No admissible drug → log conflict; do not invent a drug
- Agent-written observed series → delete; DATA-STOP

### Framing (GOAL §12)

Banned in `src/` and `tests/`: “inappropriate prescribing” as a clinician attribute, “prescriber error,” “compliance” applied to clinicians, “misuse.” Use *fidelity* or *adherence to policy*. No resistance-only figure writer.

### Tests (no event numbers)

Green in Slice-0: AT-1, 2, 3, 4, 7, 8.1, 8.2, 11, 13.2, 14.

`not_run` or explicit `BLOCK`: AT-5, 6, 8.3, 9, 10, 12, 13.1. AT-13.1 stays `not_run` until the ≥10⁶-episode no-violation campaign exists; parent AT-13 is not pass while 13.1 is `not_run`. An allergy unit test is not that campaign.

**Reporting gate:** GOAL §8 — if AT-1 through AT-5 fail, no scientific result may be reported. AT-5 is `not_run` in Slice-0. `stewardsim report` refuses Tier 2/3 until AT-5 is green or a new `DECISIONS.md` entry changes the gate. Fixture directories are not paper results.

---

## 5. Out of scope until a new design

M7 belief/Cooke (unless a Slice-0 parameter is actually ELICITED), M8 ensemble, M9 SBI, M10 search/regret, M11 full Sobol/EVPPI, v1.5 novel-agent, v2 network, units, HGT, four-structure YAML, named hospital event.

---

## Approval

Brainstorming §1–§4 approved 2026-08-12. Next: implementation plan via writing-plans, then execution only after that plan exists.
