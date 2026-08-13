"""stewardsim command line.

``stewardsim`` / ``stewardsim --version`` prints the package version.
``stewardsim study <yaml>`` runs a fixture study.
``stewardsim odd`` / ``stewardsim trace`` emit live Parameter skeletons.
``stewardsim validate`` writes the AT gate file.
``stewardsim report`` refuses Tier 2/3 while AT-5 is not green.
"""

from __future__ import annotations

import sys


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
