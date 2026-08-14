"""What-if scenario runner. Not an AT-12 event."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from stewardsim.antibiogram import resistance_frequency
from stewardsim.feasibility import ConstraintSet
from stewardsim.host import Host
from stewardsim.params import Parameter, Provenance
from stewardsim.pathogen import Determinant
from stewardsim.policy import AdherenceModel, DeviationTarget, Policy, PolicyRule, point_value
from stewardsim.restriction import ForcedRestriction, RestrictionInterval
from stewardsim.simulate import SimulateResult, simulate

DEFAULT_S_MAX = 0.02
DEFAULT_N = 200
DEFAULT_HORIZON = 365
DEFAULT_SEED = 0

_BUG_ALIASES = {
    "ecoli": "Escherichia coli",
    "e.coli": "Escherichia coli",
    "e. coli": "Escherichia coli",
    "klebsiella": "Klebsiella pneumoniae ssp",
    "kp": "Klebsiella pneumoniae ssp",
    "pa": "Pseudomonas aeruginosa",
    "pseudo": "Pseudomonas aeruginosa",
    "pseudomonas": "Pseudomonas aeruginosa",
}
_DRUG_ALIASES = {
    "cipro": "ciprofloxacin",
    "levo": "levofloxacin",
    "ceftriaxone": "ceftriaxone",
    "cro": "ceftriaxone",
    "pip-tazo": "pip_tazo",
    "piptazo": "pip_tazo",
    "tzp": "pip_tazo",
}


def resolve_bug(raw: str) -> str:
    key = raw.strip().lower()
    return _BUG_ALIASES.get(key, raw.strip())


def resolve_drug(raw: str) -> str:
    key = raw.strip().lower().replace(" ", "_")
    return _DRUG_ALIASES.get(key, key)


def campus_for_year(year: int) -> str:
    if year == 2017:
        return "TUH"
    if year in {2024, 2025}:
        return "TUH-Main"
    raise ValueError(f"year must be 2017, 2024, or 2025; got {year}")


def backup_drug(primary: str) -> str:
    if primary == "levofloxacin":
        return "ceftriaxone"
    return "levofloxacin"


def _point(name: str, value: float, *, provenance: Provenance, source: str) -> Parameter:
    return Parameter(
        name=name,
        provenance=provenance,
        source=source,
        distribution={"family": "point", "fitted_params": {"value": value}},
    )


def parse_ban(raw: str) -> int | None:
    text = raw.strip().lower()
    if text == "none":
        return None
    day = int(text)
    if day < 0:
        raise ValueError("ban day must be >= 0")
    return day


@dataclass(frozen=True)
class ScenarioCompare:
    year: int
    campus_id: str
    organism: str
    drug: str
    p0: float
    s_max: float
    ban_day: int | None
    horizon: int
    banned: SimulateResult
    control: SimulateResult

    @property
    def start_resistant_pct(self) -> float:
        return 100.0 * self.p0

    @property
    def end_banned_pct(self) -> float:
        return 100.0 * self.banned.frequencies[-1]

    @property
    def end_control_pct(self) -> float:
        return 100.0 * self.control.frequencies[-1]

    @property
    def delta_points(self) -> float:
        return self.end_banned_pct - self.end_control_pct

    def saturated_before_ban(self) -> bool:
        if self.ban_day is None or self.ban_day <= 0:
            return False
        idx = min(self.ban_day, len(self.control.frequencies)) - 1
        return self.control.frequencies[idx] > 0.99

    def first_line_miss_pct(self, result: SimulateResult) -> float:
        """Share of primary-drug treatment-days when p > 0.5 at dosing.

        Scoring uses start-of-day resistance (p0, then yesterday's end p),
        matching ``simulate``'s rounds rule.
        """
        doses = result.dose_days.get(self.drug, [])
        if not result.frequencies or not doses:
            return 0.0
        missed = 0.0
        given = 0.0
        for t, dose in enumerate(doses):
            if dose <= 0.0:
                continue
            p = self.p0 if t == 0 else result.frequencies[t - 1]
            given += dose
            if p > 0.5:
                missed += dose
        if given == 0.0:
            return 0.0
        return 100.0 * missed / given


def run_scenario(
    *,
    year: int,
    bug: str,
    drug: str,
    ban: str,
    s_max: float = DEFAULT_S_MAX,
    n: int = DEFAULT_N,
    horizon: int = DEFAULT_HORIZON,
    seed: int = DEFAULT_SEED,
) -> ScenarioCompare:
    organism = resolve_bug(bug)
    primary = resolve_drug(drug)
    campus = campus_for_year(year)
    organisms = [organism]
    if organism.endswith(" ssp"):
        organisms.append(organism[: -len(" ssp")])
    last_error: Exception | None = None
    p0 = None
    for name in organisms:
        try:
            p0 = resistance_frequency(
                year=year, campus_id=campus, organism=name, drug=primary
            )
            organism = name
            break
        except ValueError as exc:
            last_error = exc
    if p0 is None:
        raise ValueError(
            f"no printed cell for {year} {campus} {organism} vs {primary}"
        ) from last_error
    ban_day = parse_ban(ban)
    backup = backup_drug(primary)
    policy = Policy(
        id="prefer_primary",
        rules=[PolicyRule(preferred=[primary, backup])],
        duration=_point("policy.duration", 1.0, provenance=Provenance.ASSUMED, source="scenario"),
    )
    adherence = AdherenceModel(
        baseline_fidelity=_point(
            "adherence.baseline_fidelity",
            1.0,
            provenance=Provenance.ASSUMED,
            source="scenario",
        ),
        deviation_drivers={},
        deviation_target=DeviationTarget(drugs=[backup]),
    )
    determinant = Determinant(
        id=f"res_{primary}",
        confers_resistance_to=[primary],
        fitness_cost=_point(
            "determinant.fitness_cost",
            0.0,
            provenance=Provenance.ASSUMED,
            source="scenario",
        ),
    )
    constraints = ConstraintSet(hard=[], soft=[], sources=["scenario"])
    hosts = [
        Host(id=i, exposure_history=[])
        for i in range(n)
    ]
    empty = ForcedRestriction(intervals=[])
    if ban_day is None:
        tape = empty
    else:
        tape = ForcedRestriction(
            intervals=[RestrictionInterval(drug_id=primary, t0=ban_day, t1=horizon + 1)]
        )
    banned = simulate(
        hosts,
        policy=policy,
        constraints=constraints,
        adherence=adherence,
        tape=tape,
        determinant=determinant,
        p0=p0,
        horizon=horizon,
        rng=np.random.default_rng(seed),
        s_max=s_max,
    )
    control = simulate(
        hosts,
        policy=policy,
        constraints=constraints,
        adherence=adherence,
        tape=empty,
        determinant=determinant,
        p0=p0,
        horizon=horizon,
        rng=np.random.default_rng(seed),
        s_max=s_max,
    )
    return ScenarioCompare(
        year=year,
        campus_id=campus,
        organism=organism,
        drug=primary,
        p0=p0,
        s_max=s_max,
        ban_day=ban_day,
        horizon=horizon,
        banned=banned,
        control=control,
    )


def format_compare(cmp: ScenarioCompare) -> str:
    ban_label = "none" if cmp.ban_day is None else f"day {cmp.ban_day} to end"
    miss_ban = cmp.first_line_miss_pct(cmp.banned)
    miss_ctl = cmp.first_line_miss_pct(cmp.control)
    lines = [
        "STEWARDSHIP CARD (conditional what-if, not a prediction)",
        f"start: {cmp.year} {cmp.campus_id} {cmp.organism} vs {cmp.drug}",
        f"starting resistant: {cmp.start_resistant_pct:.1f}%",
        f"s_max: {cmp.s_max} (assumed speed; not estimated from Temple)",
        f"restriction: {ban_label}",
        "",
        "Resistance at end of run",
        f"  WITH restriction: {cmp.end_banned_pct:.1f}%",
        f"  NO restriction:   {cmp.end_control_pct:.1f}%",
        f"  difference:       {cmp.delta_points:+.1f} points",
        "",
        "Empiric first-line (same page as resistance — required)",
        f"  mean rounds to effective WITH restriction: {cmp.banned.rounds_to_effective:.2f}",
        f"  mean rounds to effective NO restriction:   {cmp.control.rounds_to_effective:.2f}",
        f"  first-line miss share WITH restriction: {miss_ban:.1f}%",
        f"  first-line miss share NO restriction:   {miss_ctl:.1f}%",
    ]
    if cmp.ban_day is not None:
        after = sum(cmp.banned.dose_days.get(cmp.drug, [])[cmp.ban_day :])
        lines.append(f"  {cmp.drug} dose-days after restriction: {after:.0f}")
    if cmp.saturated_before_ban():
        lines.append(
            "WARNING: no-restriction resistance already >99% before the ban day; "
            "the comparison may look flat. Lower --s-max or ban earlier."
        )
    lines.append("")
    lines.append(
        "Not a history-match. AT-12 back-test is optional and does not "
        "block this run."
    )
    return "\n".join(lines) + "\n"


def write_compare(cmp: ScenarioCompare, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "compare.txt"
    path.write_text(format_compare(cmp))
    return path
