"""Tests of gdcov.rustfuncs on a hand-made llvm-cov export."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from gdcov.rustfuncs import (
    RustFunction,
    clean_name,
    demangle,
    main,
    merge_records,
    never_executed,
    relative,
    report_lines,
)

ROOT = "/repo/crateX"
SOLVE = "_RNvNtCs19QNHY5L25T_8my_crate6search10build_tree"
CLOSURE = "_RNCNvNtCs19QNHY5L25T_8my_crate5world13pending_itemss_0B5_"
GENERIC = "_RNvNtCs19QNHY5L25T_8my_crate5world4tick"


def _record(
    name: str, count: int, file: str, regions: list[list[int]]
) -> dict[str, Any]:
    return {"name": name, "count": count, "filenames": [file], "regions": regions}


EXPORT: dict[str, Any] = {
    "data": [
        {
            "functions": [
                _record(
                    SOLVE, 0, f"{ROOT}/src/search.rs", [[10, 1, 12, 2], [11, 5, 20, 6]]
                ),
                _record(CLOSURE, 0, f"{ROOT}/src/world.rs", [[40, 21, 40, 30]]),
                _record(GENERIC, 3, f"{ROOT}/src/world.rs", [[50, 1, 60, 2]]),
                _record(GENERIC + "x", 2, f"{ROOT}/src/world.rs", [[50, 1, 55, 2]]),
                _record(SOLVE, 0, "/registry/dep.rs", [[1, 1, 99, 1]]),
                _record(SOLVE, 0, "/repo/crate2/src/x.rs", [[1, 1, 99, 1]]),
            ]
        }
    ]
}

needs_rustfilt = pytest.mark.skipif(shutil.which("rustfilt") is None, reason="rustfilt")


def test_merge_records_sums_instances_and_spans_all_regions() -> None:
    merged = merge_records(EXPORT["data"][0]["functions"][:4])
    assert merged == [
        RustFunction(f"{ROOT}/src/search.rs", 10, 11, SOLVE, 0),
        RustFunction(f"{ROOT}/src/world.rs", 40, 1, CLOSURE, 0),
        RustFunction(f"{ROOT}/src/world.rs", 50, 11, GENERIC, 5),
    ]


def test_merge_records_same_line_other_column_stays_apart() -> None:
    records = [
        _record("a", 0, "f.rs", [[5, 1, 5, 9]]),
        _record("b", 1, "f.rs", [[5, 10, 5, 20]]),
        _record("c", 0, "g.rs", [[5, 1, 5, 9]]),
    ]
    assert [f.mangled for f in merge_records(records)] == ["a", "b", "c"]


def test_never_executed_order() -> None:
    functions = [
        RustFunction("b.rs", 9, 2, "x", 0),
        RustFunction("a.rs", 9, 2, "y", 0),
        RustFunction("a.rs", 3, 2, "z", 0),
        RustFunction("a.rs", 1, 50, "run", 1),
        RustFunction("c.rs", 1, 7, "w", 0),
    ]
    assert [f.mangled for f in never_executed(functions)] == ["w", "z", "y", "x"]


def test_clean_name() -> None:
    assert clean_name("my_crate[1a2b]::world::f::h0123456789abcdef") == (
        "my_crate::world::f"
    )
    assert clean_name("a::h0123") == "a::h0123"
    assert clean_name("a[xyz]") == "a[xyz]"


def test_relative() -> None:
    assert relative("/repo/crateX/src/a.rs", "/repo/crateX/") == "src/a.rs"
    assert relative("/other/a.rs", "/repo/crate") == "/other/a.rs"
    assert relative("/repo/a.rs", "") == "/repo/a.rs"


def _fake_rustfilt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> None:
    tool = tmp_path / "rustfilt"
    tool.write_text(f"#!/bin/sh\n{body}\n")
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")


def test_demangle_failure_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_rustfilt(tmp_path, monkeypatch, "exit 3")
    with pytest.raises(subprocess.CalledProcessError):
        demangle(["a"])


def test_report_lines_needs_one_name_per_function(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_rustfilt(tmp_path, monkeypatch, "head -n 1")
    with pytest.raises(ValueError):
        report_lines(EXPORT, ROOT)


def test_demangle_empty_does_not_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_rustfilt(tmp_path, monkeypatch, "exit 3")
    assert demangle([]) == []


@needs_rustfilt
def test_demangle() -> None:
    assert demangle([SOLVE, CLOSURE]) == [
        "my_crate::search::build_tree",
        "my_crate::world::pending_items::{closure#1}",
    ]


@needs_rustfilt
def test_report_lines_only_inside_root() -> None:
    assert report_lines(EXPORT, ROOT) == [
        "   11  src/search.rs:10  my_crate::search::build_tree",
        "    1  src/world.rs:40  my_crate::world::pending_items::{closure#1}",
    ]


@needs_rustfilt
def test_main(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "cov.json"
    path.write_text(json.dumps(EXPORT))
    assert main(["--json", str(path), "--root", ROOT + "/"]) == 0
    assert capsys.readouterr().out == (
        "   11  src/search.rs:10  my_crate::search::build_tree\n"
        "    1  src/world.rs:40  my_crate::world::pending_items::{closure#1}\n"
    )


@needs_rustfilt
def test_main_default_root_keeps_absolute_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "cov.json"
    path.write_text(json.dumps(EXPORT))
    assert main(["-j", str(path)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "   99  /registry/dep.rs:1  my_crate::search::build_tree"
    assert len(lines) == 4


def test_main_help(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COLUMNS", "200")
    with pytest.raises(SystemExit):
        main(["--help"])
    text = capsys.readouterr().out
    assert text.startswith("usage: gdcov-rustfuncs [-h] -j JSON [-r ROOT]\n")
    assert (
        "\n``cargo llvm-cov report --json`` keeps one record per monomorphised" in text
    )
    assert "-j, --json JSON  llvm-cov export JSON file\n" in text
    assert (
        "-r, --root ROOT  crate directory: only its files are listed, relative to it "
        "(default: every file, absolute paths)\n"
    ) in text
    assert text.endswith("Example: gdcov-rustfuncs -j coverage.json -r /repo/crate\n")


def test_main_requires_json(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main([])
    assert "--json" in capsys.readouterr().err
