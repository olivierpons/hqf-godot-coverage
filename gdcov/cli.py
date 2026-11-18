"""Command line of gdcov: ``instrument``, ``run``, ``report``, or ``all`` three."""

import argparse
import logging
import re
import sys
from collections.abc import Sequence
from pathlib import Path

from gdcov.instrument import DEFAULT_EXCLUDES, instrument_project
from gdcov.report import write_reports
from gdcov.runner import (
    DEFAULT_TESTS,
    SuiteResult,
    find_godot,
    find_suites,
    run_suites,
)

DESCRIPTION = """\
GDScript line coverage for a Godot 4 project whose tests are headless scripts
extending SceneTree (by default tests/test_*.gd), each run with
godot --headless --script.

How it works: the project is copied to OUT/project (rsync, without .git and Cargo
target directories); every .gd file of the copy, except the excluded ones, gets a
probe call written on the same line as each statement of its function bodies, so
line numbers do not move. A probe increments a static counter of
res://__gdcov/rt.gd; when the scene tree exits, the counters are written to
OUT/hits/hits_<pid>_<usec>.json. The suites then run on the copy, and the report
merges every hit file with OUT/coverage_map.json.

Measured: statements of func bodies, property get/set bodies, one-line bodies
(func f(): return 1, else: x, match patterns), lambdas declared as statements.
Not measured: class-level initialisers, and the statements of a multi-line lambda
written inside brackets (connect(func(): ...)), which count as their enclosing
line.

Subcommands:
  instrument  copy and instrument the project into OUT
  run         run the suites of OUT/project, hits into OUT/hits, logs into OUT/logs
              (a suite's summary is its last output line, or the last match of
              --summary)
  report      write OUT/summary.txt, OUT/coverage.json and OUT/html/
  all         the three in a row (OUT/hits is emptied first)
"""

EPILOG = """\
Examples:
  gdcov all -p /path/to/project -o /path/to/run -j 4
  gdcov all -p . -o /path/to/run -T 'test/**/*_test.gd' -e 'test/*' -e 'addons/*'
  gdcov run -o /path/to/run -s '*_live.gd' -m '\\d+ passed, \\d+ failed'
  gdcov run -o /path/to/run -u tests/test_player.gd -g /opt/godot/godot
  gdcov report -p /path/to/project -o /path/to/run

Each suite runs with --headless --audio-driver Dummy, under nice -n 19 ionice -c 3
unless --no-nice is given: a coverage run keeps several Godot processes busy for a
long time, and at idle priority the desktop and other work stay responsive.
Exit code: 0, or 1 when a suite failed or timed out (the report is written anyway).
"""

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """The argument parser; options are listed in short-letter order."""
    parser = argparse.ArgumentParser(
        prog="gdcov",
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", choices=("instrument", "run", "report", "all"))
    parser.add_argument(
        "-d",
        "--depth",
        type=int,
        default=1,
        help="directory levels of a report area (default: 1)",
    )
    parser.add_argument(
        "-e",
        "--exclude",
        action="append",
        metavar="GLOB",
        help="script not to instrument, fnmatch on its project-relative path "
        "(repeatable; default: tests/*)",
    )
    parser.add_argument(
        "-g",
        "--godot",
        type=Path,
        help="Godot binary (default: godot on PATH, else the newest "
        "~/godot/Godot_v4*-stable_linux.x86_64)",
    )
    parser.add_argument(
        "-j", "--jobs", type=int, default=2, help="suites run at once (default: 2)"
    )
    parser.add_argument(
        "-m",
        "--summary",
        type=re.compile,
        metavar="REGEX",
        help="summary of a suite: last match of REGEX in its output "
        "(default: its last non-blank line)",
    )
    parser.add_argument(
        "-N",
        "--no-nice",
        dest="low_priority",
        action="store_false",
        help="run the suites at normal priority, without the default "
        "nice -n 19 ionice -c 3 (faster on an idle machine; on a desktop in use, "
        "the default keeps it responsive)",
    )
    parser.add_argument(
        "-o", "--out", type=Path, required=True, help="run directory (created)"
    )
    parser.add_argument(
        "-p",
        "--project",
        type=Path,
        default=Path.cwd(),
        help="original project directory (default: current directory)",
    )
    parser.add_argument(
        "-s",
        "--skip",
        action="append",
        metavar="GLOB",
        help="suite not to run, fnmatch on its project-relative path (repeatable)",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=1800.0,
        help="seconds before a suite is killed (default: 1800)",
    )
    parser.add_argument(
        "-u",
        "--suite",
        action="append",
        metavar="PATH",
        help="run only this suite, path relative to the project (repeatable; "
        "overrides --tests and --skip)",
    )
    parser.add_argument(
        "-T",
        "--tests",
        default=DEFAULT_TESTS,
        metavar="GLOB",
        help="suites to run, glob relative to the project, ** recurses "
        f"(default: {DEFAULT_TESTS})",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Runs the command; returns the process exit code."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    out: Path = args.out.resolve()
    project: Path = args.project
    results: list[SuiteResult] = []
    if args.command in ("instrument", "all"):
        excludes = tuple(args.exclude or DEFAULT_EXCLUDES)
        done = instrument_project(project, out, excludes)
        print(f"instrumented {done.files} files, {done.probes} probes")
    if args.command in ("run", "all"):
        hits = out / "hits"
        if args.command == "all" and hits.is_dir():
            for stale in hits.glob("*.json"):
                stale.unlink()
        godot = args.godot or find_godot(Path.home())
        copy = out / "project"
        suites = args.suite or find_suites(copy, args.tests, args.skip or ())
        results = run_suites(
            godot,
            copy,
            out,
            suites,
            args.jobs,
            args.timeout,
            args.summary,
            args.low_priority,
        )
    if args.command in ("report", "all"):
        total = write_reports(out, project, args.depth)
        print(f"{total.percent:.1f} % ({total.hit} / {total.lines}) -> {out}")
    return 1 if any(r.returncode != 0 for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
