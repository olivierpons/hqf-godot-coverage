#!/bin/zsh
# Line and region coverage of a Rust crate under `cargo test` (all targets: unit,
# integration, bench and example harnesses), measured with cargo-llvm-cov.
# Usage: zsh rust_cov.zsh CRATE_DIR OUT_DIR [CARGO_ARG...]
# CARGO_ARG... go to the test run (e.g. --features foo, --workspace).
# Writes OUT_DIR/summary.txt (per file), missing_lines.txt, html/index.html,
# coverage.json, lcov.info and never_executed.txt (functions no test ran).
# Needs: cargo install cargo-llvm-cov rustfilt; rustup component add llvm-tools-preview
# for the crate's toolchain; a systemd user session for the memory cap; python3.14, or
# the interpreter named by $PYTHON, for never_executed.txt.
# Every cargo call runs at idle priority (nice 19, idle I/O class) inside a systemd
# user scope capped at 3 GB of memory without swap, and builds with -j 1: an
# instrumented build of a large crate otherwise takes every core and enough memory
# to freeze a desktop. A cargo call that exceeds the cap is killed and the script
# stops.
if [[ $1 == -h || $1 == --help || $# -lt 2 ]]; then
	sed -n '2,15p' ${0:A} | cut -c 3-
	[[ $1 == -h || $1 == --help ]]
	exit
fi
renice -n 19 -p $$ > /dev/null; ionice -c 3 -p $$
set -e
here=${0:A:h}
crate=${1:A}
out=${2:A}
extra=(${@[3,-1]})
capped=(systemd-run --user --scope -q -p MemoryMax=3G -p MemorySwapMax=0)
mkdir -p $out
cd $crate
$capped cargo llvm-cov --no-report --all-targets -j 1 $extra
$capped cargo llvm-cov report --summary-only > $out/summary.txt
$capped cargo llvm-cov report --show-missing-lines | sed -n '/Uncovered Lines/,$p' \
	> $out/missing_lines.txt
$capped cargo llvm-cov report --html --output-dir $out
$capped cargo llvm-cov report --json --output-path $out/coverage.json
$capped cargo llvm-cov report --lcov --output-path $out/lcov.info
PYTHONPATH=$here ${PYTHON:-python3.14} -m gdcov.rustfuncs -j $out/coverage.json \
	-r $crate > $out/never_executed.txt
tail -1 $out/summary.txt
