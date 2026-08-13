# THEORY.md — reference for `scaffold`

Companion to `GOAL.md`. Read this first. It contains the formalism, the prior work that
must not be reinvented, the arithmetic that constrains what may be claimed, the
methodological standards, and the use cases.

> **Citation note.** References below are given so the implementer can locate the correct
> literature, not as a verified bibliography. Every citation must be checked against the
> primary source before it appears in a manuscript. Items marked **[verify]** are ones
> where the exact reference or figure should be confirmed with particular care.

---

## 1. The core reframing

The intuition that motivates this project is usually stated as: *medical treatment lets
people survive and reproduce who otherwise would not, so harmful alleles accumulate and
future populations become more vulnerable.*

The first half of that is true. The second half is where the intuition fails, and it fails
in an instructive direction.

**Two clocks run at very different speeds.**

| Quantity | Direction under successful treatment | Timescale to matter |
|---|---|---|
| Allele frequency at a treated recessive locus | Approximately flat | Centuries; magnitude small |
| Number of living people whose viability depends on the treatment continuing | Rises steeply | Decades |

The separation is roughly three orders of magnitude. The perceived vulnerability is real,
but it is **not genetic**. It is a dependency and continuity-of-supply problem. The genome
is not the fragile object; the scaffold is.

`scaffold` therefore models the second clock, using the first only as a correctly
implemented, well-tested background process.

---

## 2. Formalism: the Viability Dependency Graph

**Definition.** A *viability dependency* is an external, engineered input required for an
individual's continued survival, whose withdrawal produces excess mortality on a
characterizable timescale.

A **Viability Dependency Graph (VDG)** is a bipartite-plus-DAG structure:

```
individuals ──requires──▶ dependencies ──supplied_by──▶ infrastructure nodes
                                                              │
                                                          upstream
                                                              ▼
                                                    shared chokepoints
```

Three quantities of interest:

1. **Scaffold-dependent fraction** _D(t)_ — proportion of the living population with at
   least one unmet-tolerance-limited dependency.
2. **Failure consequence function** _C(n, t)_ — excess deaths if node _n_ fails at time _t_.
   Its growth in _t_ is the central result.
3. **Minimum cut sets** — smallest simultaneous failure sets producing consequence above
   threshold, with probabilities.

**Why this is not already done.** Population biology models populations. Reliability
engineering models systems. Health services research models care delivery. Each has mature
tools. The *coupling* — where individual survival is conditioned on a stochastic
infrastructure process with correlated failures, and the dependent population is itself
growing because the infrastructure works — has no standard formalism. That gap is the
contribution.

The nearest prior art is critical-infrastructure interdependency modeling (Rinaldi,
Peerenboom & Kelly, *IEEE Control Systems* 2001, on identifying and analyzing
interdependencies), which models the systems but not the demography of the dependent
population.

---

## 3. Population genetics: what is settled, and the arithmetic

### 3.1 Prior work — do not reinvent

- Haldane (1937), *American Naturalist* — the cost of selection; load is a function of
  mutation rate, not selection intensity.
- Muller (1950), "Our load of mutations," *American Journal of Human Genetics* — the
  original statement of the relaxed-selection worry. Note the eugenic context (§12).
- Crow & Kimura (1970), *An Introduction to Population Genetics Theory* — the standard
  reference for everything in `genetics.py`.
- Kimura, Maruyama & Crow (1963) — mutation load in small populations.
- Lynch (2010), *PNAS*, "Rate, molecular spectrum, and consequences of human mutation" —
  the closest modern statement of the concern; argues measurable fitness decline per
  generation under relaxed selection. **This is the paper the project must be positioned
  against, not the paper it can restate.** **[verify magnitude]**
- Kong et al. (2012), *Nature* — paternal age and de novo mutation rate; roughly one to two
  additional mutations per additional year of paternal age. Feeds `demography.py`.
- Karczewski et al. (2020), *Nature* — gnomAD, for allele frequency inputs.

### 3.2 The viability/fertility split

Fitness must decompose. Therapies overwhelmingly restore **viability** (survival to
reproductive age) while leaving **fertility** unchanged or only partly restored. A single
scalar fitness parameter conflates these and produces wrong answers.

The canonical illustration: CFTR modulators restore health substantially but do not restore
congenital bilateral absence of the vas deferens in affected males, which is present from
birth and not pharmacologically reversible. Fitness is therefore *not* fully restored, and
the allele continues to decline slowly even under complete clinical success.

### 3.3 The CF arithmetic (worked, because it determines what may be claimed)

Order-of-magnitude figures for a European-ancestry population:

- Carrier frequency ≈ 1 in 25 ⟹ allele frequency _q_ ≈ 0.02
- Affected births ≈ 1 in 2,500

The decisive observation: at _q_ = 0.02, the proportion of alleles residing in affected
homozygotes is _q_ ≈ 2%. **Approximately 98% of copies sit in unaffected heterozygotes,
invisible to selection.** Selection was only ever acting on a small minority of copies.

Consequently, removing selection entirely does not inflate the allele — it **freezes** it.
Under historical strong selection the per-generation decline was on the order of 4 × 10⁻⁴;
mutation input is on the order of 10⁻⁶ and cannot drive an increase. Ten generations
(~300 years) of complete relaxation yields affected births near today's rate rather than
the somewhat lower rate the counterfactual would have produced.

**This is why recessive conditions are common enough to notice in the first place:** they
hide too well to have been purged.

`AT-7` in `GOAL.md` encodes this. A model showing the allele *rising* has a sign error.

### 3.4 The counter-force that flips the sign

Carrier screening plus embryo selection removes alleles from the reproductive pool faster
than relaxed selection preserves them, at plausible uptake rates. Reproductive technology
is now a more powerful selective agent on such loci than natural selection was.

**A model omitting a screening term gets the long-run direction wrong.** This is required,
not optional, in `genetics.py`.

### 3.5 Where the concern is legitimate

Not one locus — thousands simultaneously. Each individual carries on the order of one to
two new deleterious mutations per generation. Broad relaxation across many conditions at
once produces a slow decline in mean fitness. This is the real form of the worry, it is
Lynch's argument, and it operates on a centuries timescale — against which medical
capability has been improving for two hundred years. Model it in the multi-locus mode;
do not claim it as a finding.

---

## 4. Demography

- Leslie (1945), *Biometrika* — the projection matrix.
- Caswell (2001), *Matrix Population Models*, 2nd ed. — the canonical reference; use its
  notation throughout `demography.py`.

The reproductive-span question decomposes into three effects that partly cancel:

1. **Longer generation time slows all genetic change measured in calendar years.** Shifting
   mean reproductive age from ~28 to ~45 slows per-year genetic processes by roughly 40%.
   This *dampens* the relaxed-selection concern.
2. **Paternal age increases de novo mutation rate.** This is the one channel where
   extending reproductive span genuinely raises genetic load — and unlike the single-locus
   story it acts genome-wide.
3. **Demographic effects dominate and act immediately.** Growth rate and age structure
   change within one generation; allele frequencies take fifty.

Fitness in the age-structured model is **lifetime reproductive output**, not a scalar
attached to a genotype.

---

## 5. Reliability and correlated failure

- Standard reliability theory: hazard functions, MTBF, repair processes, availability.
- Cut-set and fault-tree analysis for minimum cut sets.
- Rinaldi et al. (2001) for interdependency taxonomy.

**The dominant modeling error in this domain is assuming independent failures.** Real
scaffolds share upstream nodes: a single sterile-injectable manufacturing plant, one
regional distributor, one power grid, one port. Independence assumptions make catastrophic
tail events appear impossibly rare — which is precisely the regime the project exists to
characterize.

No dataset will supply the correlation structure, because the correlated events are too
rare to have been observed often. This is exactly the void formal expert elicitation exists
to fill (§6), and it is why the belief-network layer is load-bearing rather than
decorative.

---

## 6. Expert elicitation and provenance

### 6.1 Protocols

- O'Hagan et al. (2006), *Uncertain Judgements: Eliciting Experts' Probabilities* — the
  standard text.
- **SHELF** (Sheffield Elicitation Framework), Oakley & O'Hagan — structured group
  elicitation with behavioral aggregation.
- **Cooke's Classical Model** — Cooke (1991), *Experts in Uncertainty*, Oxford. Experts
  additionally answer *seed questions* with known answers; their measured calibration
  produces performance weights used in aggregation.

Cooke's model matters disproportionately here: it converts expert opinion from an
unfalsifiable input into a **scored, auditable** one. It is the strongest available answer
to the reviewer objection that the model rests on opinion.

### 6.2 Elicit quantiles, never moments

People are reasonably good at medians and tail quantiles and poor at means and variances.
Elicit the 5th, 50th and 95th percentiles and fit; never ask for a distribution family or a
standard deviation. `DistributionSpec` in `GOAL.md §4.3` enforces this.

### 6.3 Overconfidence correction

Elicited 90% intervals empirically contain the truth substantially less than 90% of the
time. Uncorrected, this propagates directly into falsely tight credible intervals on
outputs. Apply and expose a widening factor. **[verify magnitude against the calibration
literature before publication]**

### 6.4 The frozen boundary

The map of which parameters are elicited and which are data-derived is fixed **before any
results are examined**. Elicitation is permitted only where no data source exists.

Rationale: without a frozen boundary, elicited parameters migrate to wherever they are
needed to make results come out. Reviewers look for exactly this. `belief.py` enforces the
boundary programmatically.

### 6.5 Provenance-weighted variance decomposition — the novel reportable

Standard sensitivity analysis reports variance by *parameter*. Report it additionally by
*evidence class*, producing:

> **X% of the variance in the projected outcome derives from parameters with no empirical
> support.**

This is unusual, uncomfortable, and highly defensible. It converts the model's epistemic
honesty from a disclaimer paragraph into a measured quantity, and gives reviewers a way to
accept the paper without having to trust the elicitation panel.

If that figure is high, it is a finding. `GOAL.md §11` sets 70% as a kill threshold.

### 6.6 Integration with calibration

Chain, do not compete:

```
elicited distributions → priors → registry / disruption data → likelihood
                                → posterior → simulation
```

Where data exists it updates the expert prior. Where it does not, the prior stands, labeled.
The expert layer then degrades gracefully as real data arrives rather than needing removal.

---

## 7. Ensemble design

Three sources of uncertainty, three loops:

| Loop | Uncertainty | Method | Prevalence in the literature |
|---|---|---|---|
| Inner | Aleatory — stochastic events | seeded pseudo-RNG | universal |
| Outer | Epistemic — parameter values | Sobol-sequence QMC | standard practice |
| Ensemble | **Structural — model form** | enumerate alternative DAGs | **rare** |

References:
- Briggs et al. (2012), ISPOR–SMDM Modeling Good Research Practices Task Force-6,
  *Medical Decision Making* — parameter uncertainty and probabilistic sensitivity analysis.
- Bojke et al. (2009), *Value in Health* — characterizing structural uncertainty in
  decision-analytic models. **[verify]**
- Tebaldi & Knutti (2007), *Phil. Trans. R. Soc. A* — multi-model ensembles in climate
  projection; the discipline that takes structural uncertainty most seriously. **[verify]**
- Saltelli et al. (2008), *Global Sensitivity Analysis: The Primer* — Sobol indices.
- Law & Kelton, *Simulation Modeling and Analysis* — common random numbers and variance
  reduction.
- Niederreiter (1992) / `scipy.stats.qmc` — quasi-Monte Carlo sequences.

**Structural uncertainty is usually larger than parameter uncertainty and is usually not
reported.** Separating and reporting both is a methodological contribution on its own.

Efficiency notes for the M4: QMC buys roughly an order of magnitude fewer outer draws for
equivalent coverage; common random numbers commonly give 10–50× variance reduction on
paired scenario comparisons; the SBI density estimator doubles as an emulator so the full
ensemble sweep runs against the surrogate with only extremes verified against the full
simulator.

---

## 8. Simulation-based inference

- Cranmer, Brehmer & Louppe (2020), *PNAS*, "The frontier of simulation-based inference" —
  the survey to cite.
- Papamakarios & Murray (2016); Greenberg et al. (2019) — neural posterior estimation.
- Tejero-Cantero et al. (2020), *JOSS* — the `sbi` package.
- Talts et al. (2018) — simulation-based calibration; the diagnostic that determines
  whether a posterior is usable. **[verify]**

Individual-based models are too slow to fit by brute-force parameter sweeps. NPE inverts
the simulator: run it a few hundred thousand times, train a density estimator to recover
parameters from summary statistics, obtain a full posterior given observed data.

SBC is not optional. A posterior failing SBC is rejected automatically (`AT-10`), not
reported with a caveat.

---

## 9. Value of information

- Strong, Oakley & Brennan (2014), *Medical Decision Making* — efficient EVPPI computation
  from existing PSA samples. **[verify]**
- Claxton & Sculpher — the health-economic VOI tradition.

Once provenance-tagged parameters and a working ensemble exist, EVPPI is nearly free. It
answers: *which single unmeasured quantity, if measured, would most reduce decision
uncertainty?*

This converts the model from a projection into a **research-prioritization instrument** —
"the highest-value measurement anyone could fund in this space is X, and here is the
calculation." For a policy audience this is often the most useful output the project
produces.

---

## 10. Reporting standards

Simulation papers are rejected for description quality more often than for method quality.
Using the established standards signals competence immediately.

- **ODD protocol** — Grimm et al. (2006), *Ecological Modelling*; updated 2010 and 2020.
  Overview, Design concepts, Details. The standard for individual-based model description.
- **TRACE** — Grimm et al. (2014), *Ecological Modelling*. Documentation of model
  evaluation ("evaludation").
- **ISPOR–SMDM Modeling Good Research Practices** — the seven-report series, *Medical
  Decision Making* / *Value in Health*, 2012.
- **CHEERS** if any health-economic outcome is reported.

Additionally: preregistration with explicit predictions and kill criteria; versioned code;
fixed seeds; containerized runtime; open data derivation scripts.

---

## 11. Use cases

The VDG schema must express all of these without modification.

### 11.1 Dialysis — the reference case, build first

Roughly half a million people in the United States are alive contingent on attending a
fixed facility three times weekly. It is the purest scaffold dependency available: absolute,
short-tolerance, facility-bound, and geographically concentrated.

Critically, **documented natural experiments in scaffold failure exist**: Hurricane Katrina,
Superstorm Sandy, and Hurricane Maria each produced missed treatments and measurable excess
morbidity and mortality in dialysis populations. See for example Anderson et al. on missed
sessions and hospitalization following Katrina, *Kidney International* 2009 **[verify]**,
and the Puerto Rico / Maria literature **[verify]**.

This is the retrodiction target for `AT-12`. Very few simulation projects have an observed,
involuntary, outcome-measured instance of the exact failure they model. This one does, and
it is the single strongest methodological asset available.

Data: USRDS Annual Data Report; CMS ESRD facility data.

### 11.2 Insulin

Supply-chain and cost-driven interruption; a large dependent population; documented
rationing behavior. Tolerance is short. Failure modes are economic as well as physical,
which exercises the `substitutable_by` and partial-capacity paths in the schema.

Data: FDA Drug Shortages Database; ASHP shortage database.

### 11.3 Transplant immunosuppression

Drug-absolute, device-free dependency with a distinctive consequence curve: graft loss
rather than immediate death, so `ConsequenceModel` must support delayed and staged
consequences.

Data: SRTR; OPTN.

### 11.4 CF modulators

The genetics-coupled case, and the setting in which the naive framing is tested and
rejected (§3). Small dependent population, very high per-person dependency, single-source
manufacturing.

Data: CF Foundation Patient Registry annual reports; UK CF Registry.

### 11.5 ART for HIV

Global scale, well-documented pandemic-era interruptions, and an unusually well-quantified
relationship between interruption duration and outcome. The best case for validating the
`tolerance` / `hazard_curve` shape.

### 11.6 Cold-chain biologics

Utility-coupled failure: the dependency is on a temperature-controlled chain that itself
depends on power. Exercises multi-hop `upstream` correlation.

### 11.7 Home oxygen and powered devices

Direct grid dependency at the individual level. Correlated failure is geographic and
weather-driven — the clearest case of individually-rare failures co-occurring.

### 11.8 Non-health generalization

The formalism is not intrinsically medical. Any population whose viability has been
migrated onto engineered systems fits: agricultural monocultures dependent on specific
inputs, communities dependent on single-source water treatment, systems dependent on
positioning and timing signals. If the schema requires modification to express one of
these, the schema is wrong.

### 11.9 A note on PKU

The best-validated *genetics* anchor, distinct from the scaffold cases: newborn screening
since the 1960s gives sixty years of treatment history, and maternal PKU syndrome — where
treated affected mothers carry risk to unaffected offspring — is a documented
intergenerational second-order effect of exactly the class this project models. See Lenke &
Levy, *NEJM* 1980 **[verify]**.

---

## 12. Framing constraint

The eugenic reading of this subject matter is not a hypothetical risk. Muller, who
formalized mutational load, was an active eugenicist, and "relaxed selection is degrading
the population" is that tradition's central claim. Work framed that way will be read as
belonging to it, regardless of intent, and readers will not be wrong to do so.

The ethical constraint and the correct scientific framing coincide. Observe what each
framing makes you measure:

| Framing | Measured variable | Behavior | Result |
|---|---|---|---|
| Genetic deterioration | Allele frequencies | Barely moves | A paper about a non-effect |
| Dependency and continuity of care | People at risk of interruption | Moves fast | Actionable, and true |

The eugenic framing is not merely offensive; it points at the wrong variable and produces a
null result. Stating this explicitly in the discussion strengthens the work.

Prohibited throughout code and prose: "genetic deterioration," "degradation of the gene
pool," "genetic quality," "dysgenic," "burden" applied to people, "defective." Outputs are
counts of people at risk of care interruption, never rankings of genetic worth.

---

## 13. Positioning: what is and is not novel

**Not novel — implement correctly, claim nothing:**
- Relaxed selection changes allele frequencies (Haldane, Muller, Crow, Kimura, Lynch)
- Age-structured population projection (Leslie, Caswell)
- Reliability modeling of infrastructure (standard engineering)
- Probabilistic sensitivity analysis in decision models (ISPOR–SMDM)
- Neural posterior estimation (Cranmer et al.)

**Novel — this is the contribution:**
1. **The VDG formalism** — a schema coupling individual viability to a stochastic
   infrastructure process with correlated failure, and the demography of the dependent
   population feeding back into it.
2. **Provenance-weighted variance decomposition** — reporting output variance grouped by
   evidence class, with "% from parameters with no empirical support" as a headline figure.
3. **Structural ensembles in this domain** — routine in climate, near-absent in health
   modeling.
4. **Adaptive rare-event search over dependency-graph perturbations** with an unfakeable
   simulator-computed objective, producing ranked minimum cut sets as policy output.

**Suggested outputs:**
- *Paper 1 (methods)* — VDG formalism plus open-source simulator, validated against
  analytic limits and PKU/CF retrodiction. Computational biology or interface venue.
- *Paper 2 (applied)* — scaffold-dependent population fraction across conditions,
  calibrated to registry and shortage data, retrodicting disruption mortality. Health policy
  venue. This is the one that gets read.
- *Paper 3 (AI methods)* — SBI calibration plus adaptive rare-event search for coupled
  population–infrastructure models. Venue-agnostic; generalizes well beyond health.

Build order 1 → 3 → 2: Paper 2's numbers are only trustworthy once the calibration and
search machinery are validated.

---

## 14. Glossary

| Term | Meaning |
|---|---|
| **Scaffold** | An engineered system on which individual viability depends |
| **VDG** | Viability Dependency Graph |
| **Scaffold-dependent fraction** _D(t)_ | Share of living population with ≥1 viability dependency |
| **Tolerance** | Time an individual survives an unmet dependency before excess hazard begins |
| **Consequence function** _C(n,t)_ | Excess deaths if node _n_ fails at time _t_ |
| **Minimum cut set** | Smallest simultaneous failure set exceeding a consequence threshold |
| **Provenance class** | Evidence category attached to every parameter |
| **Viability fitness** | Survival to reproductive age |
| **Fertility fitness** | Offspring production given survival — restored far less often by treatment |
| **Structural uncertainty** | Uncertainty in model *form*, distinct from parameter values |
| **EVPPI** | Expected value of partial perfect information |
| **SBC** | Simulation-based calibration |
