"""What-if scenario CLI. Not AT-12."""

from __future__ import annotations

import pytest

from stewardsim.cli import main
from stewardsim.scenario import (
    DEFAULT_S_MAX,
    backup_drug,
    campus_for_year,
    format_compare,
    parse_ban,
    resolve_bug,
    resolve_drug,
    run_scenario,
)


def test_aliases_and_campus() -> None:
    assert resolve_bug("ecoli") == "Escherichia coli"
    assert resolve_drug("cipro") == "ciprofloxacin"
    assert campus_for_year(2017) == "TUH"
    assert campus_for_year(2025) == "TUH-Main"
    assert backup_drug("ciprofloxacin") == "levofloxacin"
    assert parse_ban("none") is None
    assert parse_ban("100") == 100


def test_2025_ecoli_cipro_start_matches_transcript() -> None:
    cmp = run_scenario(
        year=2025,
        bug="ecoli",
        drug="cipro",
        ban="none",
        horizon=5,
        n=20,
    )
    assert cmp.p0 == pytest.approx(0.44)
    assert cmp.campus_id == "TUH-Main"
    assert cmp.drug == "ciprofloxacin"


def test_ban_stops_primary_and_moves_end_frequency() -> None:
    cmp = run_scenario(
        year=2025,
        bug="ecoli",
        drug="cipro",
        ban="20",
        s_max=0.05,
        horizon=80,
        n=40,
        seed=0,
    )
    after = sum(cmp.banned.dose_days["ciprofloxacin"][20:])
    assert after == 0.0
    assert sum(cmp.control.dose_days["ciprofloxacin"][20:]) > 0.0
    assert cmp.banned.frequencies[-1] < cmp.control.frequencies[-1]
    assert "Not a history-match" in format_compare(cmp)


def test_2017_uses_tuh_campus() -> None:
    cmp = run_scenario(year=2017, bug="ecoli", drug="cipro", ban="none", horizon=3, n=10)
    assert cmp.campus_id == "TUH"
    assert cmp.p0 == pytest.approx(0.30)


def test_unknown_cell_fails() -> None:
    with pytest.raises(ValueError, match="no printed cell"):
        run_scenario(year=2025, bug="ecoli", drug="not_a_drug", ban="none", horizon=2, n=5)


def test_cli_scenario_writes_compare(tmp_path, capsys) -> None:
    main(
        [
            "scenario",
            "--year",
            "2025",
            "--bug",
            "ecoli",
            "--drug",
            "cipro",
            "--ban",
            "10",
            "--s-max",
            str(DEFAULT_S_MAX),
            "--output-root",
            str(tmp_path),
        ]
    )
    out = capsys.readouterr().out
    assert "starting resistant: 44.0%" in out
    assert "Not a history-match" in out
    compare = (
        tmp_path
        / "scenario"
        / "2025_escherichia_coli_ciprofloxacin_ban10"
        / "compare.txt"
    )
    assert compare.is_file()
