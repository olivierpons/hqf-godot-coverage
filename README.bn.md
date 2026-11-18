# hqf-godot-coverage

[![CI](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml/badge.svg)](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776ab.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Godot 4](https://img.shields.io/badge/Godot-4-478cbf.svg?logo=godotengine&logoColor=white)](https://godotengine.org/)

🇬🇧 [English](README.md) · 🇫🇷 [Français](README.fr.md) · 🇨🇳 [简体中文](README.zh-CN.md) · 🇮🇳 [हिन्दी](README.hi.md) · 🇪🇸 [Español](README.es.md) · 🇸🇦 [العربية](README.ar.md) · 🇧🇩 [বাংলা](README.bn.md) · 🇧🇷 [Português](README.pt-BR.md) · 🇮🇩 [Bahasa Indonesia](README.id.md) · 🇵🇰 [اردو](README.ur.md)

Godot 4 গেমের জন্য কোড কভারেজ:

- `gdcov`: প্রজেক্টের headless টেস্ট স্যুট চলার সময় GDScript-এর লাইন কভারেজ মাপে;
- `rust_cov.zsh`: `cargo test` চলার সময় কোনো Rust crate-এর লাইন ও রিজিয়ন কভারেজ মাপে (সেটি [godot-rust](https://godot-rust.github.io/) GDExtension হোক বা অন্য যেকোনো crate), সঙ্গে সেই ফাংশনগুলোর তালিকাও দেয় যেগুলো কোনো টেস্ট কখনো চালায়নি।

## gdcov কীভাবে কাজ করে

1. **instrument**: প্রজেক্টটি `OUT/project`-এ কপি করা হয় (rsync দিয়ে, `.git`, Cargo-র `target` ডিরেক্টরি, `mutants.out*` আর `__pycache__` বাদ দিয়ে)। কপির প্রতিটি `.gd` ফাইলে (বাদ দেওয়া ফাইলগুলো ছাড়া) ফাংশন বডির প্রতিটি স্টেটমেন্টের লাইনেই একটি প্রোব কল লেখা হয়, ফলে লাইন নম্বর সরে না এবং এরর মেসেজও সঠিক লাইন দেখায়। প্রোবগুলো `res://__gdcov/rt.gd`-এর স্ট্যাটিক কাউন্টারে হিট গোনে। `OUT/coverage_map.json` প্রতিটি প্রোবকে তার ফাইল, লাইন ও ফাংশনের সঙ্গে মেলায়।
2. **run**: প্রতিটি স্যুট কপির ওপর `godot --headless --audio-driver Dummy --path OUT/project --script res://<suite>` দিয়ে চলে, idle প্রায়োরিটিতে (`nice -n 19 ionice -c 3`, নিচে দেখুন), একসঙ্গে কয়েকটি করে। কোনো স্যুটের সিন ট্রি বন্ধ হলে সেটি তার কাউন্টারগুলো `OUT/hits/`-এ লিখে দেয়।
3. **report**: হিট ফাইলগুলো প্রোব ম্যাপের সঙ্গে মিলিয়ে টেক্সট, JSON আর HTML রিপোর্ট তৈরি করা হয়।

স্যুট হলো এমন একটি স্ক্রিপ্ট যা `SceneTree` extend করে এবং `--script` দিয়ে চালানো হয়; ডিফল্টভাবে প্রতিটি `tests/test_*.gd` একটি স্যুট। মূল প্রজেক্টে কখনো কোনো পরিবর্তন করা হয় না।

যা মাপা হয়: `func` বডির স্টেটমেন্ট, প্রপার্টির `get`/`set` বডি, এক লাইনের বডি (`func f(): return 1`, `else: x`, `match` প্যাটার্ন), আর স্টেটমেন্ট হিসেবে লেখা ল্যাম্বডা।
যা মাপা হয় না: ক্লাস-স্তরের ইনিশিয়ালাইজার, এবং ব্র্যাকেটের ভেতরে লেখা একাধিক লাইনের ল্যাম্বডার (`connect(func(): ...)`) স্টেটমেন্ট; এগুলো যে লাইনের ভেতরে লেখা, সেই লাইনের হিসেবেই গোনা হয়।

## যা যা লাগবে

- Linux, Python 3.14, [uv](https://docs.astral.sh/uv/), `rsync`;
- একটি Godot 4 বাইনারি: `-g/--godot`, তা না থাকলে `PATH`-এ থাকা `godot`, তাও না থাকলে সবচেয়ে নতুন `~/godot/Godot_v4*-stable_linux.x86_64`;
- Rust-এর জন্য: `cargo install cargo-llvm-cov rustfilt`, crate-এর toolchain-এর জন্য `rustup component add llvm-tools-preview`, আর একটি systemd ইউজার সেশন (নিচে বলা মেমরি সীমার জন্য)।

## ইনস্টল

```sh
uv tool install git+https://github.com/olivierpons/hqf-godot-coverage
```

এতে `gdcov` আর `gdcov-rustfuncs` কমান্ড দুটি ইনস্টল হয়। ক্লোন থেকে চালাতে: আগে `uv sync`, তারপর `uv run gdcov --help`।

## GDScript-এর জন্য ব্যবহার

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

| অপশন | অর্থ |
| --- | --- |
| `-p, --project DIR` | যে প্রজেক্ট মাপা হবে (ডিফল্ট: বর্তমান ডিরেক্টরি) |
| `-o, --out DIR` | রান ডিরেক্টরি, যা তৈরি করে নেওয়া হয় (আবশ্যক) |
| `-e, --exclude GLOB` | যে স্ক্রিপ্ট ইনস্ট্রুমেন্ট করা হবে না, প্রজেক্টের সাপেক্ষে পাথ (ডিফল্ট: `tests/*`) |
| `-T, --tests GLOB` | যে স্যুটগুলো চালানো হবে, প্রজেক্টের সাপেক্ষে পাথ, `**` সাব-ডিরেক্টরিতেও খোঁজে (ডিফল্ট: `tests/test_*.gd`) |
| `-s, --skip GLOB` | যে স্যুট চালানো হবে না, প্রজেক্টের সাপেক্ষে পাথ |
| `-u, --suite PATH` | শুধু এই স্যুটটি চালায় (`--tests` ও `--skip`-কে ওভাররাইড করে) |
| `-g, --godot PATH` | Godot বাইনারি |
| `-j, --jobs N` | একসঙ্গে কয়টি স্যুট চলবে (ডিফল্ট: 2) |
| `-t, --timeout S` | কত সেকেন্ড পর স্যুট বন্ধ করে দেওয়া হবে (ডিফল্ট: 1800) |
| `-N, --no-nice` | স্যুটগুলো `nice -n 19 ionice -c 3`-এর বদলে সাধারণ প্রায়োরিটিতে চালায় (নিচে idle প্রায়োরিটির অংশটি দেখুন) |
| `-m, --summary REGEX` | স্যুটের সারাংশ: তার আউটপুটে REGEX-এর শেষ মিল (ডিফল্ট: আউটপুটের শেষ অ-ফাঁকা লাইন) |
| `-d, --depth N` | রিপোর্টের একটি এরিয়ায় ডিরেক্টরির কয়টি স্তর থাকবে (ডিফল্ট: 1) |

`-e`, `-s` আর `-u` একাধিকবার দেওয়া যায়। `gdcov all` প্রথমে `OUT/hits` খালি করে; শুধু `run` চালালে আগের হিটগুলো থেকে যায়, তাই কয়েকটি রানের ফল যোগ হতে থাকে। এক্সিট কোড: 0, অথবা কোনো স্যুট ফেল করলে বা টাইমআউট হলে 1 (রিপোর্ট তবুও লেখা হয়)।

### আউটপুট ফাইল

| ফাইল | বিষয়বস্তু |
| --- | --- |
| `OUT/summary.txt` | মোট, প্রতিটি এরিয়া ও প্রতিটি ফাইলের কভারেজ, তারপর কখনো না চলা ফাংশনগুলো (সবচেয়ে বড়টি আগে), এবং প্রতিটি স্যুটের এক্সিট কোড, সময়কাল ও সারাংশ |
| `OUT/coverage.json` | একই সংখ্যাগুলো, মেশিনে পড়ার উপযোগী রূপে |
| `OUT/html/index.html` | এরিয়া ও ফাইলের তালিকা, প্রতিটি স্ক্রিপ্টের জন্য একটি পেজ, যেখানে প্রতিটি লাইন হিট (হিটের সংখ্যাসহ), মিস বা মাপা হয়নি হিসেবে চিহ্নিত |
| `OUT/suites.json` | প্রতিটি স্যুট রানের একটি রেকর্ড |
| `OUT/logs/` | প্রতিটি স্যুটের আউটপুট |
| `OUT/project/`, `OUT/hits/`, `OUT/coverage_map.json` | ইনস্ট্রুমেন্ট করা কপি, কাঁচা কাউন্টার, প্রোব ম্যাপ |

## ডিফল্টভাবে idle প্রায়োরিটি

দুটি টুলই তাদের প্রসেসগুলো `nice -n 19 ionice -c 3` দিয়ে চালু করে: সবচেয়ে কম CPU প্রায়োরিটি আর idle I/O ক্লাস। একটি কভারেজ রান কয়েক মিনিট ধরে Godot বা cargo-র কয়েকটি প্রসেসকে ব্যস্ত রাখে, আর প্রায়ই সেই সময়ে আপনি একই মেশিনে কাজ চালিয়ে যান; idle প্রায়োরিটিতে এই প্রসেসগুলো শুধু সেটুকু CPU সময় আর ডিস্ক অ্যাক্সেস নেয় যা অন্য কেউ চাইছে না, তাই এডিটর, ব্রাউজার আর ডেস্কটপ দ্রুত সাড়া দিতে থাকে, আর মেশিন ব্যস্ত থাকলে রান শুধু একটু বেশি সময় নেয়। I/O-র idle ক্লাসও `nice`-এর মতোই গুরুত্বপূর্ণ: শুধু ডিস্কে ভারী লেখালেখিই ডেস্কটপ ফ্রিজ করে দিতে পারে, বিশেষ করে এনক্রিপ্ট করা ডিস্কে।

যে মেশিনে আর কোনো কাজ নেই (CI রানার, বিল্ড সার্ভার), সেখানে কম প্রায়োরিটি শুধু রানকে ধীর করে: `-N` / `--no-nice` দিয়ে এটি বন্ধ করুন (`gdcov all -N ...`, `zsh rust_cov.zsh -N CRATE_DIR OUT_DIR`)। `rust_cov.zsh`-এ মেমরি সীমা আর `-j 1` দুই ক্ষেত্রেই বহাল থাকে।

## Rust-এর জন্য ব্যবহার

```sh
zsh rust_cov.zsh /path/to/crate /path/to/rust_run
zsh rust_cov.zsh /path/to/crate /path/to/rust_run --features foo
zsh rust_cov.zsh -N /path/to/crate /path/to/rust_run   # normal priority
```

আউটপুট ডিরেক্টরির পরে দেওয়া আর্গুমেন্টগুলো টেস্ট রানে পাঠানো হয়। স্ক্রিপ্টটি আউটপুট ডিরেক্টরিতে এই ফাইলগুলো লেখে: `summary.txt` (ফাইলভিত্তিক), `missing_lines.txt`, `html/index.html`, `coverage.json`, `lcov.info`, এবং `never_executed.txt`। শেষ ফাইলটিতে থাকে crate-এর সেই ফাংশনগুলো যাদের প্রতিটি monomorphised ইনস্ট্যান্সের গণনা শূন্য, সবচেয়ে লম্বাটি আগে, নামগুলো demangle করা। `gdcov-rustfuncs -j coverage.json -r /path/to/crate` কোনো এক্সপোর্ট থেকে এই তালিকাটি আবার প্রিন্ট করে।

প্রতিটি cargo কল idle প্রায়োরিটিতে (`-N` না দিলে) একটি systemd ইউজার scope-এর ভেতরে চলে, যার মেমরি সীমা 3 GB এবং swap বন্ধ (`systemd-run --user --scope -p MemoryMax=3G -p MemorySwapMax=0`); বিল্ড চলে `-j 1` দিয়ে। তা না হলে বড় কোনো crate-এর ইনস্ট্রুমেন্টেড বিল্ড সব কোর দখল করে নেয় এবং এত মেমরি খায় যে ডেস্কটপ ফ্রিজ হয়ে যায়। সীমা পেরোনো cargo কল বন্ধ করে দেওয়া হয় এবং স্ক্রিপ্ট থেমে যায়; সীমা বাড়াতে চাইলে স্ক্রিপ্টে `capped` বদলান।

## সীমাবদ্ধতা

- শুধু লাইন কভারেজ: GDScript-এর জন্য ব্রাঞ্চ বা কন্ডিশন কভারেজ নেই।
- GDScript স্ক্যানার লাইনভিত্তিক, পূর্ণাঙ্গ পার্সার নয়: এক লাইনে `;` দিয়ে জোড়া একাধিক স্টেটমেন্ট একটি লাইন হিসেবেই গোনা হয়।
- স্যুটের সিন ট্রি বন্ধ হলে তবেই হিট লেখা হয়: যে স্যুট ক্র্যাশ করে বা টাইমআউটে পৌঁছায়, সেই রানের হিটগুলো হারিয়ে যায়।
- এক্সিট হুক সেট করে সেই প্রথম প্রোব, যা ট্রি-তে রুট আসার পরে চলে: যে স্যুট তার সব কাজ `_init()`-এ করে সেখানেই বন্ধ হয়ে যায়, সেটি কোনো হিট লেখে না; তার বদলে `_initialize()` বা `_process()` ব্যবহার করুন।
- শুধু স্যুটগুলো যে স্ক্রিপ্ট চালায়, সেগুলোই গোনা হয়; এডিটরে খোলা সিন বা এক্সপোর্ট করা বিল্ড মাপা হয় না।
- godot-rust crate-এর ক্ষেত্রে শুধু সেই কোডই মাপা হয় যেখানে `cargo test` পৌঁছায়: যে টেস্টগুলোর জন্য চালু Godot ইঞ্জিন দরকার, সেগুলো এর মধ্যে পড়ে না।
- শুধু Linux (`rsync`, `nice`, `ionice`, `systemd-run`)।

## গুণমান

ওপরের CI ব্যাজটি এই যাচাইগুলোর ফল দেখায়, যা দিনে একবার এবং প্রয়োজনমতো চলে: Python 3.14-এ `pytest`, `mypy --strict`, `black --check` আর `isort --check`। নিজের মেশিনে:

```sh
uv run pytest && uv run mypy && uv run black --check . && uv run isort --check .
```

## লাইসেন্স

MIT, দেখুন [LICENSE](LICENSE)।
