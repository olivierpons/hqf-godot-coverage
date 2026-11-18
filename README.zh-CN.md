# hqf-godot-coverage

[![CI](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml/badge.svg)](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776ab.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Godot 4](https://img.shields.io/badge/Godot-4-478cbf.svg?logo=godotengine&logoColor=white)](https://godotengine.org/)

🇬🇧 [English](README.md) · 🇫🇷 [Français](README.fr.md) · 🇨🇳 [简体中文](README.zh-CN.md) · 🇮🇳 [हिन्दी](README.hi.md) · 🇪🇸 [Español](README.es.md) · 🇸🇦 [العربية](README.ar.md) · 🇧🇩 [বাংলা](README.bn.md) · 🇧🇷 [Português](README.pt-BR.md) · 🇮🇩 [Bahasa Indonesia](README.id.md) · 🇵🇰 [اردو](README.ur.md)

面向 Godot 4 游戏的代码覆盖率工具：

- `gdcov`：在项目的 headless 测试套件运行期间，统计 GDScript 的行覆盖率；
- `rust_cov.zsh`：在 `cargo test` 下统计 Rust crate 的行覆盖率和区域覆盖率（[godot-rust](https://godot-rust.github.io/) GDExtension 或其他任意 crate 均可），并列出从未被任何测试执行过的函数。

## gdcov 的工作原理

1. **instrument**（插桩）：将项目复制到 `OUT/project`（使用 rsync，不包含 `.git`、Cargo 的 `target` 目录、`mutants.out*` 和 `__pycache__`）。在副本的每个 `.gd` 文件中（被排除的文件除外），探针调用与函数体中的每条语句写在同一行，因此行号不会偏移，错误信息中的行号也依然准确。探针把命中次数记录在 `res://__gdcov/rt.gd` 的静态计数器中。`OUT/coverage_map.json` 记录每个探针对应的文件、行号和函数。
2. **run**（运行）：每个套件都在副本上通过 `godot --headless --audio-driver Dummy --path OUT/project --script res://<suite>` 运行，以空闲优先级（`nice -n 19 ionice -c 3`，见下文）执行，多个套件并行。套件的场景树退出时，会把计数器写入 `OUT/hits/`。
3. **report**（报告）：将命中文件与探针映射表合并，生成文本、JSON 和 HTML 报告。

测试套件是一个继承 `SceneTree`、通过 `--script` 运行的脚本；默认为所有 `tests/test_*.gd`。原项目始终不会被修改。

统计范围：`func` 函数体中的语句、属性的 `get`/`set` 函数体、单行代码块（`func f(): return 1`、`else: x`、`match` 分支）、以语句形式声明的 lambda。
不统计：类级别的初始化语句，以及写在括号内的多行 lambda（`connect(func(): ...)`）中的语句，这些语句计入其所在的那一行。

## 环境要求

- Linux、Python 3.14、[uv](https://docs.astral.sh/uv/)、`rsync`；
- Godot 4 可执行文件：优先使用 `-g/--godot` 指定的路径，其次是 `PATH` 中的 `godot`，最后是版本最新的 `~/godot/Godot_v4*-stable_linux.x86_64`；
- Rust 覆盖率还需要：`cargo install cargo-llvm-cov rustfilt`，为该 crate 所用的 toolchain 执行 `rustup component add llvm-tools-preview`，以及一个 systemd 用户会话（用于下文所述的内存上限）。

## 安装

```sh
uv tool install git+https://github.com/olivierpons/hqf-godot-coverage
```

这会安装 `gdcov` 和 `gdcov-rustfuncs` 两个命令。从克隆的仓库使用：先执行 `uv sync`，再执行 `uv run gdcov --help`。

## GDScript 用法

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

| 选项 | 说明 |
| --- | --- |
| `-p, --project DIR` | 要统计的项目（默认：当前目录） |
| `-o, --out DIR` | 运行目录，会自动创建（必填） |
| `-e, --exclude GLOB` | 不插桩的脚本，路径相对于项目（默认：`tests/*`） |
| `-T, --tests GLOB` | 要运行的套件，路径相对于项目，`**` 表示递归匹配（默认：`tests/test_*.gd`） |
| `-s, --skip GLOB` | 不运行的套件，路径相对于项目 |
| `-u, --suite PATH` | 只运行此套件（覆盖 `--tests` 和 `--skip`） |
| `-g, --godot PATH` | Godot 可执行文件 |
| `-j, --jobs N` | 同时运行的套件数（默认：2） |
| `-t, --timeout S` | 超时秒数，超时后终止套件（默认：1800） |
| `-N, --no-nice` | 以正常优先级运行套件，不使用 `nice -n 19 ionice -c 3`（详见下文关于空闲优先级的一节） |
| `-m, --summary REGEX` | 套件的摘要：取其输出中 REGEX 的最后一个匹配（默认：输出的最后一个非空行） |
| `-d, --depth N` | 报告中每个分区包含的目录层级数（默认：1） |

`-e`、`-s` 和 `-u` 可重复指定。`gdcov all` 会先清空 `OUT/hits`；单独执行 `run` 则保留之前的命中数据，因此多次运行的结果会累加。退出码：正常为 0；若有套件失败或超时则为 1（报告仍会生成）。

### 输出文件

| 文件 | 内容 |
| --- | --- |
| `OUT/summary.txt` | 总计、各分区、各文件的覆盖率，然后是从未执行过的函数（按函数大小降序），以及各套件的退出码、耗时和摘要 |
| `OUT/coverage.json` | 同样的数据，机器可读格式 |
| `OUT/html/index.html` | 分区和文件列表，每个脚本一页，每一行都标注为已命中（附命中次数）、未命中或不统计 |
| `OUT/suites.json` | 每次套件运行对应一条记录 |
| `OUT/logs/` | 每个套件的输出 |
| `OUT/project/`, `OUT/hits/`, `OUT/coverage_map.json` | 插桩后的副本、原始计数器、探针映射表 |

## 默认以空闲优先级运行

两个工具都用 `nice -n 19 ionice -c 3` 启动各自的进程，即最低的 CPU 优先级和空闲（idle）I/O 类别。一次覆盖率运行会让多个 Godot 或 cargo 进程持续忙碌数分钟，而这期间往往还要在同一台机器上继续工作；在空闲优先级下，这些进程只占用其他程序不需要的 CPU 时间和磁盘访问，因此编辑器、浏览器和桌面都能保持流畅响应，只是机器繁忙时运行耗时更长。空闲 I/O 类别与 `nice` 同样重要：单是大量磁盘写入就可能让桌面卡死，在加密磁盘上尤其如此。

在没有其他任务的机器上（CI runner、构建服务器），低优先级只会拖慢运行，可用 `-N` / `--no-nice` 关闭（`gdcov all -N ...`、`zsh rust_cov.zsh -N CRATE_DIR OUT_DIR`）。对于 `rust_cov.zsh`，无论是否关闭，内存上限和 `-j 1` 都保持不变。

## Rust 用法

```sh
zsh rust_cov.zsh /path/to/crate /path/to/rust_run
zsh rust_cov.zsh /path/to/crate /path/to/rust_run --features foo
zsh rust_cov.zsh -N /path/to/crate /path/to/rust_run   # normal priority
```

输出目录之后的参数会传给测试运行。脚本在输出目录下生成：`summary.txt`（按文件统计）、`missing_lines.txt`、`html/index.html`、`coverage.json`、`lcov.info`，以及 `never_executed.txt`。最后这个文件列出 crate 中所有单态化实例计数均为零的函数，按函数长度降序排列，函数名已 demangle。`gdcov-rustfuncs -j coverage.json -r /path/to/crate` 可根据导出文件重新打印这份列表。

每次 cargo 调用都以空闲优先级（除非使用 `-N`）运行在一个 systemd 用户 scope 中，内存上限为 3 GB，且禁用 swap（`systemd-run --user --scope -p MemoryMax=3G -p MemorySwapMax=0`），构建时使用 `-j 1`。否则，对大型 crate 进行插桩构建会占满所有 CPU 核心，并消耗大量内存，足以让桌面卡死。超出上限的 cargo 调用会被终止，脚本随即停止；如需提高上限，请修改脚本中的 `capped`。

## 局限性

- 仅支持行覆盖率：GDScript 不支持分支覆盖率或条件覆盖率。
- GDScript 扫描器按行处理，并非完整的解析器：同一行中用 `;` 连接的多条语句只算作一行。
- 命中数据在套件的场景树退出时写入：崩溃或超时的套件会丢失该次运行的命中数据。
- 退出钩子由场景树拥有根节点后运行的第一个探针设置：如果套件在 `_init()` 中完成全部工作并直接退出，则不会写入任何命中数据；请改用 `_initialize()` 或 `_process()`。
- 只统计测试套件运行到的脚本；编辑器中打开的场景和导出的构建不在统计范围内。
- 对于 godot-rust crate，只统计 `cargo test` 能执行到的代码：需要运行中的 Godot 引擎的测试不在其中。
- 仅支持 Linux（`rsync`、`nice`、`ionice`、`systemd-run`）。

## 质量保证

上方 CI 徽章对应的流水线每天运行一次，也可手动触发，检查内容为：在 Python 3.14 上运行 `pytest`、`mypy --strict`、`black --check` 和 `isort --check`。在本地运行：

```sh
uv run pytest && uv run mypy && uv run black --check . && uv run isort --check .
```

## 许可证

MIT，详见 [LICENSE](LICENSE)。
