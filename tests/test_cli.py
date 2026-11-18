"""Tests of gdcov.cli, end to end with a fake Godot binary."""

import argparse
import json
import logging
import re
import subprocess
import sys
from pathlib import Path

import pytest

from gdcov.cli import DESCRIPTION, EPILOG, build_parser, main
from gdcov.runner import SuiteResult


def test_parser_actions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    parser = build_parser()
    assert parser.prog == "gdcov"
    assert parser.formatter_class is argparse.RawDescriptionHelpFormatter
    assert (parser.description, parser.epilog) == (DESCRIPTION, EPILOG)
    actions = [
        (a.option_strings, a.dest, a.help, a.metavar, a.default, a.type, a.required)
        for a in parser._actions[1:]
    ]
    assert actions == [
        ([], "command", None, None, None, None, True),
        (
            ["-d", "--depth"],
            "depth",
            "directory levels of a report area (default: 1)",
            None,
            1,
            int,
            False,
        ),
        (
            ["-e", "--exclude"],
            "exclude",
            "script not to instrument, fnmatch on its project-relative path "
            "(repeatable; default: tests/*)",
            "GLOB",
            None,
            None,
            False,
        ),
        (
            ["-g", "--godot"],
            "godot",
            "Godot binary (default: godot on PATH, else the newest "
            "~/godot/Godot_v4*-stable_linux.x86_64)",
            None,
            None,
            Path,
            False,
        ),
        (
            ["-j", "--jobs"],
            "jobs",
            "suites run at once (default: 2)",
            None,
            2,
            int,
            False,
        ),
        (
            ["-m", "--summary"],
            "summary",
            "summary of a suite: last match of REGEX in its output "
            "(default: its last non-blank line)",
            "REGEX",
            None,
            re.compile,
            False,
        ),
        (["-o", "--out"], "out", "run directory (created)", None, None, Path, True),
        (
            ["-p", "--project"],
            "project",
            "original project directory (default: current directory)",
            None,
            tmp_path,
            Path,
            False,
        ),
        (
            ["-s", "--skip"],
            "skip",
            "suite not to run, fnmatch on its project-relative path (repeatable)",
            "GLOB",
            None,
            None,
            False,
        ),
        (
            ["-t", "--timeout"],
            "timeout",
            "seconds before a suite is killed (default: 1800)",
            None,
            1800.0,
            float,
            False,
        ),
        (
            ["-u", "--suite"],
            "suite",
            "run only this suite, path relative to the project (repeatable; "
            "overrides --tests and --skip)",
            "PATH",
            None,
            None,
            False,
        ),
        (
            ["-T", "--tests"],
            "tests",
            "suites to run, glob relative to the project, ** recurses "
            "(default: tests/test_*.gd)",
            "GLOB",
            "tests/test_*.gd",
            None,
            False,
        ),
    ]
    assert [type(a).__name__ for a in parser._actions[2:]] == [
        "_StoreAction",
        "_AppendAction",
        "_StoreAction",
        "_StoreAction",
        "_StoreAction",
        "_StoreAction",
        "_StoreAction",
        "_AppendAction",
        "_StoreAction",
        "_AppendAction",
        "_StoreAction",
    ]
    assert parser._actions[1].choices == ("instrument", "run", "report", "all")


FAKE_GODOT = """\
#!/bin/sh
# Writes a hit file covering probe 0, like an instrumented run would.
echo '{"hits": {"0": 1}}' > "$GDCOV_OUT/hits_1.json"
echo "1 checks, 0 errors, 0 failures"
case "$7" in *fail*) exit 1 ;; esac
"""


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "src"
    (root / "tests").mkdir(parents=True)
    (root / "project.godot").write_text("")
    (root / "a.gd").write_text("func f() -> void:\n\tpass\n\tpass\n")
    (root / "tests" / "test_a.gd").write_text("extends SceneTree\n")
    (root / "tests" / "test_b_live.gd").write_text("extends SceneTree\n")
    return root


@pytest.fixture
def godot(tmp_path: Path) -> Path:
    path = tmp_path / "godot"
    path.write_text(FAKE_GODOT)
    path.chmod(0o755)
    return path


def test_parser_defaults_and_short_options() -> None:
    args = build_parser().parse_args(["run", "-o", "/o"])
    assert (args.jobs, args.timeout, args.exclude, args.skip, args.suite) == (
        2,
        1800.0,
        None,
        None,
        None,
    )
    assert (args.summary, args.tests, args.depth) == (None, "tests/test_*.gd", 1)
    args = build_parser().parse_args(
        "all -d 2 -e x -g /g -j 3 -m a+ -o /o -p /p -s y -t 5 -u z -T w".split()
    )
    assert (args.summary, args.tests, args.depth) == (re.compile("a+"), "w", 2)
    assert args.exclude == ["x"]
    assert (args.godot, args.jobs, args.out, args.project) == (
        Path("/g"),
        3,
        Path("/o"),
        Path("/p"),
    )
    assert (args.skip, args.timeout, args.suite) == (["y"], 5.0, ["z"])


def test_help_lists_long_options(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--help"])
    text = capsys.readouterr().out
    for option in (
        "--depth",
        "--exclude",
        "--godot",
        "--jobs",
        "--summary",
        "--out",
        "--project",
        "--skip",
        "--timeout",
        "--suite",
        "--tests",
    ):
        assert option in text
    assert "How it works" in text
    assert "Examples:" in text


def test_all(
    project: Path,
    godot: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "run"
    (out / "hits").mkdir(parents=True)
    (out / "hits" / "stale.json").write_text('{"hits": {"1": 5}}')
    argv = ["all", "-p", "src", "-o", "run", "-g", str(godot)]
    assert main(argv) == 0
    assert capsys.readouterr().out == (
        f"instrumented 1 files, 2 probes\n50.0 % (1 / 2) -> {out}\n"
    )
    suites = json.loads((out / "suites.json").read_text())
    assert [s["suite"] for s in suites] == ["tests/test_a.gd", "tests/test_b_live.gd"]
    assert suites[0]["summary"] == "1 checks, 0 errors, 0 failures"
    assert not (out / "hits" / "stale.json").exists()
    assert "  50.0 %       1 / 2      TOTAL" in (out / "summary.txt").read_text()


def test_steps_one_by_one(project: Path, godot: Path, tmp_path: Path) -> None:
    out = tmp_path / "run"
    assert main(["instrument", "-p", str(project), "-o", str(out), "-e", "x/*"]) == 0
    assert not (out / "suites.json").exists()
    (out / "hits").mkdir()
    (out / "hits" / "kept.json").write_text('{"hits": {"1": 5}}')
    argv = ["run", "-o", str(out), "-g", str(godot), "-u", "tests/test_fail.gd"]
    assert main(argv) == 1
    assert (out / "hits" / "kept.json").exists()
    assert not (out / "summary.txt").exists()
    assert main(["report", "-p", str(project), "-o", str(out)]) == 0
    assert " 100.0 %       2 / 2      TOTAL" in (out / "summary.txt").read_text()


def test_report_depth_option(project: Path, tmp_path: Path) -> None:
    (project / "lib" / "world").mkdir(parents=True)
    (project / "lib" / "world" / "w.gd").write_text("func f() -> void:\n\tpass\n")
    out = tmp_path / "run"
    main(["instrument", "-p", str(project), "-o", str(out)])
    main(["report", "-p", str(project), "-o", str(out), "-d", "2"])
    assert "lib/world\n" in (out / "summary.txt").read_text()
    main(["report", "-p", str(project), "-o", str(out)])
    summary = (out / "summary.txt").read_text()
    assert "lib\n" in summary
    assert "lib/world\n" not in summary


def test_run_passes_options_to_run_suites(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "run"
    main(["instrument", "-p", str(project), "-o", str(out)])
    seen: list[tuple[object, ...]] = []

    def record(*args: object) -> list[SuiteResult]:
        seen.append(args)
        return [SuiteResult("test_a.gd", 0, "", 0.0)]

    monkeypatch.setattr("gdcov.cli.run_suites", record)
    home = tmp_path / "home"
    (home / "godot").mkdir(parents=True)
    (home / "godot" / "Godot_v4.7.2-stable_linux.x86_64").write_text("")
    monkeypatch.setattr("gdcov.cli.Path.home", lambda: home)
    monkeypatch.setattr("gdcov.runner.shutil.which", lambda name: None)
    argv = ["run", "-o", str(out), "-j", "3", "-t", "7", "-m", "x", "-s", "*_live*"]
    assert main(argv) == 0
    assert seen == [
        (
            home / "godot" / "Godot_v4.7.2-stable_linux.x86_64",
            out / "project",
            out,
            ["tests/test_a.gd"],
            3,
            7.0,
            re.compile("x"),
        )
    ]


def test_run_tests_glob(project: Path, godot: Path, tmp_path: Path) -> None:
    out = tmp_path / "run"
    main(["instrument", "-p", str(project), "-o", str(out)])
    argv = ["run", "-o", str(out), "-g", str(godot), "-T", "tests/*_live.gd"]
    assert main(argv) == 0
    suites = json.loads((out / "suites.json").read_text())
    assert [s["suite"] for s in suites] == ["tests/test_b_live.gd"]


def test_instrument_exclude_option(project: Path, tmp_path: Path) -> None:
    out = tmp_path / "run"
    main(["instrument", "-p", str(project), "-o", str(out), "-e", "a.gd"])
    assert "_GDCOV" in (out / "project" / "tests" / "test_a.gd").read_text()
    assert "_GDCOV" not in (out / "project" / "a.gd").read_text()


def test_run_with_skip(project: Path, godot: Path, tmp_path: Path) -> None:
    out = tmp_path / "run"
    main(["instrument", "-p", str(project), "-o", str(out)])
    assert main(["run", "-o", str(out), "-g", str(godot), "-s", "*/test_a.gd"]) == 0
    suites = json.loads((out / "suites.json").read_text())
    assert [s["suite"] for s in suites] == ["tests/test_b_live.gd"]


def test_module_entry_point() -> None:
    done = subprocess.run(
        [sys.executable, "-m", "gdcov", "--help"],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).parent.parent,
    )
    assert "usage: gdcov" in done.stdout


def test_main_logs_bare_messages_at_info(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "gdcov.cli.logging.basicConfig", lambda **kwargs: calls.append(kwargs)
    )
    main(["instrument", "-p", str(project), "-o", str(tmp_path / "run")])
    assert calls == [{"level": logging.INFO, "format": "%(message)s"}]


def test_module_logs_messages_only(project: Path, tmp_path: Path) -> None:
    done = subprocess.run(
        [sys.executable, "-m", "gdcov", "instrument"]
        + ["-p", str(project), "-o", str(tmp_path / "run")],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).parent.parent,
    )
    assert done.stderr == "2 probes in 1 files\n"
    assert done.stdout == "instrumented 1 files, 2 probes\n"
