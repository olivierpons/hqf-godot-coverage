"""Lists the Rust functions an ``llvm-cov export`` JSON never saw running.

``cargo llvm-cov report --json`` keeps one record per monomorphised instance; the
records of one source function share their file and first region start. A function
counts as never executed when every one of its records has a zero count. Names are
demangled with ``rustfilt`` (``cargo install rustfilt``); generic hashes are dropped.

Output, one line per function, longest first: ``<lines>  <file>:<line>  <name>``.
"""

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RustFunction:
    """A source function with its execution count summed over instances."""

    file: str
    line: int
    lines: int
    mangled: str
    count: int


def merge_records(records: Iterable[Mapping[str, Any]]) -> list[RustFunction]:
    """One [RustFunction] per source function of llvm-cov ``functions`` records.

    Each record holds ``name``, ``count``, ``filenames`` and ``regions``; a region
    is ``[line_start, col_start, line_end, col_end, ...]``, the first one starting the
    function body; the function spans up to the last region end.
    """
    merged: dict[tuple[str, int, int], RustFunction] = {}
    for record in records:
        start, col = record["regions"][0][:2]
        end = max(region[2] for region in record["regions"])
        key = (record["filenames"][0], start, col)
        known = merged.get(key)
        lines = end - start + 1
        if known is not None:
            merged[key] = RustFunction(
                key[0],
                start,
                max(lines, known.lines),
                known.mangled,
                known.count + record["count"],
            )
        else:
            merged[key] = RustFunction(
                key[0], start, lines, record["name"], record["count"]
            )
    return list(merged.values())


def never_executed(functions: Iterable[RustFunction]) -> list[RustFunction]:
    """Functions with a zero count, longest first, then by file and line."""
    zero = [f for f in functions if f.count == 0]
    return sorted(zero, key=lambda f: (-f.lines, f.file, f.line))


def clean_name(demangled: str) -> str:
    """[param demangled] without crate hashes (``[1a2b3c]``, ``::h0123abcd``)."""
    without = re.sub(r"\[[0-9a-f]+\]", "", demangled)
    return re.sub(r"::h[0-9a-f]{16}$", "", without)


def demangle(names: Sequence[str]) -> list[str]:
    """Demangles [param names] in one ``rustfilt`` call; order kept."""
    if not names:
        return []
    done = subprocess.run(
        ["rustfilt"], input="\n".join(names), capture_output=True, text=True, check=True
    )
    return [clean_name(line) for line in done.stdout.splitlines()]


def relative(file: str, root: str) -> str:
    """[param file] relative to [param root] when inside it, else unchanged; an empty
    [param root] keeps every path as it is."""
    if not root:
        return file
    return file.removeprefix(root.rstrip("/") + "/")


def report_lines(export: Mapping[str, Any], root: str) -> list[str]:
    """Report lines for an llvm-cov JSON export.

    Only files under [param root] are listed (dependencies left out), relative to it.
    """
    records = export["data"][0]["functions"]
    inside = [
        r for r in records if r["filenames"][0].startswith(root.rstrip("/") + "/")
    ]
    functions = never_executed(merge_records(inside))
    names = demangle([f.mangled for f in functions])
    return [
        f"{f.lines:5d}  {relative(f.file, root)}:{f.line}  {name}"
        for f, name in zip(functions, names, strict=True)
    ]


def main(argv: Sequence[str] | None = None) -> int:
    """Prints the never-executed functions of an llvm-cov JSON export."""
    parser = argparse.ArgumentParser(
        prog="gdcov-rustfuncs",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: gdcov-rustfuncs -j coverage.json -r /repo/crate",
    )
    parser.add_argument(
        "-j", "--json", type=Path, required=True, help="llvm-cov export JSON file"
    )
    parser.add_argument(
        "-r",
        "--root",
        default="",
        help="crate directory: only its files are listed, relative to it "
        "(default: every file, absolute paths)",
    )
    args = parser.parse_args(argv)
    export = json.loads(args.json.read_text(encoding="utf-8"))
    print("\n".join(report_lines(export, args.root)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
