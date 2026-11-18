"""Merges hit files with the coverage map and writes the text and HTML reports.

Outputs, under the report directory:

- ``summary.txt``: total, per area (directory cut at a given depth), per file, then never-executed functions sorted by
  their number of measured lines (largest first);
- ``coverage.json``: the same numbers, machine-readable;
- ``html/index.html`` plus one page per script, each line marked hit (with its count),
  missed, or not measured.
"""

import html
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from gdcov.instrument import CoverageMap


@dataclass
class Tally:
    """Measured and hit line counts."""

    lines: int = 0
    hit: int = 0

    @property
    def percent(self) -> float:
        """Share of hit lines; 100 when nothing is measured."""
        return 100.0 * self.hit / self.lines if self.lines else 100.0

    def add(self, hit: bool) -> None:
        """Counts one more measured line."""
        self.lines += 1
        self.hit += int(hit)


@dataclass
class FileCoverage:
    """Coverage of one script."""

    path: str
    tally: Tally = field(default_factory=Tally)
    functions: dict[str, Tally] = field(default_factory=dict)
    function_lines: dict[str, int] = field(default_factory=dict)
    line_hits: dict[int, int] = field(default_factory=dict)


def load_hits(paths: Iterable[Path]) -> Counter[int]:
    """Sums the per-probe counters of every hit file."""
    total: Counter[int] = Counter()
    for path in paths:
        hits: Mapping[str, int] = json.loads(path.read_text(encoding="utf-8"))["hits"]
        total.update({int(key): count for key, count in hits.items()})
    return total


def area_of(res_path: str, depth: int) -> str:
    """Report area: the script's directory cut to its first [param depth] levels;
    ``(root)`` for scripts at the project root."""
    folders = res_path.removeprefix("res://").split("/")[:-1]
    if not folders:
        return "(root)"
    return "/".join(folders[:depth])


def compute(coverage: CoverageMap, hits: Mapping[int, int]) -> list[FileCoverage]:
    """Per-file coverage, files in path order."""
    result: list[FileCoverage] = []
    for path, entry in sorted(coverage["files"].items()):
        file = FileCoverage(path)
        for name, line in entry["functions"]:
            file.functions[name] = Tally()
            file.function_lines[name] = line
        for probe_id, line, function in entry["probes"]:
            count = hits.get(probe_id, 0)
            file.tally.add(count > 0)
            file.functions.setdefault(function, Tally()).add(count > 0)
            file.line_hits[line] = file.line_hits.get(line, 0) + count
        result.append(file)
    return result


def by_area(files: Iterable[FileCoverage], depth: int) -> dict[str, Tally]:
    """Line tallies summed per [func area_of] area, areas sorted."""
    areas: dict[str, Tally] = {}
    for file in files:
        tally = areas.setdefault(area_of(file.path, depth), Tally())
        tally.lines += file.tally.lines
        tally.hit += file.tally.hit
    return dict(sorted(areas.items()))


def total_of(files: Iterable[FileCoverage]) -> Tally:
    """Line tally of every file together."""
    total = Tally()
    for file in files:
        total.lines += file.tally.lines
        total.hit += file.tally.hit
    return total


def never_run(files: Iterable[FileCoverage]) -> list[tuple[str, str, int, int]]:
    """Functions with measured lines and no hit: ``(path, name, header line, lines)``.

    Largest first; equal sizes in path then line order.
    """
    found = [
        (file.path, name, file.function_lines.get(name, 0), tally.lines)
        for file in files
        for name, tally in file.functions.items()
        if tally.lines > 0 and tally.hit == 0
    ]
    return sorted(found, key=lambda item: (-item[3], item[0], item[2]))


def _row(label: str, tally: Tally) -> str:
    return f"{tally.percent:6.1f} %  {tally.hit:6d} / {tally.lines:<6d} {label}"


def summary_text(files: list[FileCoverage], suites: str, depth: int) -> str:
    """The whole ``summary.txt`` text; [param suites] is a pre-formatted suite list."""
    lines = ["GDScript line coverage (lines of function bodies)", ""]
    lines.append(_row("TOTAL", total_of(files)))
    lines += ["", "Per area:"]
    lines += [_row(area, tally) for area, tally in by_area(files, depth).items()]
    lines += ["", "Per file:"]
    lines += [_row(f.path, f.tally) for f in files]
    lines += ["", "Functions never executed (path:line function, measured lines):"]
    lines += [
        f"{lines_count:5d}  {path}:{line} {name}"
        for path, name, line, lines_count in never_run(files)
    ]
    lines += ["", "Suites:", suites]
    return "\n".join(lines) + "\n"


def _css_class(count: int | None) -> str:
    if count is None:
        return ""
    return "hit" if count > 0 else "miss"


def file_page(file: FileCoverage, source: str) -> str:
    """HTML page of one script with every measured line marked."""
    rows = []
    for number, text in enumerate(source.split("\n"), start=1):
        count = file.line_hits.get(number)
        mark = "" if count is None else str(count)
        rows.append(
            f'<tr class="{_css_class(count)}"><td class="n">{number}</td>'
            f'<td class="c">{mark}</td><td><pre>{html.escape(text)}</pre></td></tr>'
        )
    title = html.escape(file.path)
    return (
        f"<!doctype html><meta charset=utf-8><title>{title}</title>{_STYLE}"
        f"<h1>{title} {file.tally.percent:.1f} %</h1>"
        f'<p><a href="index.html">index</a></p><table>{"".join(rows)}</table>'
    )


def page_name(res_path: str) -> str:
    """File name of a script's HTML page."""
    return res_path.removeprefix("res://").replace("/", "__") + ".html"


def index_page(files: list[FileCoverage], depth: int) -> str:
    """HTML index: total, areas, and one linked row per file."""
    total = total_of(files)
    area_rows = "".join(
        f"<tr><td>{html.escape(a)}</td><td>{t.percent:.1f} %</td>"
        f"<td>{t.hit} / {t.lines}</td></tr>"
        for a, t in by_area(files, depth).items()
    )
    file_rows = "".join(
        f'<tr><td><a href="{page_name(f.path)}">{html.escape(f.path)}</a></td>'
        f"<td>{f.tally.percent:.1f} %</td><td>{f.tally.hit} / {f.tally.lines}</td></tr>"
        for f in files
    )
    return (
        f"<!doctype html><meta charset=utf-8><title>GDScript coverage</title>{_STYLE}"
        f"<h1>GDScript line coverage {total.percent:.1f} % "
        f"({total.hit} / {total.lines})</h1><h2>Areas</h2><table>{area_rows}</table>"
        f"<h2>Files</h2><table>{file_rows}</table>"
    )


_STYLE = (
    "<style>body{font-family:sans-serif}pre{margin:0}td{padding:0 6px}"
    "td.n,td.c{text-align:right;color:#666}tr.hit{background:#dfd}"
    "tr.miss{background:#fdd}</style>"
)


def write_reports(out: Path, project: Path, depth: int) -> Tally:
    """Reads ``out/coverage_map.json``, ``out/hits/*.json``, ``out/suites.json``;
    writes ``out/summary.txt``, ``out/coverage.json`` and ``out/html/``.

    Args:
        out: Run directory.
        project: The original (not instrumented) project, for HTML sources.
        depth: Directory levels of a report area, see [func area_of].

    Returns:
        The total tally.
    """
    coverage: CoverageMap = json.loads((out / "coverage_map.json").read_text("utf-8"))
    files = compute(coverage, load_hits(sorted((out / "hits").glob("*.json"))))
    try:
        suites_json = json.loads((out / "suites.json").read_text("utf-8"))
    except FileNotFoundError:
        suites_json = []
    suites = "\n".join(
        f"  rc={s['returncode']:<4d} {s['seconds']:7.1f}s {s['suite']}  {s['summary']}"
        for s in suites_json
    )
    (out / "summary.txt").write_text(
        summary_text(files, suites, depth), encoding="utf-8"
    )
    machine = {
        "total": vars(total_of(files)),
        "areas": {a: vars(t) for a, t in by_area(files, depth).items()},
        "files": {f.path: vars(f.tally) for f in files},
        "never_run": never_run(files),
    }
    (out / "coverage.json").write_text(json.dumps(machine, indent=1), encoding="utf-8")
    pages = out / "html"
    pages.mkdir(exist_ok=True)
    (pages / "index.html").write_text(index_page(files, depth), encoding="utf-8")
    for file in files:
        source_path = project / file.path.removeprefix("res://")
        source = source_path.read_text(encoding="utf-8")
        (pages / page_name(file.path)).write_text(
            file_page(file, source), encoding="utf-8"
        )
    return total_of(files)
