"""Tests of gdcov.report: merge, tallies, ordering and written files."""

import json
from collections import Counter
from pathlib import Path

import pytest

from gdcov.instrument import CoverageMap
from gdcov.report import (
    FileCoverage,
    Tally,
    area_of,
    by_area,
    compute,
    file_page,
    index_page,
    load_hits,
    never_run,
    page_name,
    summary_text,
    total_of,
    write_reports,
)

COVERAGE: CoverageMap = {
    "total": 6,
    "files": {
        "res://ui/b.gd": {
            "probes": [(3, 2, "show"), (4, 3, "show"), (5, 6, "_hidden")],
            "functions": [("show", 1), ("_hidden", 5), ("empty", 8)],
        },
        "res://lib/world/a.gd": {
            "probes": [(0, 2, "f"), (1, 2, "f"), (2, 4, "g")],
            "functions": [("f", 1), ("g", 3)],
        },
    },
}


def test_tally() -> None:
    tally = Tally()
    assert tally.percent == 100.0
    tally.add(True)
    tally.add(False)
    tally.add(True)
    tally.add(True)
    assert (tally.lines, tally.hit) == (4, 3)
    assert tally.percent == 75.0


def test_load_hits_sums_files(tmp_path: Path) -> None:
    (tmp_path / "1.json").write_text(json.dumps({"hits": {"0": 2, "5": 1}}))
    (tmp_path / "2.json").write_text(json.dumps({"hits": {"0": 3}}))
    assert load_hits(sorted(tmp_path.glob("*.json"))) == Counter({0: 5, 5: 1})


@pytest.mark.parametrize(
    ("path", "depth", "area"),
    [
        ("res://main.gd", 1, "(root)"),
        ("res://main.gd", 2, "(root)"),
        ("res://ui/x.gd", 1, "ui"),
        ("res://ui/x.gd", 2, "ui"),
        ("res://lib/world/x.gd", 1, "lib"),
        ("res://lib/world/x.gd", 2, "lib/world"),
        ("res://a/b/c/x.gd", 2, "a/b"),
        ("res://a/b/c/x.gd", 3, "a/b/c"),
    ],
)
def test_area_of(path: str, depth: int, area: str) -> None:
    assert area_of(path, depth) == area


def _files() -> list[FileCoverage]:
    return compute(COVERAGE, {0: 4, 1: 0, 3: 1, 4: 2})


def test_compute_per_file_and_function() -> None:
    files = _files()
    assert [f.path for f in files] == ["res://lib/world/a.gd", "res://ui/b.gd"]
    world, ui = files
    assert (world.tally.lines, world.tally.hit) == (3, 1)
    assert world.line_hits == {2: 4, 4: 0}
    assert {n: (t.lines, t.hit) for n, t in world.functions.items()} == {
        "f": (2, 1),
        "g": (1, 0),
    }
    assert world.function_lines == {"f": 1, "g": 3}
    assert (ui.tally.lines, ui.tally.hit) == (3, 2)
    assert ui.line_hits == {2: 1, 3: 2, 6: 0}
    assert {n: (t.lines, t.hit) for n, t in ui.functions.items()} == {
        "show": (2, 2),
        "_hidden": (1, 0),
        "empty": (0, 0),
    }


def test_compute_probe_of_unknown_function() -> None:
    coverage: CoverageMap = {
        "total": 1,
        "files": {"res://x.gd": {"probes": [(0, 3, "lost")], "functions": []}},
    }
    file = compute(coverage, {})[0]
    assert (file.functions["lost"].lines, file.functions["lost"].hit) == (1, 0)


def test_by_area_and_total() -> None:
    files = _files()
    areas = by_area(files, 2)
    assert list(areas) == ["lib/world", "ui"]
    assert {a: (t.lines, t.hit) for a, t in areas.items()} == {
        "lib/world": (3, 1),
        "ui": (3, 2),
    }
    assert list(by_area(files, 1)) == ["lib", "ui"]
    total = total_of(files)
    assert (total.lines, total.hit) == (6, 3)


def test_by_area_sums_same_area() -> None:
    a = FileCoverage("res://ui/a.gd", Tally(4, 1))
    b = FileCoverage("res://ui/b.gd", Tally(2, 2))
    assert vars(by_area([a, b], 1)["ui"]) == {"lines": 6, "hit": 3}


def test_never_run_order() -> None:
    big = FileCoverage("res://z.gd")
    big.functions = {"huge": Tally(9, 0), "used": Tally(5, 1)}
    big.function_lines = {"huge": 10}
    small = FileCoverage("res://a.gd")
    small.functions = {"a": Tally(2, 0), "b": Tally(2, 0), "none": Tally(0, 0)}
    small.function_lines = {"b": 1, "a": 7}
    assert never_run([big, small]) == [
        ("res://z.gd", "huge", 10, 9),
        ("res://a.gd", "b", 1, 2),
        ("res://a.gd", "a", 7, 2),
    ]


def test_never_run_unknown_line_is_zero() -> None:
    file = FileCoverage("res://x.gd")
    file.functions = {"lost": Tally(1, 0)}
    assert never_run([file]) == [("res://x.gd", "lost", 0, 1)]


def test_summary_text() -> None:
    assert "      lib\n" in summary_text(_files(), "", 1)
    text = summary_text(_files(), "  suites here", 2)
    assert text == (
        "GDScript line coverage (lines of function bodies)\n"
        "\n"
        "  50.0 %       3 / 6      TOTAL\n"
        "\n"
        "Per area:\n"
        "  33.3 %       1 / 3      lib/world\n"
        "  66.7 %       2 / 3      ui\n"
        "\n"
        "Per file:\n"
        "  33.3 %       1 / 3      res://lib/world/a.gd\n"
        "  66.7 %       2 / 3      res://ui/b.gd\n"
        "\n"
        "Functions never executed (path:line function, measured lines):\n"
        "    1  res://lib/world/a.gd:3 g\n"
        "    1  res://ui/b.gd:5 _hidden\n"
        "\n"
        "Suites:\n"
        "  suites here\n"
    )


def test_page_name() -> None:
    assert page_name("res://lib/world/a.gd") == "lib__world__a.gd.html"


def test_file_page_marks_lines() -> None:
    ui = _files()[1]
    page = file_page(ui, "a\nb <x>\nc\nd\ne\nf")
    assert "<title>res://ui/b.gd</title>" in page
    assert "<h1>res://ui/b.gd 66.7 %</h1>" in page
    assert (
        '<tr class=""><td class="n">1</td><td class="c"></td><td><pre>a</pre>' in page
    )
    assert (
        '<tr class="hit"><td class="n">2</td><td class="c">1</td>'
        "<td><pre>b &lt;x&gt;</pre></td></tr>"
    ) in page
    assert '<tr class="miss"><td class="n">6</td><td class="c">0</td>' in page
    assert '<a href="index.html">index</a>' in page
    assert page.count("</tr><tr") == 5


def test_index_page() -> None:
    assert "<tr><td>lib</td>" in index_page(_files(), 1)
    page = index_page(_files(), 2)
    assert "<tr><td>lib/world</td>" in page
    assert "GDScript line coverage 50.0 % (3 / 6)" in page
    assert "<tr><td>ui</td><td>66.7 %</td><td>2 / 3</td></tr>" in page
    assert page.count("</tr><tr>") == 2
    assert (
        '<tr><td><a href="ui__b.gd.html">res://ui/b.gd</a></td>'
        "<td>66.7 %</td><td>2 / 3</td></tr>"
    ) in page


def _run_dir(tmp_path: Path) -> tuple[Path, Path]:
    out = tmp_path / "out"
    (out / "hits").mkdir(parents=True)
    (out / "coverage_map.json").write_text(json.dumps(COVERAGE))
    (out / "hits" / "h1.json").write_text(json.dumps({"hits": {"0": 1, "3": 2}}))
    (out / "hits" / "h2.json").write_text(json.dumps({"hits": {"4": 1}}))
    (out / "hits" / "ignored.txt").write_text("not json")
    project = tmp_path / "project"
    for relative in ("ui/b.gd", "lib/world/a.gd"):
        (project / relative).parent.mkdir(parents=True, exist_ok=True)
        (project / relative).write_text("l1\nl2\nl3\nl4\nl5\nl6\n")
    return out, project


def test_write_reports(tmp_path: Path) -> None:
    out, project = _run_dir(tmp_path)
    (out / "suites.json").write_text(
        json.dumps(
            [
                {
                    "suite": "test_a.gd",
                    "returncode": 0,
                    "summary": "3 checks",
                    "seconds": 1.5,
                },
                {
                    "suite": "test_b.gd",
                    "returncode": -1,
                    "summary": "",
                    "seconds": 1800.0,
                },
            ]
        )
    )
    write_reports(out, project, 2)
    total = write_reports(out, project, 2)
    assert (total.lines, total.hit) == (6, 3)
    summary = (out / "summary.txt").read_text()
    assert summary.endswith(
        "Suites:\n"
        "  rc=0        1.5s test_a.gd  3 checks\n"
        "  rc=-1    1800.0s test_b.gd  \n"
    )
    text = (out / "coverage.json").read_text()
    assert text.startswith('{\n "total": {\n  "lines": 6,\n  "hit": 3\n },')
    machine = json.loads(text)
    assert machine["total"] == {"lines": 6, "hit": 3}
    assert machine["areas"] == {
        "lib/world": {"lines": 3, "hit": 1},
        "ui": {"lines": 3, "hit": 2},
    }
    assert machine["files"]["res://lib/world/a.gd"] == {"lines": 3, "hit": 1}
    assert machine["never_run"] == [
        ["res://lib/world/a.gd", "g", 3, 1],
        ["res://ui/b.gd", "_hidden", 5, 1],
    ]
    assert "GDScript line coverage 50.0 %" in (out / "html" / "index.html").read_text()
    page = (out / "html" / "ui__b.gd.html").read_text()
    assert '<td class="c">2</td><td><pre>l2</pre>' in page


def test_write_reports_without_suites_file(tmp_path: Path) -> None:
    out, project = _run_dir(tmp_path)
    write_reports(out, project, 1)
    assert (out / "summary.txt").read_text().endswith("Suites:\n\n")
