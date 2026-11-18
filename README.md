# hqf-godot-coverage

[![CI](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml/badge.svg)](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776ab.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Godot 4](https://img.shields.io/badge/Godot-4-478cbf.svg?logo=godotengine&logoColor=white)](https://godotengine.org/)

Code coverage for Godot 4 games:

- `gdcov`: line coverage of GDScript, measured while the project's headless test
  suites run;
- `rust_cov.zsh`: line and region coverage of a Rust crate (a
  [godot-rust](https://godot-rust.github.io/) GDExtension or any other) under
  `cargo test`, with the list of functions no test ever ran.

## How gdcov works

1. **instrument**: the project is copied to `OUT/project` (rsync, without `.git`,
   Cargo `target` directories, `mutants.out*` and `__pycache__`). In every `.gd` file
   of the copy, except the excluded ones, a probe call is written on the same line as
   each statement of a function body, so line numbers (and error messages) do not
   move. The probes count hits in static counters of `res://__gdcov/rt.gd`.
   `OUT/coverage_map.json` maps each probe back to its file, line and function.
2. **run**: each suite runs on the copy with
   `godot --headless --audio-driver Dummy --path OUT/project --script res://<suite>`,
   at idle priority (`nice -n 19 ionice -c 3`), several at a time. When its scene
   tree exits, a suite writes its counters to `OUT/hits/`.
3. **report**: the hit files are merged with the map into text, JSON and HTML
   reports.

A suite is a script that extends `SceneTree` and is run with
`--script`; by default every `tests/test_*.gd`. The original project is never
modified.

Measured: statements of `func` bodies, property `get`/`set` bodies, one-line bodies
(`func f(): return 1`, `else: x`, `match` patterns), lambdas declared as statements.
Not measured: class-level initialisers, and the statements of a multi-line lambda
written inside brackets (`connect(func(): ...)`), which count as their enclosing line.

## Requirements

- Linux, Python 3.14, [uv](https://docs.astral.sh/uv/), `rsync`;
- a Godot 4 binary: `-g/--godot`, else `godot` on `PATH`, else the newest
  `~/godot/Godot_v4*-stable_linux.x86_64`;
- for Rust: `cargo install cargo-llvm-cov rustfilt`,
  `rustup component add llvm-tools-preview` for the crate's toolchain, and a systemd
  user session (the memory cap below).

## Install

```sh
uv tool install git+https://github.com/olivierpons/hqf-godot-coverage
```

This installs the `gdcov` and `gdcov-rustfuncs` commands. From a clone:
`uv sync`, then `uv run gdcov --help`.

## GDScript usage

```sh
# Instrument, run every tests/test_*.gd 4 at a time, write the reports.
gdcov all -p /path/to/project -o /path/to/run -j 4

# Other test layout, test helpers and addons left out of the measure.
gdcov all -p . -o /path/to/run -T 'test/**/*_test.gd' -e 'test/*' -e 'addons/*'

# Skip slow suites; take each suite's summary from a line of its output.
gdcov all -p . -o /path/to/run -s '*_live.gd' -m '\d+ passed, \d+ failed'

# One step at a time: instrument once, rerun one suite, rebuild the report.
gdcov instrument -p . -o /path/to/run
gdcov run -o /path/to/run -u tests/test_player.gd
gdcov report -p . -o /path/to/run -d 2
```

| Option | Meaning |
| --- | --- |
| `-p, --project DIR` | project to measure (default: current directory) |
| `-o, --out DIR` | run directory, created (required) |
| `-e, --exclude GLOB` | script not to instrument, project-relative (default: `tests/*`) |
| `-T, --tests GLOB` | suites to run, project-relative, `**` recurses (default: `tests/test_*.gd`) |
| `-s, --skip GLOB` | suite not to run, project-relative |
| `-u, --suite PATH` | run only this suite (overrides `--tests` and `--skip`) |
| `-g, --godot PATH` | Godot binary |
| `-j, --jobs N` | suites run at once (default: 2) |
| `-t, --timeout S` | seconds before a suite is killed (default: 1800) |
| `-m, --summary REGEX` | a suite's summary: last match of REGEX in its output (default: its last non-blank line) |
| `-d, --depth N` | directory levels of a report area (default: 1) |

`-e`, `-s` and `-u` are repeatable. `gdcov all` empties `OUT/hits` first; `run`
alone keeps earlier hits, so several runs add up. Exit code: 0, or 1 when a suite
failed or timed out (the report is written anyway).

### Output files

| File | Content |
| --- | --- |
| `OUT/summary.txt` | total, per area, per file, then the functions never executed, largest first, and the suites with their exit code, duration and summary |
| `OUT/coverage.json` | the same numbers, machine-readable |
| `OUT/html/index.html` | areas and files, one page per script with each line marked hit (with its count), missed or not measured |
| `OUT/suites.json` | one record per suite run |
| `OUT/logs/` | output of each suite |
| `OUT/project/`, `OUT/hits/`, `OUT/coverage_map.json` | instrumented copy, raw counters, probe map |

## Rust usage

```sh
zsh rust_cov.zsh /path/to/crate /path/to/rust_run
zsh rust_cov.zsh /path/to/crate /path/to/rust_run --features foo
```

Arguments after the output directory go to the test run. The script writes, under
the output directory: `summary.txt` (per file), `missing_lines.txt`,
`html/index.html`, `coverage.json`, `lcov.info`, and `never_executed.txt`: the
functions of the crate whose every monomorphised instance has a zero count, longest
first, names demangled. `gdcov-rustfuncs -j coverage.json -r /path/to/crate` prints
that list again from an export.

Every cargo call runs at idle priority inside a systemd user scope capped at 3 GB of
memory with no swap (`systemd-run --user --scope -p MemoryMax=3G -p MemorySwapMax=0`),
and the build uses `-j 1`: an instrumented build of a large crate otherwise takes every
core and enough memory to freeze a desktop. A cargo call over the cap is killed and the
script stops; edit `capped` in the script to raise it.

## Limits

- Line coverage only: no branch or condition coverage for GDScript.
- The GDScript scanner is line-based, not a full parser: several statements joined by
  `;` on one line count as one line.
- Hits are written when a suite's scene tree exits: a suite that crashes or hits the
  timeout loses its hits for that run.
- The exit hook is set by the first probe that runs once the tree has a root: a
  suite that does all its work in `_init()` and quits there writes no hits; use
  `_initialize()` or `_process()`.
- Only scripts run by the suites count; scenes opened by the editor or exported
  builds are not measured.
- For godot-rust crates, only code reached by `cargo test` is measured: tests that
  need a running Godot engine are not part of it.
- Linux only (`rsync`, `nice`, `ionice`, `systemd-run`).

## Quality

Checked by the CI badge above, once a day and on demand: `pytest`, `mypy --strict`,
`black --check` and `isort --check` on Python 3.14. Locally:

```sh
uv run pytest && uv run mypy && uv run black --check . && uv run isort --check .
```

## License

MIT, see [LICENSE](LICENSE).
