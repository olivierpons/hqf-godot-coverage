"""Tests of gdcov.runner, with a shell script standing in for Godot."""

import json
import logging
import re
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from gdcov.runner import (
    DEFAULT_TESTS,
    TIMEOUT_RC,
    SuiteResult,
    find_godot,
    find_suites,
    log_name,
    run_suite,
    run_suites,
    suite_command,
    summary_line,
)

FAKE_GODOT = """\
#!/bin/sh
# Prints its arguments and environment, then behaves as the suite name asks.
echo "args: $*"
echo "out: $GDCOV_OUT"
echo "mark: $GDCOV_TEST_MARK"
echo "to stderr" >&2
printf 'bad \\377 byte\\n'
case "$7" in
  *fail*) echo "3 checks, 1 error, 2 failures"; exit 1 ;;
  *slow*) sleep 5 ;;
  *nap*) sleep 1 ;;
  *) echo "1 check, 0 errors, 0 failures"; echo "12 checks, 0 errors, 0 failures" ;;
esac
"""


SUMMARY = re.compile(r"\d+ checks?, \d+ errors?, \d+ failures?")


@pytest.fixture
def godot(tmp_path: Path) -> Path:
    path = tmp_path / "fake_godot"
    path.write_text(FAKE_GODOT)
    path.chmod(0o755)
    return path


@pytest.fixture
def no_godot_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("gdcov.runner.shutil.which", lambda name: None)


def test_find_godot_prefers_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "godot"
    folder.mkdir()
    (folder / "Godot_v4.7-stable_linux.x86_64").write_text("")
    seen: list[str] = []

    def which(name: str) -> str:
        seen.append(name)
        return "/usr/bin/godot"

    monkeypatch.setattr("gdcov.runner.shutil.which", which)
    assert find_godot(tmp_path) == Path("/usr/bin/godot")
    assert seen == ["godot"]


@pytest.mark.usefixtures("no_godot_on_path")
def test_find_godot_takes_highest_version(tmp_path: Path) -> None:
    folder = tmp_path / "godot"
    folder.mkdir()
    for name in ("4.10.1", "4.9", "4.7.2", "3.9"):
        (folder / f"Godot_v{name}-stable_linux.x86_64").write_text("")
    (folder / "Godot_v4.99-beta_linux.x86_64").write_text("")
    (tmp_path / "Godot_v4.11-stable_linux.x86_64").write_text("")
    assert find_godot(tmp_path) == folder / "Godot_v4.10.1-stable_linux.x86_64"


@pytest.mark.usefixtures("no_godot_on_path")
def test_find_godot_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError) as caught:
        find_godot(tmp_path)
    assert str(caught.value) == (
        f"no godot on PATH and no Godot 4 binary under {tmp_path / 'godot'}"
    )


def test_find_suites_filters(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_b.gd").write_text("## Doc\nextends SceneTree\n")
    (tests / "test_a.gd").write_text("extends SceneTree\n")
    (tests / "test_node.gd").write_text("extends Node\n# extends SceneTree\n")
    (tests / "test_loop.gd").write_text("extends MainLoop\n")
    (tests / "test_treey.gd").write_text("extends SceneTreey\n")
    (tests / "test_x_live.gd").write_text("extends SceneTree\n")
    (tests / "helper.gd").write_text("extends SceneTree\n")
    (tests / "deep").mkdir()
    (tests / "deep" / "test_d.gd").write_text("extends SceneTree\n")
    assert DEFAULT_TESTS == "tests/test_*.gd"
    assert find_suites(tmp_path, DEFAULT_TESTS, ()) == [
        "tests/test_a.gd",
        "tests/test_b.gd",
        "tests/test_x_live.gd",
    ]
    assert find_suites(tmp_path, DEFAULT_TESTS, ["*_live.gd", "tests/test_b*"]) == [
        "tests/test_a.gd",
    ]
    assert find_suites(tmp_path, "tests/**/test_d.gd", []) == ["tests/deep/test_d.gd"]
    assert find_suites(tmp_path, "**/test_*.gd", ["test*/test_[!d]*"]) == [
        "tests/deep/test_d.gd"
    ]


def test_summary_line_with_pattern() -> None:
    pattern = re.compile(r"(\d+) checks?, (\d+) failures?")
    assert summary_line("x\n1 check, 0 failures\ny\n", pattern) == (
        "1 check, 0 failures"
    )
    assert summary_line("2 checks, 1 failure\n9 checks, 4 failures", pattern) == (
        "9 checks, 4 failures"
    )
    assert summary_line("nothing", pattern) == ""


def test_summary_line_without_pattern() -> None:
    assert summary_line("a\n  last one  \n \n\n", None) == "last one"
    assert summary_line(" \n", None) == ""
    assert summary_line("", None) == ""


def test_log_name() -> None:
    assert log_name("tests/deep/test_a.gd") == "tests__deep__test_a.gd.log"


def test_suite_command() -> None:
    assert suite_command(Path("/g"), Path("/c"), "tests/test_a.gd") == [
        "nice",
        "-n",
        "19",
        "ionice",
        "-c",
        "3",
        "/g",
        "--headless",
        "--audio-driver",
        "Dummy",
        "--path",
        "/c",
        "--script",
        "res://tests/test_a.gd",
    ]


def _prepare(out: Path) -> None:
    (out / "logs").mkdir(parents=True)


def _clock(monkeypatch: pytest.MonkeyPatch, *times: float) -> None:
    ticks: Iterator[float] = iter(times)
    monkeypatch.setattr("gdcov.runner.time.monotonic", lambda: next(ticks))


def _log(out: Path, suite: str) -> str:
    return (out / "logs" / log_name(suite)).read_bytes().decode(errors="replace")


def test_run_suite_success(
    godot: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    out = tmp_path / "out"
    _prepare(out)
    _clock(monkeypatch, 10.0, 12.66)
    monkeypatch.setenv("GDCOV_TEST_MARK", "kept")
    caplog.set_level(logging.INFO, logger="gdcov.runner")
    result = run_suite(godot, tmp_path / "copy", "tests/test_ok.gd", out, 30, SUMMARY)
    assert result == SuiteResult(
        "tests/test_ok.gd", 0, "12 checks, 0 errors, 0 failures", 2.7
    )
    log = _log(out, "tests/test_ok.gd")
    assert f"out: {out / 'hits'}\n" in log
    assert (
        f"args: --headless --audio-driver Dummy --path {tmp_path / 'copy'} "
        "--script res://tests/test_ok.gd\n"
    ) in log
    assert "mark: kept\n" in log
    assert "to stderr\n" in log
    assert caplog.messages == [
        "tests/test_ok.gd rc=0 3s 12 checks, 0 errors, 0 failures"
    ]


def test_run_suite_default_summary_is_last_line(godot: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    _prepare(out)
    result = run_suite(godot, tmp_path, "test_fail.gd", out, 30, None)
    assert result.summary == "3 checks, 1 error, 2 failures"


def test_run_suite_failure_and_timeout(godot: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    _prepare(out)
    failed = run_suite(godot, tmp_path, "test_fail.gd", out, 30, SUMMARY)
    assert (failed.returncode, failed.summary) == (1, "3 checks, 1 error, 2 failures")
    slow = run_suite(godot, tmp_path, "test_slow.gd", out, 0.5, SUMMARY)
    assert slow.returncode == TIMEOUT_RC
    assert slow.summary == ""
    assert slow.seconds < 4


def test_run_suites_writes_json(godot: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    suites = ["test_ok.gd", "test_fail.gd"]
    results = run_suites(godot, tmp_path, out, suites, 2, 30, SUMMARY)
    assert [r.suite for r in results] == ["test_ok.gd", "test_fail.gd"]
    assert (out / "hits").is_dir()
    assert "mark: " in _log(out, "test_ok.gd")
    text = (out / "suites.json").read_text()
    assert text.startswith('[\n {\n  "suite": "test_ok.gd",\n  "returncode": 0,')
    saved = json.loads(text)
    assert [s["returncode"] for s in saved] == [0, 1]
    assert saved[1]["summary"] == "3 checks, 1 error, 2 failures"
    assert set(saved[0]) == {"suite", "returncode", "summary", "seconds"}
    assert isinstance(results[0], SuiteResult)


def test_run_suites_passes_copy_and_timeout(godot: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    copy = tmp_path / "the_copy"
    results = run_suites(godot, copy, out, ["test_slow.gd"], 1, 0.5, None)
    assert results[0].returncode == TIMEOUT_RC
    run_suites(godot, copy, out, ["test_ok.gd"], 1, 30, None)
    assert f"--path {copy} " in _log(out, "test_ok.gd")


def test_run_suites_runs_at_most_jobs_at_once(godot: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    start = time.monotonic()
    suites = ["test_nap1.gd", "test_nap2.gd"]
    results = run_suites(godot, tmp_path, out, suites, 1, 30, None)
    assert time.monotonic() - start >= 2.0
    assert all(r.returncode == 0 for r in results)


def test_run_suites_creates_nested_out(godot: Path, tmp_path: Path) -> None:
    out = tmp_path / "a" / "b"
    result = run_suites(godot, tmp_path, out, ["test_ok.gd"], 1, 30, None)[0]
    assert result.returncode == 0


def test_run_suites_reuses_existing_dirs(godot: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    (out / "hits").mkdir(parents=True)
    (out / "logs").mkdir()
    result = run_suites(godot, tmp_path, out, ["test_ok.gd"], 1, 30, None)[0]
    assert result.returncode == 0
