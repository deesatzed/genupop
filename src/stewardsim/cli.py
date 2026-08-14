"""stewardsim command line.

``stewardsim`` / ``stewardsim --version`` prints the package version.
``stewardsim study <yaml>`` runs a fixture study.
``stewardsim scenario`` runs a what-if start+ban pair (not AT-12).
``stewardsim odd`` / ``stewardsim trace`` emit live Parameter skeletons.
``stewardsim validate`` writes the AT gate file.
``stewardsim report`` refuses Tier 2/3 while AT-5 is not green.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _parse_study_args(rest: list[str]) -> tuple[str, str]:
    usage = "usage: stewardsim study <yaml> [--output-root DIR]"
    if not rest:
        raise SystemExit(usage)
    yaml_path = rest[0]
    output_root = "output"
    extra = rest[1:]
    if extra:
        if len(extra) == 2 and extra[0] == "--output-root":
            output_root = extra[1]
        else:
            raise SystemExit(usage)
    return yaml_path, output_root


def _run_scenario_cli(rest: list[str]) -> None:
    usage = (
        "usage: stewardsim scenario --year 2017|2024|2025 "
        "--bug NAME --drug NAME --ban none|DAY [--s-max 0.05] [--output-root DIR]"
    )
    flags: dict[str, str] = {}
    i = 0
    while i < len(rest):
        key = rest[i]
        if not key.startswith("--") or i + 1 >= len(rest):
            raise SystemExit(usage)
        flags[key[2:].replace("-", "_")] = rest[i + 1]
        i += 2
    required = {"year", "bug", "drug", "ban"}
    if not required.issubset(flags):
        raise SystemExit(usage)
    from stewardsim.scenario import DEFAULT_S_MAX, format_compare, run_scenario, write_compare

    try:
        year = int(flags["year"])
        s_max = float(flags["s_max"]) if "s_max" in flags else DEFAULT_S_MAX
        cmp = run_scenario(
            year=year,
            bug=flags["bug"],
            drug=flags["drug"],
            ban=flags["ban"],
            s_max=s_max,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(str(exc)) from exc
    root = flags.get("output_root", "output")
    ban_slug = "none" if cmp.ban_day is None else str(cmp.ban_day)
    bug_slug = cmp.organism.lower().replace(" ", "_").replace(".", "")
    outdir = (
        Path(root)
        / "scenario"
        / f"{cmp.year}_{bug_slug}_{cmp.drug}_ban{ban_slug}"
    )
    write_compare(cmp, outdir)
    print(format_compare(cmp), end="")
    print(outdir)


def _parse_report_args(rest: list[str]) -> int | None:
    usage = "usage: stewardsim report [--tier 1|2|3]"
    if not rest:
        return None
    if len(rest) == 2 and rest[0] == "--tier":
        try:
            tier = int(rest[1])
        except ValueError as exc:
            raise SystemExit(usage) from exc
        if tier not in {1, 2, 3}:
            raise SystemExit(usage)
        return tier
    raise SystemExit(usage)


def main(argv: list[str] | None = None) -> None:
    from stewardsim import __version__

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"--version", "-V"}:
        print(__version__)
        return
    if args[0] == "scenario":
        _run_scenario_cli(args[1:])
        return
    if args[0] == "study":
        yaml_path, output_root = _parse_study_args(args[1:])
        from stewardsim.runner import run_study

        run = run_study(yaml_path, output_root=output_root)
        print(run.outdir)
        return
    if args[0] == "odd":
        from stewardsim.reporting import emit_odd

        print(emit_odd(), end="")
        return
    if args[0] == "trace":
        from stewardsim.reporting import emit_trace

        print(emit_trace(), end="")
        return
    if args[0] == "validate":
        from stewardsim.reporting import write_at_gate

        print(write_at_gate())
        return
    if args[0] == "report":
        from stewardsim.reporting import report

        report(tier=_parse_report_args(args[1:]))
        return
    raise SystemExit(f"unknown command: {args[0]}")


if __name__ == "__main__":
    main(sys.argv[1:])
