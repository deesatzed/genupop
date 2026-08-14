# DECISIONS.md — architecture decision record

Format: Context / Decision / Consequences / Status.

Rule: **acceptance tests are the contract.** Prose in `GOAL.md` may be revised freely.
Adding, changing, or removing an acceptance test requires an entry here.

---

## ADR-001 — Pivot from scaffold-dependency modeling to antimicrobial stewardship

**Date:** 2026-08-12
**Status:** Accepted

### Context

v1 specified `scaffold`: a coupled population–infrastructure simulator for
treatment-dependent viability, anchored on dialysis and validated against documented
scaffold-failure events (hurricane-related dialysis disruption).

Subsequent scoping identified antimicrobial resistance as a stronger application of the
same machinery, for reasons that are structural rather than preferential:

1. **Two genuinely evolving populations.** The pathogen population is literal population
   genetics — allele frequencies under selection, with drift, mutation and gene flow. The
   population-genetics core was decorative in the human-scaffold model; here it is
   load-bearing.
2. **Scaffold logic survives, with a sharper mechanism.** Effective antibiotics are a
   scaffold on which surgery, chemotherapy, transplant and neonatal care depend — but
   unlike dialysis, *this scaffold degrades because it is used*. Consumption is the failure
   mechanism.
3. **The fitness reframe is native.** Rounds-to-effective-therapy maps onto
   time-to-appropriate-therapy, an established clinical metric with a documented mortality
   association. No composite score needs inventing.
4. **Proposer/solver is not metaphor.** The pathogen population generates harder problems in
   direct response to prescribing policy.
5. **Better retrodiction targets.** Documented restriction interventions with time-resolved
   resistance response.

### Decision

Replace `scaffold` with `stewardsim`. One active `GOAL.md`, one active `THEORY.md`, both
v2.0. v1 documents move to `ARCHIVE/`, retained for reasoning, explicitly excluded as build
targets.

No shared "framework" package is extracted. Building an abstraction before two applications
exist is premature; the second application may prove it later.

### Consequences

**Carried unchanged:** environment constraints; `Provenance` / `Parameter` /
`DistributionSpec`; study runner pattern; claim ladder; reporting standards
(ODD, TRACE, ISPOR–SMDM); `ensemble`, `inference`, `analysis` modules; AT-1, AT-2, AT-3,
AT-8, AT-9, AT-10, AT-11.

**Replaced:**
- VDG / failure / consequence contracts → host, pathogen, policy, importation contracts
- AT-4 (Leslie eigenvalue) → AT-4 (logistic selection sweep)
- AT-5, AT-6 (reliability, correlated failure) → AT-5 (SIS equilibrium), AT-6 (importation limit)
- AT-7 (CF allele sanity) → AT-7 (resistance reversal bounded by fitness cost)
- AT-12 retrodiction target: disruption mortality → documented restriction intervention
- Framing constraints: eugenic framing → prescriber blame and stewardship-as-rationing

**Added:** AT-13 (feasibility oracle), AT-14 (state-dependent adherence); kill criterion 4
(no separable recommendation).

**Retired:** `genetics.py` applied to human populations; `demography.py`; `vdg.py`;
`reliability.py`. The genetics *mathematics* is retained in `pathogen.py`.

That the analytic core (AT-1 through AT-3) survives the pivot unchanged is the evidence
this is a redirection of a working formalism rather than a search for an application.

---

## ADR-002 — v1 scoped to a single institution with exogenous importation

**Date:** 2026-08-12
**Status:** Accepted

### Context

Cross-institution spillover is real and policy-relevant: unilateral stewardship investment
benefits neighbors, and their laxity imposes cost. But it requires transfer data,
multi-institution calibration, and it multiplies the parameter space. It is also not
unclaimed territory.

### Decision

v1 models a single institution. The rest of the world enters as one exogenous
`Importation` term. Network coupling is deferred to v2 and recorded in `THEORY.md §13`
rather than in the build spec, so it is not designed for prematurely.

### Consequences

`Importation` is specified as a first-class parameter object with its own provenance and
uncertainty (`GOAL.md §4.7`), never a hardcoded constant. v2 replaces the scalar rate with a
network coupling — a swap, not a rewrite. `AT-6` guards the seam.

Risk accepted: if the setting turns out to be importation-dominated, v1's conclusions are
conditional on an assumed import rate. This is why `importation_dominated` is one of the
four ensemble structures rather than an afterthought.

---

## ADR-003 — Guideline-conflict discovery becomes a module, not a project

**Date:** 2026-08-12
**Status:** Accepted

### Context

Automated guideline-conflict discovery under multimorbidity was considered as a standalone
project. It is a constraint-satisfaction search over a static rule set: nothing evolves,
nothing propagates, no state carries forward. Population modeling would enter only as a
prevalence weight.

### Decision

Implement it as `feasibility.py` — the admissibility oracle inside `stewardsim`.

### Consequences

Two nested unfakeable oracles: feasibility (is this policy clinically admissible for this
host state?) and consequence (what does it do to the pathogen population?). Feasibility
prunes the search space at zero simulation cost, which is what makes searching a large
policy space tractable.

The conflict log remains a deliverable in its own right (`THEORY.md §7`) and may be
published separately.

---

## ADR-004 — Scenarios are the product; AT-12 is an optional back-test

**Date:** 2026-08-14
**Status:** Accepted

### Context

AT-12 was written as a paper kill criterion: match a *documented historical*
restriction with independently locked parameters. The operator's purpose is
Antibiotic Stewardship Committee what-ifs: different restriction dates, drugs,
and starting antibiograms. Treating AT-12 `BLOCK` as "you may not model a
restriction" blocked that purpose.

### Decision

1. **What-if restrictions are in scope.** Choosing a ban day/date is a lever,
   not a missing event file.
2. **AT-12 does not gate `stewardsim scenario`.** `BLOCK` means "no historical
   back-test is available," not "do not run."
3. **Committee output must show both sides:** resistance **and** empiric
   adequacy (rounds / first-line miss), with vs without the restriction.
   Resistance-only cards are a defect (GOAL §12.2).
4. **AT-12 remains optional.** If a real past formulary change is later named,
   lock parameters first, then compare. Until then, every number is a
   conditional scenario, not a retrodiction.

### Consequences

Scenario CLI is the stewardship surface. Paper-style AT-12 can wait. Labels
must say the run is not a history-match.
