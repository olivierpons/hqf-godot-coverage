"""Runs the headless test suites of an instrumented copy, several at a time.

Every suite runs as ``nice -n 19 ionice -c 3 <godot> --headless --audio-driver Dummy
--path <copy> --script res://<suite>`` with ``GDCOV_OUT`` naming the hits directory;
``<suite>`` is the script path relative to the project, and the output goes to
``logs/<suite with / replaced by __>.log``.
"""

import fnmatch
import json
import logging
import os
import re
import shutil
import subprocess
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TESTS: str = "tests/test_*.gd"
TIMEOUT_RC: int = -1


@dataclass(frozen=True)
class SuiteResult:
    """Outcome of one suite run.

    Attributes:
        suite: Script path relative to the project.
        returncode: Process exit code; [constant TIMEOUT_RC] when it was killed.
        summary: See [func summary_line].
        seconds: Wall-clock duration.
    """

    suite: str
    returncode: int
    summary: str
    seconds: float


def find_godot(home: Path) -> Path:
    """``godot`` on ``PATH``, else the newest ``~/godot/Godot_v4*-stable_linux.x86_64``
    by version number.

    Raises:
        FileNotFoundError: No such binary.
    """
    on_path = shutil.which("godot")
    if on_path is not None:
        return Path(on_path)
    candidates = list((home / "godot").glob("Godot_v4*-stable_linux.x86_64"))
    if not candidates:
        raise FileNotFoundError(
            f"no godot on PATH and no Godot 4 binary under {home / 'godot'}"
        )

    def version(path: Path) -> tuple[int, ...]:
        found = re.search(r"_v([\d.]+)-", path.name)
        assert found is not None
        return tuple(int(part) for part in found.group(1).split("."))

    return max(candidates, key=version)


def find_suites(copy: Path, tests: str, skips: Iterable[str]) -> list[str]:
    """Suites of [param copy]: scripts matching the [param tests] glob that extend
    ``SceneTree``, minus the [param skips] ``fnmatch`` patterns.

    Both patterns apply to the path relative to [param copy]; ``**`` in [param tests]
    recurses, ``*`` in a skip pattern also matches ``/``. Sorted by path.
    """
    patterns = tuple(skips)
    suites: list[str] = []
    for path in sorted(copy.glob(tests)):
        relative = path.relative_to(copy).as_posix()
        if any(fnmatch.fnmatch(relative, p) for p in patterns):
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"^extends SceneTree\b", text, re.M):
            suites.append(relative)
    return suites


def summary_line(output: str, pattern: re.Pattern[str] | None) -> str:
    """Last match of [param pattern] in [param output], or its last non-blank line
    when [param pattern] is None; "" when nothing is found."""
    if pattern is None:
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        return lines[-1] if lines else ""
    found = [match.group(0) for match in pattern.finditer(output)]
    return found[-1] if found else ""


def log_name(suite: str) -> str:
    """File name of a suite's log under ``logs/``."""
    return suite.replace("/", "__") + ".log"


def suite_command(godot: Path, copy: Path, suite: str) -> list[str]:
    """Command line running [param suite] of [param copy] at idle priority."""
    return [
        "nice",
        "-n",
        "19",
        "ionice",
        "-c",
        "3",
        str(godot),
        "--headless",
        "--audio-driver",
        "Dummy",
        "--path",
        str(copy),
        "--script",
        f"res://{suite}",
    ]


def run_suite(
    godot: Path,
    copy: Path,
    suite: str,
    out: Path,
    timeout: float,
    summary: re.Pattern[str] | None,
) -> SuiteResult:
    """Runs one suite; its hits land in ``out/hits``, its output in ``out/logs``.

    Args:
        summary: Passed to [func summary_line].
    """
    env = dict(os.environ, GDCOV_OUT=str(out / "hits"))
    log = out / "logs" / log_name(suite)
    start = time.monotonic()
    with log.open("w", encoding="utf-8") as sink:
        try:
            done = subprocess.run(
                suite_command(godot, copy, suite),
                stdout=sink,
                stderr=subprocess.STDOUT,
                env=env,
                timeout=timeout,
            )
            returncode = done.returncode
        except subprocess.TimeoutExpired:
            returncode = TIMEOUT_RC
    seconds = time.monotonic() - start
    text = summary_line(log.read_text(encoding="utf-8", errors="replace"), summary)
    logger.info("%s rc=%d %.0fs %s", suite, returncode, seconds, text)
    return SuiteResult(suite, returncode, text, round(seconds, 1))


def run_suites(
    godot: Path,
    copy: Path,
    out: Path,
    suites: list[str],
    jobs: int,
    timeout: float,
    summary: re.Pattern[str] | None,
) -> list[SuiteResult]:
    """Runs [param suites] [param jobs] at a time; writes ``out/suites.json``."""
    (out / "hits").mkdir(parents=True, exist_ok=True)
    (out / "logs").mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(
            pool.map(lambda s: run_suite(godot, copy, s, out, timeout, summary), suites)
        )
    (out / "suites.json").write_text(
        json.dumps([asdict(r) for r in results], indent=1), encoding="utf-8"
    )
    return results
