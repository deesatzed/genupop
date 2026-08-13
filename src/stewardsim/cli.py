"""stewardsim command line.

``stewardsim`` / ``stewardsim --version`` prints the package version.
``stewardsim study <yaml>`` runs a fixture study.
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
    raise SystemExit(f"unknown command: {args[0]}")


if __name__ == "__main__":
    main(sys.argv[1:])
