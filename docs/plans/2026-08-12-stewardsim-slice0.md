# stewardsim Slice-0 Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A `stewardsim` package whose restriction-loop runs on structural fixtures: forced formulary tape → policy ∘ feasibility ∘ adherence → exposure-dependent selection → determinant frequencies, with AT-12 blocked until the user supplies event files.

**Architecture:** One package at repo root. Install the `files/` packet as canonical `GOAL.md` / `THEORY.md` / `DECISIONS.md` / `ARCHIVE/`. Implement only what the loop calls (Approach A). M0 contracts are copied from `ARCHIVE/GOAL-v1-scaffold.md` §4.1–4.3, not redesigned. Binding design: `docs/plans/2026-08-12-stewardsim-slice0-design.md`.

**Tech Stack:** Python 3.12, `uv`, `numpy`, `scipy`, `pydantic>=2`, `pyyaml`, `pytest`, `hypothesis`. No `sbi`, `torch`, or CUDA.

**Do not:** invent antibiogram numbers; execute the retired `scaffold` plan; add search/ensemble/SBI/units/HGT dynamics; report Tier 2/3 while AT-5 is `not_run`.

---

### Task 1: Install canonical spec layout

**Files:**
- Create: `GOAL.md`, `THEORY.md`, `DECISIONS.md`, `ARCHIVE/README.md`, `ARCHIVE/GOAL-v1-scaffold.md`, `ARCHIVE/THEORY-v1-scaffold.md`
- Delete: `GOAL_ABX.md` (content is `files/GOAL.md`)

**Step 1: Copy the packet**

```bash
cp files/GOAL.md GOAL.md
cp files/THEORY.md THEORY.md
cp files/DECISIONS.md DECISIONS.md
mkdir -p ARCHIVE
cp files/README.md ARCHIVE/README.md
cp files/GOAL-v1-scaffold.md ARCHIVE/GOAL-v1-scaffold.md
cp files/THEORY-v1-scaffold.md ARCHIVE/THEORY-v1-scaffold.md
rm GOAL_ABX.md
```

**Step 2: Verify**

```bash
diff -q files/GOAL.md GOAL.md
diff -q files/THEORY.md THEORY.md
test ! -e GOAL_ABX.md
test -f ARCHIVE/README.md
```

Expected: all diffs silent; `GOAL_ABX.md` gone.

**Step 3: Commit**

```bash
git add GOAL.md THEORY.md DECISIONS.md ARCHIVE GOAL_ABX.md
git commit -m "docs: install stewardsim v2 specs; retire GOAL_ABX.md name"
```

---

### Task 2: Package stub

**Files:**
- Create: `pyproject.toml`, `src/stewardsim/__init__.py`, `src/stewardsim/cli.py`, `tests/conftest.py`, `tests/test_deps.py`

**Step 1: Write `pyproject.toml`**

```toml
[project]
name = "stewardsim"
version = "0.1.0"
requires-python = "==3.12.*"
dependencies = [
  "numpy",
  "scipy",
  "pydantic>=2",
  "pyyaml",
]

[project.optional-dependencies]
dev = ["pytest", "hypothesis"]

[project.scripts]
stewardsim = "stewardsim.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/stewardsim"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

No `sbi`, `torch`, `cuda`.

**Step 2: Stub**

```python
# src/stewardsim/__init__.py
__version__ = "0.1.0"

# src/stewardsim/cli.py
def main() -> None:
    from stewardsim import __version__
    print(__version__)

# tests/test_deps.py
from pathlib import Path

def test_default_extra_forbids_sbi_torch_cuda():
    text = Path("pyproject.toml").read_text()
    for banned in ("sbi", "torch", "cuda", "cupy"):
        assert banned not in text.lower()
```

**Step 3: Sync and test**

```bash
uv lock && uv sync --extra dev
uv run python -c "import stewardsim; assert stewardsim.__version__=='0.1.0'"
uv run pytest tests/test_deps.py -q
```

Expected: PASS.

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock src/stewardsim/__init__.py src/stewardsim/cli.py tests/test_deps.py tests/conftest.py
git commit -m "build: stewardsim 0.1.0 package stub"
```

---

### Task 3: Parameter and Provenance (red)

**Files:**
- Create: `tests/test_params.py`, `tests/test_provenance.py`

**Step 1: Write failing tests**

```python
# tests/test_params.py
import pytest
from pydantic import ValidationError
from stewardsim.params import DistributionSpec, Parameter, Provenance

def test_parameter_requires_provenance():
    with pytest.raises((ValidationError, TypeError)):
        Parameter(
            name="x",
            distribution=DistributionSpec(family="point", fitted_params={"value": 1.0}),
            source="test",
        )

def test_elicited_without_id_raises():
    with pytest.raises(ValueError):
        Parameter(
            name="fitness_cost",
            provenance=Provenance.ELICITED,
            distribution=DistributionSpec(
                family="lognormal",
                quantiles={0.05: 0.01, 0.5: 0.05, 0.95: 0.2},
            ),
            source="panel",
            elicitation_id=None,
        )

def test_inconsistent_quantiles_raise():
    with pytest.raises(ValueError):
        DistributionSpec(family="lognormal", quantiles={0.05: 0.9, 0.5: 0.1, 0.95: 0.2})

def test_moments_only_rejected():
    with pytest.raises(ValueError):
        DistributionSpec(family="normal", fitted_params={"mean": 0.0, "sd": 1.0})
```

```python
# tests/test_provenance.py
import pytest
from stewardsim.params import DistributionSpec, Parameter, Provenance

def test_elicited_id_must_resolve(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="elicitation"):
        Parameter(
            name="hgt_rate",
            provenance=Provenance.ELICITED,
            distribution=DistributionSpec(
                family="lognormal",
                quantiles={0.05: 1e-6, 0.5: 1e-4, 0.95: 1e-2},
            ),
            source="panel",
            elicitation_id="missing_record",
        )
```

**Step 2: Run to verify fail**

```bash
uv run pytest tests/test_params.py tests/test_provenance.py -q
```

Expected: FAIL (import error).

**Step 3: Commit red tests**

```bash
git add tests/test_params.py tests/test_provenance.py
git commit -m "test: Parameter and Provenance gates (red)"
```

---

### Task 4: Implement params (green)

**Files:**
- Create: `src/stewardsim/params.py`
- Create: `configs/elicitation/.gitkeep`

**Step 1: Implement** `Provenance`, `DistributionSpec`, `Parameter` exactly as `ARCHIVE/GOAL-v1-scaffold.md` §4.1–4.3.

Rules:
- `family` in `lognormal|beta|gamma|normal|triangular|point|empirical`
- Quantiles required unless `family=="point"` (then `fitted_params={"value": ...}`) or `empirical`
- Fit by quantile loss; store `fitted_params` and residual
- 5th > 50th or 50th > 95th → `ValueError`
- `provenance==ELICITED` ⇒ `elicitation_id` set and `configs/elicitation/<id>.yaml` exists

**Step 2:**

```bash
uv run pytest tests/test_params.py tests/test_provenance.py -q
```

Expected: PASS.

**Step 3: Commit**

```bash
git add src/stewardsim/params.py configs/elicitation/.gitkeep
git commit -m "feat: Parameter and Provenance contracts"
```

---

### Task 5: Claim ladder

**Files:**
- Create: `tests/test_claim.py`
- Modify: `src/stewardsim/params.py` or Create: `src/stewardsim/claim.py`

**Step 1: Red test**

```python
import pytest
from stewardsim.claim import Claim

def test_tier3_requires_variance_and_supports():
    with pytest.raises(ValueError):
        Claim(value=1.0, unit="rounds", tier=3, supports=[], provenance_variance=None)

def test_tier3_requires_tier1_and_tier2_support():
    with pytest.raises(ValueError):
        Claim(
            value=1.0, unit="rounds", tier=3,
            supports=["c3"], provenance_variance=0.2,
        )

def test_valid_tier3():
    t1 = Claim(id="c1", value=0.0, unit="freq", tier=1, supports=[], provenance_variance=None)
    t2 = Claim(id="c2", value=0.1, unit="freq", tier=2, supports=["c1"], provenance_variance=None)
    Claim(
        id="c3", value=1.2, unit="rounds", tier=3,
        supports=["c1", "c2"], provenance_variance=0.4,
    )
```

**Step 2:** `uv run pytest tests/test_claim.py -q` → FAIL  
**Step 3:** Implement `Claim`  
**Step 4:** PASS  
**Step 5:** Commit `feat: Claim tier ladder`

---

### Task 6: Study config kinds

**Files:**
- Create: `src/stewardsim/study.py`, `tests/test_study.py`

**Step 1: Red tests**

- Parse YAML with `kind`, `hosts.n`, `hosts.years`
- `kind` ∈ `retrodiction|genetic_limit` only in Slice-0 (`projection` raises)
- `kind: retrodiction` without `restriction_tape` path raises
- `kind: projection` raises `ValueError` (not in Slice-0)
- Bare float `importation: 0.01` raises (must be `Importation` object / mapping)

**Step 2:** FAIL  
**Step 3:** Implement Pydantic `StudyConfig`  
**Step 4:** PASS  
**Step 5:** Commit `feat: study config kinds`

---

### Task 7: Run record

**Files:**
- Create: `src/stewardsim/provenance.py`, `tests/test_run_record.py`

**Step 1: Red tests**

- `start_run(config, seed, outdir)` writes `run_record.json` before returning
- Record contains `config_hash`, `seed`, `git_commit` or `dirty: true`, dependency versions
- Changing one YAML byte changes `config_hash`

**Step 2–5:** implement, green, commit `feat: append-only run record`

---

### Task 8: Determinant + pathogen analytic ATs

**Files:**
- Create: `src/stewardsim/pathogen.py`, `tests/test_analytic_limits.py` (AT-1, 2, 3, 4, 7)

**Step 1: Red tests** — copy acceptance criteria from `GOAL.md` §8:

- AT-1: neutral determinant, no selection/mutation/drift → frequency change `< 1e-12` over 1000 generations
- AT-2: equilibrium within 1% of `sqrt(mu/s)`
- AT-3: WF variance matches `p(1-p)/(2N)` within MC error, `>= 10**4` replicates, fixed seed
- AT-4: constant `s` → logistic trajectory rate `s`, error `< 1e-6`
- AT-7: withdraw selection, `fitness_cost==0` → frequency does not decline; with cost > 0, decline rate bounded above by the cost

**Step 2:** FAIL  
**Step 3:** Deterministic recursions + WF mode. Selection coefficient is a function argument, not a hidden constant.  
**Step 4:** PASS those five IDs  
**Step 5:** Commit `feat: pathogen dynamics; AT-1-4-7 green`

---

### Task 9: Host + exposure history

**Files:**
- Create: `src/stewardsim/host.py`, `tests/test_host.py`

**Step 1: Red tests**

- `Host` requires `exposure_history` list (may be empty)
- `append_exposure(drug_id, dose_days, t)` grows history; cannot collapse to a scalar rate on the object
- `cumulative_dose_days(drug_id)` sums history
- No `unit_trajectory` field required

**Step 2–5:** implement, green, commit `feat: Host exposure history`

---

### Task 10: Feasibility oracle

**Files:**
- Create: `src/stewardsim/feasibility.py`, `configs/constraints/slice0.yaml`, `tests/test_feasibility.py`

**Step 1: Red tests (AT-13)**

- Hard rule: allergy to drug A ⇒ A excluded with reason
- Seeded state where policy’s only drug is contraindicated ⇒ `conflict=True`, log entry
- Oracle is a pure function; no RNG

**Step 2–5:** implement mechanical rules only, commit `feat: feasibility oracle`

---

### Task 11: Policy + adherence

**Files:**
- Create: `src/stewardsim/policy.py`, `src/stewardsim/episode.py`, `tests/test_policy.py`, `tests/test_adherence.py`

**Step 1: Red tests (AT-14)**

- `baseline_fidelity=1.0` ⇒ executed drug list equals `feasibility(policy(host))` exactly, ≥1000 episodes, seed fixed
- `baseline_fidelity=0.7` ⇒ realized deviation frequency within MC error of `0.3`
- Deviation rate higher when a driver (e.g. `severity`) is high than when low — uniform random deviation fails
- Substitute comes from `deviation_target`, never `random.choice(all_drugs)`

**Step 2–5:** implement, green, commit `feat: policy and state-dependent adherence`

---

### Task 12: ForcedRestriction + Importation types

**Files:**
- Create: `src/stewardsim/restriction.py`, `src/stewardsim/importation.py`, `tests/test_restriction.py`, `tests/test_importation.py`

**Step 1: Red tests**

- `ForcedRestriction.play(t)` returns frozen drug ids; two plays bit-identical; module does not import `numpy.random`
- `Importation` requires `Parameter` fields; `Importation(rate=0.01)` (raw float) raises
- Zero rate is legal

**Step 2–5:** implement, commit `feat: ForcedRestriction and Importation`

---

### Task 13: Coupling driver

**Files:**
- Create: `src/stewardsim/simulate.py`, `tests/test_simulate.py`

**Step 1: Red tests**

Given two drugs `{A,B}`, one determinant conferring resistance to `A` only, restriction tape that bans `A` after day `T`:

- Before `T`, realized dose-days of `A` > 0 under a policy that prefers `A`
- After `T`, new `A` dose-days stop (feasibility treats `A` as inadmissible)
- Resistant frequency trajectory after `T` is not identical to an unrestricted control (same seed) — the tape changes selection
- `rounds_to_effective` is present in the result object next to frequencies
- Conflict log is a list (may be empty)

Use structural hosts created in the test, not files from `data/derived/event_*`.

**Step 2–5:** implement the loop from the design §2, commit `feat: restriction-loop coupling`

---

### Task 14: Fixture study runner + CLI

**Files:**
- Create: `src/stewardsim/runner.py`, `configs/studies/slice0_shape.yaml`, `tests/fixtures/shape/` (hosts/drugs/tape only; citation `test://shape`), `tests/test_study_runner.py`
- Modify: `src/stewardsim/cli.py`

**Step 1: Write `configs/studies/slice0_shape.yaml`**

```yaml
study: slice0_shape
kind: retrodiction
hosts: {n: 200, years: 1}
restriction_tape: tests/fixtures/shape/restriction_tape.csv
seed: 0
outputs: [rounds_to_effective, determinant_trajectories, conflict_log]
```

Tape and fixture JSON contain **no** real-hospital rates and no paper citation other than `test://shape`.

**Step 2: Red test** — `stewardsim study configs/studies/slice0_shape.yaml` writes `output/slice0_shape/<config_hash>/{run_record.json,results.json,PROVENANCE.md}`; `trace` on `mean_rounds_to_effective` lists every `Parameter`.

**Step 3–5:** implement runner (no sockets), green, commit `feat: stewardsim study runner`

---

### Task 15: AT-11 determinism

**Files:**
- Modify: `tests/test_analytic_limits.py`

**Step 1: Red test** — run fixture study twice; hash `results.json` identical.

**Step 2–5:** sort dicts; no `set` iteration in hashed output; no wall-clock in hashed files. Commit `fix: deterministic fixture outputs` (or `test: AT-11` if already deterministic).

---

### Task 16: Framing linter

**Files:**
- Create: `tests/test_framing.py`

**Step 1:** Grep `src/` and `tests/` for `inappropriate prescribing`, `prescriber error`, `compliance` (as clinician attribute), `misuse`. Fail on result keys `resistance` without sibling `rounds_to_effective`.

**Step 2:** PASS if clean; rename if not.

**Step 3:** Commit `test: framing lexicon`

---

### Task 17: AT-12 gate (no numbers)

**Files:**
- Create: `tests/test_at12_gate.py`, `data/raw/README.md`, `data/derived/README.md`, `configs/locks/README.md`

**Step 1: Red/green tests**

- `validate_at12(event_id)` returns `BLOCK` if any of lock, tape, observed_series, cohort is missing
- README files contain **no** integer death/resistance counts
- Filenames or values containing `mock`, `dummy`, `fake`, `placeholder` as an observed series are rejected

**Step 2:** Implement gate in `validate.py`. Do not create observed series files.

**Step 3:** Commit `feat: AT-12 plug-in gate`

---

### Task 18: Reporting + AT gate file

**Files:**
- Create: `src/stewardsim/reporting.py`, `src/stewardsim/validate.py`, `tests/test_reporting.py`

**Step 1: Red tests**

- `stewardsim odd` / `stewardsim trace` include every registered `Parameter.name`
- `stewardsim validate` writes `output/at_gate.json`
- AT-5, AT-6, AT-8.3, AT-9, AT-10, AT-12 are `not_run` or `BLOCK`
- `stewardsim report` exits non-zero if asked for Tier 2/3 (AT-5 not green)

**Step 2–5:** implement, commit `feat: odd/trace/validate; report refuses Tier 2/3`

---

### Task 19: Checkpoint — Slice-0 started

**Step 1: Run**

```bash
uv run pytest -q
uv run stewardsim study configs/studies/slice0_shape.yaml
uv run stewardsim validate
test -f output/slice0_shape/*/PROVENANCE.md
uv run stewardsim report; test $? -ne 0
```

**Step 2:** All Slice-0 tests PASS. Report refuses. AT-12 BLOCK without user files.

If anything is red, return to the first failing task. Do not start M7–M11, units, HGT, search, or a named event.

**Step 3:** Commit only if the working tree is dirty with fixes; otherwise stop.

---

## Anti-drift

- Every public function traces to `GOAL.md`, `THEORY.md`, a `DECISIONS.md` ADR, or the approved design.
- Do not fill AT-12 from Dingle, MRSA, or memory.
- Do not follow `docs/plans/2026-08-12-scaffold-slice0.md`.
- Do not add `sbi`/`torch`.
- `exposure_history` must not be replaced by a population prescribing rate.
- Deviation must not become uniform noise.

---

## Operator checklist

- [ ] Task 1: Install specs; remove `GOAL_ABX.md`
- [ ] Task 2: Package stub + deps test
- [ ] Task 3: Red params/provenance
- [ ] Task 4: Green params
- [ ] Task 5: Claim
- [ ] Task 6: Study config
- [ ] Task 7: Run record
- [ ] Task 8: Pathogen ATs
- [ ] Task 9: Host
- [ ] Task 10: Feasibility
- [ ] Task 11: Policy + adherence
- [ ] Task 12: Restriction + Importation
- [ ] Task 13: Coupling
- [ ] Task 14: Study runner
- [ ] Task 15: AT-11
- [ ] Task 16: Framing
- [ ] Task 17: AT-12 gate
- [ ] Task 18: Reporting
- [ ] Task 19: Checkpoint
