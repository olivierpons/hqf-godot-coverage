"""Tests of gdcov.instrument: file selection, rewrite, runtime script and map."""

import json
import logging
import subprocess
from pathlib import Path

import pytest

from gdcov.instrument import (
    COPY_EXCLUDES,
    DEFAULT_EXCLUDES,
    MAP_NAME,
    RUNTIME_DIR,
    RUNTIME_TEMPLATE,
    copy_project,
    instrument_project,
    instrument_tree,
    project_scripts,
)


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "src"
    _write(root, "project.godot", "config_version=5\n")
    _write(root, "a.gd", "func f() -> void:\n\tpass\n\tpass")
    _write(root, "sub/b.gd", "extends Node\nfunc g() -> int:\n\treturn 1\n")
    _write(root, "tests/test_a.gd", "extends SceneTree\nfunc t() -> void:\n\tpass\n")
    _write(root, "nested/project.godot", "")
    _write(root, "nested/n.gd", "func n() -> void:\n\tpass\n")
    _write(root, "ignored/.gdignore", "")
    _write(root, "ignored/i.gd", "func i() -> void:\n\tpass\n")
    _write(root, ".godot/cache.gd", "func c() -> void:\n\tpass\n")
    _write(root, f"{RUNTIME_DIR}/rt.gd", "old")
    _write(root, ".git/HEAD", "ref")
    _write(root, "rust/target/big.bin", "x")
    return root


def test_project_scripts_skips_tests_nested_ignored_cache_and_runtime(
    project: Path,
) -> None:
    found = [
        p.relative_to(project).as_posix()
        for p in project_scripts(project, DEFAULT_EXCLUDES)
    ]
    assert found == ["a.gd", "sub/b.gd"]


def test_project_scripts_without_excludes_takes_tests(project: Path) -> None:
    found = [p.relative_to(project).as_posix() for p in project_scripts(project, ())]
    assert found == ["a.gd", "sub/b.gd", "tests/test_a.gd"]


def test_instrument_tree_rewrites_and_maps(project: Path) -> None:
    coverage = instrument_tree(project, DEFAULT_EXCLUDES)
    assert set(coverage) == {"total", "files"}
    assert coverage["total"] == 3
    assert coverage["files"] == {
        "res://a.gd": {"probes": [(0, 2, "f"), (1, 3, "f")], "functions": [("f", 1)]},
        "res://sub/b.gd": {"probes": [(2, 3, "g")], "functions": [("g", 2)]},
    }
    preload = f'preload("res://{RUNTIME_DIR}/rt.gd")'
    assert (project / "a.gd").read_text() == (
        "func f() -> void:\n\t_GDCOV_0.h(0); pass\n\t_GDCOV_0.h(1); pass\n"
        f"const _GDCOV_0 = {preload}\n"
    )
    assert (project / "sub/b.gd").read_text() == (
        "extends Node\nfunc g() -> int:\n\t_GDCOV_1.h(2); return 1\n"
        f"const _GDCOV_1 = {preload}\n"
    )
    runtime = (project / RUNTIME_DIR / "rt.gd").read_text()
    assert runtime == RUNTIME_TEMPLATE.format(count=3, runtime_dir=RUNTIME_DIR)
    assert "const COUNT: int = 3\n" in runtime
    assert '"hits": hits' in runtime
    assert 'preload("res://__gdcov/rt.gd")' in runtime


def test_instrument_tree_creates_runtime_dir(tmp_path: Path) -> None:
    _write(tmp_path, "a.gd", "func f() -> void:\n\tpass\n")
    instrument_tree(tmp_path, ())
    assert (tmp_path / RUNTIME_DIR / "rt.gd").is_file()


def test_copy_project_excludes_git_and_target(project: Path, tmp_path: Path) -> None:
    copy = tmp_path / "out" / "deep" / "copy"
    _write(copy, "stale.txt", "old")
    copy_project(project, copy)
    assert (copy / "a.gd").is_file()
    assert not (copy / ".git").exists()
    assert not (copy / "rust" / "target").exists()
    assert not (copy / "stale.txt").exists()
    assert ".git" in COPY_EXCLUDES


def test_instrument_project_writes_map_and_copy(project: Path, tmp_path: Path) -> None:
    out = tmp_path / "run"
    done = instrument_project(project, out)
    assert done.copy == out / "project"
    assert done.map_path == out / MAP_NAME
    assert (done.files, done.probes) == (2, 3)
    saved = json.loads(done.map_path.read_text())
    assert saved["total"] == 3
    assert saved["files"]["res://a.gd"]["probes"] == [[0, 2, "f"], [1, 3, "f"]]
    assert (project / "a.gd").read_text() == "func f() -> void:\n\tpass\n\tpass"
    assert "_GDCOV_0" in (done.copy / "a.gd").read_text()


def test_copy_project_failure_raises(tmp_path: Path) -> None:
    with pytest.raises(subprocess.CalledProcessError):
        copy_project(tmp_path / "missing", tmp_path / "copy")


def test_copy_project_creates_missing_parents(project: Path, tmp_path: Path) -> None:
    copy = tmp_path / "new" / "deep" / "copy"
    copy_project(project, copy)
    assert (copy / "sub" / "b.gd").read_text() == (project / "sub" / "b.gd").read_text()


def test_instrument_twice_and_log(
    project: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="gdcov.instrument")
    instrument_project(project, tmp_path / "run")
    done = instrument_project(project, tmp_path / "run")
    assert done.probes == 3
    assert caplog.messages == ["3 probes in 2 files", "3 probes in 2 files"]
    assert (done.copy / "a.gd").read_text().count("_GDCOV_0 = ") == 1


def test_instrument_project_default_excludes_tests(
    project: Path, tmp_path: Path
) -> None:
    done = instrument_project(project, tmp_path / "run")
    assert "_GDCOV" not in (done.copy / "tests/test_a.gd").read_text()


def test_instrument_project_custom_excludes(project: Path, tmp_path: Path) -> None:
    done = instrument_project(project, tmp_path / "run", ("sub/*",))
    assert done.files == 2
    assert "_GDCOV" in (done.copy / "tests/test_a.gd").read_text()
