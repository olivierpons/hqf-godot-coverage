"""Copies a Godot project and inserts hit probes into the copy's GDScript files.

The copy gets ``res://__gdcov/rt.gd``, a script with one static counter per probe, and
``coverage_map.json`` (next to the copy) that maps probe ids back to file, line and
function. Each instrumented file ends with ``const _GDCOV_<n> = preload(...)``: a name
unique per file, so a script extending another instrumented script does not redeclare
its parent's constant.
"""

import fnmatch
import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from gdcov.scanner import instrument, scan

logger = logging.getLogger(__name__)

RUNTIME_DIR = "__gdcov"
MAP_NAME = "coverage_map.json"
DEFAULT_EXCLUDES: tuple[str, ...] = ("tests/*",)
COPY_EXCLUDES: tuple[str, ...] = (".git", "target", "mutants.out*", "__pycache__")


class FileEntry(TypedDict):
    """Coverage map entry of one script: ``[id, line, function]`` per probe."""

    probes: list[tuple[int, int, str]]
    functions: list[tuple[str, int]]


class CoverageMap(TypedDict):
    """The whole coverage map, keyed by ``res://`` path."""

    total: int
    files: dict[str, FileEntry]


RUNTIME_TEMPLATE = """\
## Hit counters of the coverage probes; written to $GDCOV_OUT when the tree exits.
extends RefCounted

const COUNT: int = {count}

static var c: PackedInt64Array = PackedInt64Array()
static var _hooked: bool = false
static var _file: String = ""
static var _guard: RefCounted = null


class _Guard:
\textends RefCounted

\tfunc _notification(what: int) -> void:
\t\tif what == NOTIFICATION_PREDELETE:
\t\t\t_GDCOV_RT.dump()


static func _static_init() -> void:
\tc.resize(COUNT)
\t_guard = _Guard.new()


static func h(i: int) -> bool:
\tc[i] += 1
\tif not _hooked:
\t\t_hook()
\treturn true


static func _hook() -> void:
\tvar tree: SceneTree = Engine.get_main_loop() as SceneTree
\tif tree == null or tree.root == null:
\t\treturn
\t_hooked = true
\ttree.root.tree_exiting.connect(dump)


## Writes every non-zero counter as JSON; later calls overwrite the same file.
static func dump() -> void:
\tvar out: String = OS.get_environment("GDCOV_OUT")
\tif out.is_empty():
\t\treturn
\tif _file.is_empty():
\t\t_file = "%s/hits_%d_%d.json" % [out, OS.get_process_id(), Time.get_ticks_usec()]
\tvar hits: Dictionary = {{}}
\tfor i: int in COUNT:
\t\tif c[i] != 0:
\t\t\thits[str(i)] = c[i]
\tvar f: FileAccess = FileAccess.open(_file, FileAccess.WRITE)
\tif f == null:
\t\tpush_error("gdcov: cannot write %s" % _file)
\t\treturn
\tf.store_string(JSON.stringify({{"hits": hits}}))
\tf.close()

const _GDCOV_RT = preload("res://{runtime_dir}/rt.gd")
"""


@dataclass(frozen=True)
class Instrumented:
    """Outcome of [func instrument_project]."""

    copy: Path
    map_path: Path
    files: int
    probes: int


def copy_project(project: Path, copy: Path) -> None:
    """Mirrors [param project] into [param copy], skipping VCS and build directories.

    Raises:
        subprocess.CalledProcessError: rsync failed.
    """
    copy.mkdir(parents=True, exist_ok=True)
    command = ["rsync", "-a", "--delete"]
    command += [f"--exclude={pattern}" for pattern in COPY_EXCLUDES]
    command += [f"{project}/", f"{copy}/"]
    subprocess.run(command, check=True)


def _nested_roots(root: Path) -> list[Path]:
    """Directories Godot does not import: nested projects and ``.gdignore`` folders."""
    nested = [p.parent for p in root.rglob("project.godot") if p.parent != root]
    nested += [p.parent for p in root.rglob(".gdignore")]
    return nested


def project_scripts(root: Path, excludes: tuple[str, ...]) -> list[Path]:
    """The ``.gd`` files of [param root] to instrument, sorted by path.

    Args:
        root: Project directory (holds ``project.godot``).
        excludes: ``fnmatch`` patterns on the path relative to [param root]; ``*``
            also matches ``/``.
    """
    skipped = _nested_roots(root)
    result: list[Path] = []
    for path in sorted(root.rglob("*.gd")):
        relative = path.relative_to(root).as_posix()
        if relative.startswith((".godot/", f"{RUNTIME_DIR}/")):
            continue
        if any(path.is_relative_to(n) for n in skipped):
            continue
        if any(fnmatch.fnmatch(relative, pattern) for pattern in excludes):
            continue
        result.append(path)
    return result


def instrument_tree(root: Path, excludes: tuple[str, ...]) -> CoverageMap:
    """Rewrites the scripts of [param root] in place and writes the runtime script."""
    files: dict[str, FileEntry] = {}
    next_id = 0
    preload = f'preload("res://{RUNTIME_DIR}/rt.gd")'
    for number, path in enumerate(project_scripts(root, excludes)):
        source = path.read_text(encoding="utf-8")
        const_name = f"_GDCOV_{number}"
        text, probes = instrument(source, const_name, next_id)
        if not text.endswith("\n"):
            text += "\n"
        path.write_text(f"{text}const {const_name} = {preload}\n", encoding="utf-8")
        res_path = "res://" + path.relative_to(root).as_posix()
        files[res_path] = {
            "probes": [(next_id + k, p.line, p.function) for k, p in enumerate(probes)],
            "functions": [(f.name, f.line) for f in scan(source).functions],
        }
        next_id += len(probes)
    coverage: CoverageMap = {"total": next_id, "files": files}
    runtime = root / RUNTIME_DIR
    runtime.mkdir(exist_ok=True)
    (runtime / "rt.gd").write_text(
        RUNTIME_TEMPLATE.format(count=next_id, runtime_dir=RUNTIME_DIR),
        encoding="utf-8",
    )
    return coverage


def instrument_project(
    project: Path, out: Path, excludes: tuple[str, ...] = DEFAULT_EXCLUDES
) -> Instrumented:
    """Copies [param project] to ``out/project``, instruments it, writes the map.

    Raises:
        subprocess.CalledProcessError: The copy failed.
    """
    copy = out / "project"
    copy_project(project, copy)
    coverage = instrument_tree(copy, excludes)
    map_path = out / MAP_NAME
    map_path.write_text(json.dumps(coverage), encoding="utf-8")
    logger.info("%d probes in %d files", coverage["total"], len(coverage["files"]))
    return Instrumented(copy, map_path, len(coverage["files"]), coverage["total"])
