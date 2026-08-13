# THEORY.md — reference for `stewardsim`

**Version:** 2.0
**Date:** 2026-08-12
**Supersedes:** `ARCHIVE/THEORY-v1-scaffold.md`
**Status:** Active reference

Companion to `GOAL.md`. Read this first.

> **Citation note.** References locate the correct literature; they are not a verified
> bibliography. Check every one against the primary source before it appears in a
> manuscript. Items marked **[verify]** need particular care.

---

## 1. The question

Empiric antimicrobial therapy is chosen before the organism is known. The choice is made
per patient from individual risk factors. Its consequence — selection pressure — accrues to
a shared pathogen population. That population then determines what the *next* clinician
should choose.

This is a closed loop with the decision at individual level and the consequence at
population level. Standard stewardship analysis breaks the loop: it compares fixed policies
under an assumed resistance mechanism and perfect compliance, then recommends the winner.

Three things are wrong with that:

1. **The mechanism is not known.** Mutation-driven, plasmid-driven, clonal, and
   importation-dominated dynamics imply different optimal policies, and the field has not
   settled which dominates in any given setting.
2. **Compliance is not perfect, and non-compliance is not random.** Real programs achieve
   perhaps 60–80% fidelity, and deviation concentrates on sicker, atypical, off-hours cases.
3. **The individual-level state that drives the decision is discarded.** Prior antibiotic
   exposure is among the strongest predictors of carrying resistance, and compartmental
   models cannot carry it.

`stewardsim` restores the loop and asks a different question: not *which policy is best*,
but **which policy is least bad across everything we don't know.**

---

## 2. Two coupled populations

The formalism is a coupled system:

```
HOST POPULATION                          PATHOGEN POPULATION
individuals with                         determinant frequencies with
  demographics                             fitness costs
  comorbidity                              compensatory evolution
  unit trajectory                          horizontal transfer
  exposure history      ── selection ──▶   cross-resistance structure
  colonization state                              │
        ▲                                         │
        │                                         │
        └──────── empiric choice ◀────────────────┘
                  policy ∘ feasibility ∘ adherence
```

Both are genuine populations with genuine evolutionary dynamics. The pathogen side is
literal population genetics — allele frequencies under selection, with drift, mutation and
gene flow. The host side supplies the selection pressure and receives the consequence.

**Note on module reuse.** The population-genetics machinery specified for the superseded
scaffold project (`ARCHIVE/`) is not merely reusable here — it is *more apt*. Hardy–Weinberg,
selection–mutation balance and Wright–Fisher drift describe the pathogen population
correctly and directly. That the mathematical core survives the pivot unchanged is
evidence the pivot is sound rather than opportunistic.

---

## 3. Prior work — what is settled

**Do not claim novelty for anything in this section.**

- Bonhoeffer, Lipsitch & Levin (1997), *PNAS* — evaluating treatment protocols to prevent
  resistance. The foundational modeling paper.
- Lipsitch, Bergstrom & Levin (2000), *PNAS* — epidemiology of resistance in hospitals;
  paradoxes and prescriptions.
- Austin & Anderson (1999), *Phil. Trans. R. Soc. B* — transmission dynamics of resistance
  in hospital settings. **[verify]**
- Bergstrom, Lo & Lipsitch (2004), *PNAS* — ecological theory suggests antimicrobial
  **cycling will not reduce resistance** in hospitals. §3.4 below.
- Andersson & Hughes (2010), *Nature Reviews Microbiology* — fitness cost of resistance and
  whether resistance is reversible. The key reference for `Determinant.fitness_cost` and
  `compensatable`.
- Blanquart (2019), *Evolutionary Applications* — evolutionary epidemiology of resistance.
  **[verify]**
- Niewiadomska et al. (2019), *BMC Medicine* — review of population-level AMR models.
  **[verify]**
- van Kleef, Robotham et al. — review of hospital transmission models. **[verify]**

### 3.1 Fitness cost and reversibility

Resistance determinants generally impose a fitness cost in the absence of drug — but the
cost is often small, and **compensatory mutations can restore fitness while retaining
resistance**. This is why withdrawal of a drug frequently fails to reverse resistance at
the rate naive models predict.

Encoded as `AT-7`: with zero fitness cost, frequency must not decline on withdrawal. A model
showing costless resistance reverting has a sign error.

### 3.2 Cross-resistance

Determinants confer resistance to *classes*, not single agents, and plasmids carry multiple
determinants together. Models that map one drug to one determinant systematically overstate
the benefit of diversifying prescribing. `GOAL.md §4.2` makes cross-resistance explicit and
forbids implicit mappings.

### 3.3 Horizontal gene transfer

Plasmid-borne resistance spreads between lineages and between species, decoupling resistance
frequency from clonal dynamics. This is one of the four competing structures (§8) because
its dominance is genuinely contested and it implies different interventions — infection
control rather than prescribing change.

### 3.4 Cycling versus mixing — settled, do not revisit

Antibiotic cycling has been modeled extensively and the theoretical result is consistently
that it does not outperform mixing, and often underperforms it. If the policy search in M10
rediscovers this, treat it as **verification that the search works**, not as a finding.

---

## 4. The gap this project fills

Nearly all of the above is **compartmental**: susceptible/resistant compartments,
homogeneous mixing, one aggregate prescribing rate. That structure cannot represent:

| Missing | Why it matters |
|---|---|
| Individual exposure history | Prior antibiotic exposure is among the strongest predictors of carrying resistance |
| Individual-level empiric choice | The decision is made from patient risk factors, not from a population rate |
| Endogenous policy feedback | Population resistance changes the next clinician's optimal choice |
| State-dependent adherence | Deviation concentrates on sicker, atypical, off-hours cases |
| Correlated importation | Imports cluster in time and source; independence understates outbreak tails |
| Structural uncertainty | Four plausible mechanisms, different optimal policies, no consensus |

The contribution is the **coupling with individual state retained**, plus the decision-
theoretic treatment of not knowing which mechanism is operating.

---

## 5. Fitness: rounds to effective therapy

`rounds_to_effective` — lines of therapy until a verified-effective agent is reached — is
the individual-level fitness quantity.

This is not an imposed objective. Its population analogue, **time to appropriate therapy**,
is an established clinical metric with a well-documented association with mortality in
serious infection:

- Kumar et al. (2006), *Critical Care Medicine* — duration of hypotension before effective
  antimicrobial administration and survival in septic shock.
- Seymour et al. (2017), *NEJM* — time to treatment and mortality in sepsis. **[verify]**

The domain already measures this quantity and already knows it predicts death. That is why
`GOAL.md §6.5` forbids replacing it with a composite score: any composite would trade a
validated outcome for an invented one.

**Consequence for the objective function.** Because rounds-to-effective is a *patient*
outcome and resistance frequency is a *population* outcome, every policy comparison is a
tradeoff, not an optimization. `GOAL.md §12.2` requires both be reported together.

---

## 6. Adherence and informative deviation

### 6.1 Fidelity is a first-class variable

Real stewardship programs do not achieve full adherence. Most published models assume they
do. A policy optimal at fidelity 1.0 and catastrophic at 0.7 is worse in practice than one
merely good at both, and **nobody reports that curve.** `GOAL.md §7` sweeps it by default.

### 6.2 Deviation is not noise

Clinicians deviate systematically: more for severe presentations, at night, for atypical
cases, under time pressure, and for patients with prior treatment failure. Modeling
deviation as random noise is a specification error — it produces the wrong policy ranking,
because it randomizes away exactly the correlation between deviation and patient risk.

`AdherenceModel` therefore requires `deviation_drivers` and a `deviation_target`
(what clinicians switch *to*, which is not uniform). `AT-14` fails any model that deviates
uniformly at random.

### 6.3 Confounding by indication — a separable methods contribution

Observational studies report that guideline non-adherence is associated with worse outcomes.
Some unknown fraction of that association is **confounded by indication**: the deviation
occurred *because* the patient was sicker.

Observational data cannot resolve this without strong assumptions. A simulator can, because
it knows the ground truth. The procedure:

1. Generate synthetic data under a known state-dependent deviation mechanism.
2. Run the standard observational adherence–outcome analysis on it.
3. Compare the estimate to the known truth.

Output: **the magnitude of bias in the conventional analysis**, as a function of how
strongly deviation depends on severity.

This is a methods contribution independent of antimicrobials — the same structure applies to
any guideline-adherence literature. Keep it separable (`GOAL.md §6.7`); it may warrant its
own paper, and it will be read by people who do not care about antibiotics.

Background: Hernán & Robins on confounding by indication and target trial emulation.

---

## 7. The feasibility oracle

Most candidate prescribing policies are clinically inadmissible before any simulation:
contraindicated by allergy, renal function, pregnancy, age, or interaction.

Encoding guidelines and constraints as a rule engine gives a **mechanical admissibility
test** — no judgment, no rubric, no learned scoring. Two uses:

1. **Pruning.** Reject inadmissible policies at zero simulation cost. This is what makes
   searching a large policy space tractable.
2. **Discovery.** Every host state where hard constraints admit *no* drug the policy would
   select is a genuine guideline conflict. Guidelines are written one condition at a time
   and never reconciled across multimorbidity; the conflicts are real and largely
   uncatalogued.

The conflict log is a deliverable in its own right — a list of patient states for which
current guidance provides no admissible action, rankable by population prevalence. Clinical
review of that log is where domain expertise is load-bearing, not decorative.

---

## 8. Structural uncertainty — the four mechanisms

| Structure | Dominant mechanism | Implied intervention |
|---|---|---|
| `mutation_driven` | De novo chromosomal mutation under selection | Reduce total exposure; avoid sub-MIC dosing |
| `plasmid_driven` | Horizontal transfer between lineages | Infection control; decolonization |
| `clonal_expansion` | Transmission of a resistant clone | Isolation, cohorting, hand hygiene |
| `importation_dominated` | Resistance arrives from outside | Admission screening; regional coordination |

**These imply different, sometimes opposed, interventions.** A policy optimized under the
wrong assumption can be actively harmful — reducing prescribing when the problem is
importation wastes effort and delays effective therapy.

The field has not resolved which dominates in a given setting. Standard practice is to pick
one and report point estimates. `stewardsim` runs all four as a structural ensemble and
reports between-structure spread alongside within-structure uncertainty.

References for the ensemble concept: Bojke et al. (2009), *Value in Health*, on structural
uncertainty in decision models **[verify]**; Tebaldi & Knutti (2007), *Phil. Trans. R. Soc.
A*, on multi-model ensembles in climate projection **[verify]** — the discipline that takes
structural uncertainty most seriously.

---

## 9. Minimum regret, not maximum expected value

Given that the mechanism is unknown, expected-value optimization over a prior across
structures is fragile: it depends on structure weights nobody can defend.

**Minimum-regret selection** avoids that. For each candidate policy π and structure s:

```
regret(π, s) = outcome(π*_s, s) − outcome(π, s)      where π*_s is optimal under s
```

Select the π minimizing max_s regret(π, s).

The chosen policy is optimal under no structure and acceptable under all — which is the
correct posture when the structure is genuinely unknown and the downside of being wrong is
asymmetric.

Background: Savage (1951) on minimax regret; the robust optimization literature
(Ben-Tal & Nemirovski) for the general framing.

**Reporting requirement.** Report the regret matrix, not only the selected policy. A
stewardship committee should be able to see what the recommendation costs under each
structure, and substitute its own beliefs if it has them.

---

## 10. Elicitation and provenance

*(Carried from `ARCHIVE/THEORY-v1-scaffold.md §6`, unchanged in method.)*

- **SHELF** (Oakley & O'Hagan) for structured group elicitation.
- **Cooke's Classical Model** (Cooke 1991, *Experts in Uncertainty*) with seed questions and
  performance weighting — converts expert opinion into a scored, auditable input.
- O'Hagan et al. (2006), *Uncertain Judgements* — the standard text.
- **Elicit quantiles, never moments.** People are decent at medians and tails, poor at means
  and variances.
- **Correct for overconfidence.** Elicited 90% intervals contain the truth substantially
  less than 90% of the time. **[verify magnitude]**
- **Freeze the elicited/data boundary before seeing results.** Without it, elicited
  parameters migrate to wherever they are needed. Enforced in code.

### The novel reportable

Report output variance grouped by **evidence class**, producing:

> **X% of the variance in the recommended policy's projected benefit derives from
> parameters with no empirical support.**

For stewardship this is unusually pointed, because fitness costs, HGT rates and
compensation rates — the parameters that most determine whether restriction works — are
precisely the ones with the least data. If that number is high, it is a finding.
`GOAL.md §10` sets 70% as a kill threshold.

---

## 11. Calibration and search machinery

*(Carried from v1, unchanged.)*

**Simulation-based inference** — Cranmer, Brehmer & Louppe (2020), *PNAS*; Papamakarios &
Murray (2016); Greenberg et al. (2019); `sbi` (Tejero-Cantero et al. 2020, *JOSS*).
Simulation-based calibration (Talts et al. 2018 **[verify]**) is mandatory; a posterior
failing SBC is rejected, not caveated.

**Ensemble efficiency** — Sobol-sequence QMC for the outer loop; common random numbers for
paired comparisons (Law & Kelton); the trained density estimator doubles as an emulator so
the ensemble sweep runs against the surrogate with extremes verified against the full
simulator.

**Sensitivity** — Saltelli et al. (2008), *Global Sensitivity Analysis: The Primer*;
`SALib`. Sobol indices, not one-at-a-time.

**Value of information** — Strong, Oakley & Brennan (2014), *Medical Decision Making*, for
efficient EVPPI from existing PSA samples **[verify]**. Output: the single highest-value
measurement anyone could fund. Given §10, expect it to be a fitness cost or an HGT rate —
which is itself a useful message to the funders of microbiology research.

---

## 12. Retrodiction targets

`AT-12` requires reproducing a documented intervention with independently-set parameters.
Candidates, in rough order of data quality:

1. **Fluoroquinolone restriction in England and the *C. difficile* decline.** Dingle et al.
   (2017), *Lancet Infectious Diseases*, on the effect of control interventions **[verify]** —
   a large, well-documented, time-resolved natural experiment with a clear intervention date
   and a measured resistance/incidence response. The strongest single candidate.
2. **MRSA bloodstream infection decline in England** following coordinated intervention.
   **[verify]** Large signal, but multiple simultaneous interventions complicate attribution.
3. **Single-institution formulary restrictions** with published before/after antibiograms.
   Numerous, smaller, noisier — useful as a replication set rather than a primary target.

Data sources: local antibiogram and microbiology time series; MIMIC-IV for linked
encounter-level exposure and culture data during development; national surveillance
(NHSN, EARS-Net, ESPAUR) for context.

**A retrodiction that succeeds only after parameter adjustment is not a retrodiction.**
Fix parameters, freeze them, then run.

---

## 13. Roadmap — scope discipline

`GOAL.md` specifies **v1 only**. The rest is recorded here so it is not lost and not built
prematurely.

| Version | Contains | Question answered |
|---|---|---|
| **v1** *(active)* | Single institution; host + pathogen populations; state-dependent adherence; feasibility oracle; structural ensemble; **exogenous importation** | Minimum-regret empiric policy under structural uncertainty and imperfect adherence |
| **v1.5** | Same simulator, new drug object with fully elicited parameters | Optimal release/restriction strategy for a novel agent; useful-lifetime curves |
| **v2** | Importation scalar → network coupling | Return on unilateral vs coordinated stewardship |

### 13.1 v1.5 — novel agent release strategy

A new antibiotic arrives. How should its use be controlled from day one to maximize useful
lifetime? Current practice is essentially "restrict it and hope."

Needs **no new machinery** — a new drug object run through the same simulator. Output:
expected useful lifetime as a function of release policy, with intervals.

It lands in a live policy debate: pharmaceutical revenue requires volume, stewardship
requires restraint, and subscription-style pull incentives (the NHS antimicrobial
subscription pilot; PASTEUR-type proposals in the US) exist because nobody has quantified
the tradeoff.

**Why it fits the provenance machinery uniquely well:** for a drug that does not exist,
*every* parameter is `ELICITED` or `ASSUMED`. The provenance-weighted variance figure stops
being a methodological nicety and becomes the headline finding. Most groups would bury it;
reporting it is what makes the analysis usable by a regulator.

### 13.2 v2 — network coupling

Resistance ignores institutional boundaries: patients transfer, share post-acute facilities,
share catchments and staff. There is a real commons problem — unilateral stewardship
investment benefits neighbors, and their laxity costs you.

**This will eat the project if admitted early.** It requires transfer data, multi-institution
calibration, and it multiplies the parameter space. It is also not unclaimed — there is
published work on hospital referral networks and pathogen spread, including from CDC groups
on CRE. **[verify]**

**The architectural protection is `Importation` (`GOAL.md §4.7`).** Built as a first-class
parameter object with its own provenance and uncertainty, v2 replaces the scalar rate with a
network coupling — a swap, not a rewrite. `AT-6` guards that seam.

### 13.3 Questions that are runs, not versions

These require only changing what is held fixed, and cost nothing extra:

- **Duration** — short versus long course; live controversy with trial evidence to calibrate.
- **De-escalation timing** — when to narrow after culture return.
- **Diagnostic stewardship** — rapid diagnostics shorten time-to-appropriate-therapy, which
  is the fitness variable directly. Cleanest intervention to model; the mechanism is
  unambiguous.
- **Combination versus sequential therapy.**

**The scope test:** if it requires new data or new machinery it is a version; if it only
requires changing what is held fixed, it is a run.

---

## 14. Framing

The v1 eugenics constraint is retired. Two replace it, specified normatively in
`GOAL.md §12`; the reasoning is here.

### 14.1 Prescriber blame

The natural framing of an adherence model is "deviation causes resistance and worse
outcomes." That reads as clinicians being the problem — and §6.3 shows the empirical basis
is weaker than it appears, because deviation is confounded with severity.

Deviation is a **system property with measurable drivers**: staffing, time of day, diagnostic
uncertainty, case atypicality. Those are modifiable at the system level. Framing it as
individual failure both misattributes cause and points at an intervention that does not work.

### 14.2 Stewardship as rationing

Restriction reads politically as withholding care, and there is a real tradeoff underneath:
narrower empiric therapy can mean more patients receiving initially ineffective treatment,
concentrated in exactly the patients least able to tolerate delay.

Reporting resistance alone hides this. Reporting both, by subgroup, in the same figure, makes
the tradeoff a decision rather than an assumption. A policy with acceptable aggregate
performance and concentrated subgroup harm is a finding.

---

## 15. Positioning

**Not novel — implement correctly, claim nothing:**
- Resistance evolves under selection pressure (Bonhoeffer, Lipsitch, Levin, Austin & Anderson)
- Cycling does not outperform mixing (Bergstrom et al.)
- Fitness costs and compensatory evolution (Andersson & Hughes)
- Compartmental hospital transmission models
- Neural posterior estimation; Sobol sensitivity; EVPPI

**Novel — the contribution:**
1. **Individual-level host state with endogenous policy feedback** — exposure history
   retained, empiric choice made from patient risk factors, population resistance altering
   the next choice.
2. **Minimum-regret policy selection across a structural ensemble** of competing resistance
   mechanisms, rather than optimization under one assumed mechanism.
3. **State-dependent adherence as a first-class variable**, with the adherence-robustness
   curve as a reported output.
4. **Quantified confounding-by-indication bias** in the adherence–outcome literature —
   separable, and generalizable beyond antimicrobials.
5. **Provenance-weighted variance decomposition** applied to a stewardship recommendation.
6. **Mechanical guideline-conflict discovery** as a byproduct of the feasibility oracle.

**Suggested outputs:**
- *Paper 1* — the coupled model, verification, retrodiction, and the minimum-regret result.
- *Paper 2* — confounding by indication in guideline-adherence studies. Methods venue;
  broader audience than paper 1.
- *Paper 3* — novel agent release strategy (v1.5). Policy venue.

---

## 16. Glossary

| Term | Meaning |
|---|---|
| **Determinant** | A resistance-conferring genetic element |
| **Fitness cost** | Reduction in growth/competitiveness conferred by a determinant absent drug |
| **Compensation** | Secondary mutation restoring fitness while retaining resistance |
| **HGT** | Horizontal gene transfer |
| **Cross-resistance** | One determinant conferring resistance to multiple agents |
| **Rounds to effective** | Lines of therapy until a verified-effective agent is reached |
| **Fidelity** | Probability a policy is executed as specified |
| **Informative deviation** | Deviation correlated with patient state — the source of confounding |
| **Feasibility oracle** | Mechanical test of whether a drug is admissible for a host state |
| **Structural ensemble** | Set of competing model forms run in parallel |
| **Regret** | Outcome loss from choosing π when structure s obtains |
| **Importation** | Colonized arrivals from outside the modeled institution |
| **Provenance class** | Evidence category attached to every parameter |
| **EVPPI** | Expected value of partial perfect information |
| **SBC** | Simulation-based calibration |
