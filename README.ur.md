# hqf-godot-coverage

[![CI](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml/badge.svg)](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776ab.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Godot 4](https://img.shields.io/badge/Godot-4-478cbf.svg?logo=godotengine&logoColor=white)](https://godotengine.org/)

🇬🇧 [English](README.md) · 🇫🇷 [Français](README.fr.md) · 🇨🇳 [简体中文](README.zh-CN.md) · 🇮🇳 [हिन्दी](README.hi.md) · 🇪🇸 [Español](README.es.md) · 🇸🇦 [العربية](README.ar.md) · 🇧🇩 [বাংলা](README.bn.md) · 🇧🇷 [Português](README.pt-BR.md) · 🇮🇩 [Bahasa Indonesia](README.id.md) · 🇵🇰 [اردو](README.ur.md)

یہ دو ٹول Godot 4 گیمز کی کوڈ کوریج ناپتے ہیں:

- ٹول `gdcov`: GDScript کی لائن کوریج، جو پروجیکٹ کے headless ٹیسٹ سوئٹس چلنے کے دوران ناپی جاتی ہے؛
- اسکرپٹ `rust_cov.zsh`: کسی Rust crate کی لائن کوریج اور ریجن کوریج (چاہے وہ [godot-rust](https://godot-rust.github.io/) سے بنی GDExtension ہو یا کوئی اور crate)، جب `cargo test` چلتا ہے، اور ساتھ اُن فنکشنز کی فہرست جنہیں کسی ٹیسٹ نے کبھی نہیں چلایا۔

## ٹول gdcov کیسے کام کرتا ہے

1. مرحلہ **instrument**: پروجیکٹ کو rsync کے ذریعے `OUT/project` میں کاپی کیا جاتا ہے، اور `.git`، Cargo کی `target` ڈائریکٹریاں، `mutants.out*` اور `__pycache__` چھوڑ دی جاتی ہیں۔ کاپی کی ہر `.gd` فائل میں، سوائے خارج کی گئی فائلوں کے، فنکشن باڈی کے ہر اسٹیٹمنٹ کی لائن پر ہی ایک پروب (probe) کال لکھ دی جاتی ہے، تاکہ لائن نمبر (اور ایرر میسجز بھی) اپنی جگہ سے نہ ہلیں۔ پروبز ہر لائن کے چلنے کی گنتی (ہٹس) `res://__gdcov/rt.gd` کے static کاؤنٹرز میں رکھتے ہیں۔ فائل `OUT/coverage_map.json` ہر پروب کو اس کی فائل، لائن اور فنکشن سے جوڑتی ہے۔
2. مرحلہ **run**: ہر سوئٹ کاپی پر اس کمانڈ سے چلتا ہے: `godot --headless --audio-driver Dummy --path OUT/project --script res://<suite>`، کم ترین ترجیح (idle) پر (`nice -n 19 ionice -c 3`، تفصیل نیچے)، اور کئی سوئٹس ایک ساتھ چلتے ہیں۔ جب کسی سوئٹ کا scene tree ختم ہوتا ہے تو وہ اپنے کاؤنٹرز `OUT/hits/` میں لکھ دیتا ہے۔
3. مرحلہ **report**: ہٹس کی فائلوں کو پروب میپ کے ساتھ ملا کر ٹیکسٹ، JSON اور HTML رپورٹس بنائی جاتی ہیں۔

سوئٹ ایک ایسا اسکرپٹ ہے جو `SceneTree` کو extend کرتا ہے اور `--script` کے ساتھ چلایا جاتا ہے؛ ڈیفالٹ طور پر ہر `tests/test_*.gd` ایک سوئٹ ہے۔ اصل پروجیکٹ میں کبھی کوئی تبدیلی نہیں کی جاتی۔

کیا ناپا جاتا ہے: `func` باڈیز کے اسٹیٹمنٹس، پراپرٹیز کی `get`/`set` باڈیز، ایک لائن والی باڈیز (`func f(): return 1`، `else: x`، `match` کے پیٹرنز)، اور اسٹیٹمنٹ کے طور پر لکھے گئے lambdas۔ کیا نہیں ناپا جاتا: کلاس کی سطح پر initialisers، اور بریکٹس کے اندر لکھے گئے کئی لائنوں والے lambda کے اسٹیٹمنٹس (`connect(func(): ...)`)، جو اُس لائن میں شمار ہوتے ہیں جس کے اندر وہ لکھے ہیں۔

## ضروریات

- آپریٹنگ سسٹم Linux، Python 3.14، [uv](https://docs.astral.sh/uv/)، `rsync`؛
- ایک Godot 4 بائنری: `-g/--godot` سے دی گئی، ورنہ `PATH` میں موجود `godot`، ورنہ `~/godot/Godot_v4*-stable_linux.x86_64` کا سب سے نیا ورژن؛
- برائے Rust: `cargo install cargo-llvm-cov rustfilt`، crate کی toolchain کے لیے `rustup component add llvm-tools-preview`، اور systemd کا یوزر سیشن (نیچے بیان کی گئی میموری کی حد کے لیے)۔

## انسٹالیشن

```sh
uv tool install git+https://github.com/olivierpons/hqf-godot-coverage
```

اس سے `gdcov` اور `gdcov-rustfuncs` کمانڈز انسٹال ہو جاتی ہیں۔ ریپوزٹری کے clone سے: `uv sync`، پھر `uv run gdcov --help`۔

## استعمال: GDScript

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

| آپشن | مطلب |
| --- | --- |
| `-p, --project DIR` | جس پروجیکٹ کو ناپنا ہے (ڈیفالٹ: موجودہ ڈائریکٹری) |
| `-o, --out DIR` | رن ڈائریکٹری، خود بنا دی جاتی ہے (لازمی) |
| `-e, --exclude GLOB` | وہ اسکرپٹ جس میں پروبز نہیں ڈالے جائیں گے، پروجیکٹ سے relative پاتھ (ڈیفالٹ: `tests/*`) |
| `-T, --tests GLOB` | چلائے جانے والے سوئٹس، پروجیکٹ سے relative پاتھ، `**` ذیلی ڈائریکٹریوں میں بھی تلاش کرتا ہے (ڈیفالٹ: `tests/test_*.gd`) |
| `-s, --skip GLOB` | وہ سوئٹ جو نہیں چلایا جائے گا، پروجیکٹ سے relative پاتھ |
| `-u, --suite PATH` | صرف یہی سوئٹ چلائیں (`--tests` اور `--skip` کی جگہ لے لیتا ہے) |
| `-g, --godot PATH` | Godot بائنری |
| `-j, --jobs N` | ایک ساتھ چلنے والے سوئٹس کی تعداد (ڈیفالٹ: 2) |
| `-t, --timeout S` | سوئٹ کو زبردستی بند کرنے سے پہلے کتنے سیکنڈ (ڈیفالٹ: 1800) |
| `-N, --no-nice` | سوئٹس کو `nice -n 19 ionice -c 3` کے بجائے عام ترجیح پر چلائیں (نیچے کم ترین ترجیح والا حصہ دیکھیں) |
| `-m, --summary REGEX` | سوئٹ کا خلاصہ: اس کے آؤٹ پٹ میں REGEX کا آخری میچ (ڈیفالٹ: اس کی آخری غیر خالی لائن) |
| `-d, --depth N` | رپورٹ کے ہر حصے میں ڈائریکٹری کی کتنی سطحیں ہوں (ڈیفالٹ: 1) |

آپشنز `-e`، `-s` اور `-u` ایک سے زیادہ بار دیے جا سکتے ہیں۔ کمانڈ `gdcov all` پہلے `OUT/hits` کو خالی کرتی ہے؛ جبکہ اکیلی `run` پچھلے ہٹس برقرار رکھتی ہے، اس لیے کئی رنز کے ہٹس جمع ہوتے جاتے ہیں۔ ایگزٹ کوڈ: 0، یا 1 اگر کوئی سوئٹ ناکام ہو جائے یا ٹائم آؤٹ ہو جائے (رپورٹ پھر بھی لکھی جاتی ہے)۔

### آؤٹ پٹ فائلیں

| فائل | مواد |
| --- | --- |
| `OUT/summary.txt` | مجموعی کوریج، پھر ہر حصے اور ہر فائل کے حساب سے، پھر کبھی نہ چلنے والے فنکشنز (سب سے بڑے پہلے)، اور آخر میں سوئٹس، ہر ایک کے ایگزٹ کوڈ، دورانیے اور خلاصے کے ساتھ |
| `OUT/coverage.json` | یہی اعداد، مشین کے پڑھنے کے قابل شکل میں |
| `OUT/html/index.html` | حصے اور فائلیں، ہر اسکرپٹ کا ایک صفحہ جس میں ہر لائن پر نشان ہوتا ہے: چلی (گنتی کے ساتھ)، نہیں چلی، یا ناپی نہیں گئی |
| `OUT/suites.json` | ہر سوئٹ رن کا ایک ریکارڈ |
| `OUT/logs/` | ہر سوئٹ کا آؤٹ پٹ |
| `OUT/project/`, `OUT/hits/`, `OUT/coverage_map.json` | پروبز والی کاپی، خام کاؤنٹرز، پروب میپ |

## کم ترین ترجیح، ڈیفالٹ طور پر فعال

دونوں ٹول اپنے پروسیس `nice -n 19 ionice -c 3` کے ساتھ شروع کرتے ہیں، یعنی CPU کی کم ترین ترجیح اور I/O کی idle کلاس۔ کوریج کا ایک رن کئی منٹ تک Godot یا cargo کے کئی پروسیس مصروف رکھتا ہے، اور اکثر اسی دوران آپ اسی مشین پر کام بھی کر رہے ہوتے ہیں؛ کم ترین ترجیح پر یہ پروسیس CPU کا صرف وہی وقت اور ڈسک تک صرف وہی رسائی لیتے ہیں جو کوئی اور نہیں مانگ رہا، اس لیے ایڈیٹر، براؤزر اور ڈیسک ٹاپ فوراً ردِعمل دیتے رہتے ہیں، اور مشین مصروف ہو تو رن بس کچھ زیادہ وقت لے لیتا ہے۔ I/O کی idle کلاس بھی `nice` جتنی ہی اہم ہے: صرف ڈسک پر بھاری لکھائی بھی ڈیسک ٹاپ کو جام کر سکتی ہے، خاص طور پر encrypted ڈسک پر۔

جس مشین پر کوئی اور کام نہ ہو (CI رنر، build سرور)، وہاں کم ترین ترجیح صرف رن کو سست کرتی ہے: اسے `-N` / `--no-nice` سے بند کریں (`gdcov all -N ...`، `zsh rust_cov.zsh -N CRATE_DIR OUT_DIR`)۔ اسکرپٹ `rust_cov.zsh` میں میموری کی حد اور `-j 1` دونوں صورتوں میں برقرار رہتے ہیں۔

## استعمال: Rust

```sh
zsh rust_cov.zsh /path/to/crate /path/to/rust_run
zsh rust_cov.zsh /path/to/crate /path/to/rust_run --features foo
zsh rust_cov.zsh -N /path/to/crate /path/to/rust_run   # normal priority
```

آؤٹ پٹ ڈائریکٹری کے بعد دیے گئے آرگیومنٹس ٹیسٹ رن کو بھیج دیے جاتے ہیں۔ اسکرپٹ آؤٹ پٹ ڈائریکٹری میں یہ فائلیں لکھتا ہے: `summary.txt` (فائل کے حساب سے)، `missing_lines.txt`، `html/index.html`، `coverage.json`، `lcov.info`، اور `never_executed.txt`، جس میں crate کے وہ فنکشنز ہوتے ہیں جن کے ہر monomorphised instance کی گنتی صفر ہو، سب سے لمبے پہلے، اور نام demangle کیے ہوئے۔ کمانڈ `gdcov-rustfuncs -j coverage.json -r /path/to/crate` یہی فہرست ایکسپورٹ فائل سے دوبارہ پرنٹ کرتی ہے۔

ہر cargo کال کم ترین ترجیح پر (جب تک `-N` نہ دیا جائے) systemd کے ایک یوزر scope کے اندر چلتی ہے جس کی میموری 3 GB تک محدود ہے اور swap بند ہے (`systemd-run --user --scope -p MemoryMax=3G -p MemorySwapMax=0`)، اور build میں `-j 1` استعمال ہوتا ہے: ورنہ کسی بڑے crate کا پروبز والا build تمام cores اور اتنی میموری لے لیتا ہے کہ ڈیسک ٹاپ جام ہو جائے۔ جو cargo کال اس حد سے آگے جائے وہ ختم کر دی جاتی ہے اور اسکرپٹ رک جاتا ہے؛ حد بڑھانے کے لیے اسکرپٹ میں `capped` کو تبدیل کریں۔

## حدود

- صرف لائن کوریج: GDScript کے لیے نہ برانچ کوریج ہے نہ کنڈیشن کوریج۔
- اسکینر GDScript کو لائن بہ لائن پڑھتا ہے اور مکمل parser نہیں ہے: ایک لائن پر `;` سے جوڑے گئے کئی اسٹیٹمنٹس ایک ہی لائن شمار ہوتے ہیں۔
- ہٹس اُس وقت لکھے جاتے ہیں جب سوئٹ کا scene tree ختم ہوتا ہے: جو سوئٹ crash ہو جائے یا ٹائم آؤٹ تک پہنچ جائے، اُس رن کے اس کے ہٹس ضائع ہو جاتے ہیں۔
- ایگزٹ hook وہ پہلا پروب لگاتا ہے جو tree کا root بن جانے کے بعد چلتا ہے: جو سوئٹ اپنا سارا کام `_init()` میں کرے اور وہیں ختم ہو جائے، وہ کوئی ہٹ نہیں لکھتا؛ اس کے بجائے `_initialize()` یا `_process()` استعمال کریں۔
- صرف وہ اسکرپٹس شمار ہوتے ہیں جو سوئٹس چلاتے ہیں؛ ایڈیٹر میں کھولے گئے scenes اور ایکسپورٹ کیے گئے builds ناپے نہیں جاتے۔
- اگر crate کا تعلق godot-rust سے ہو تو صرف وہی کوڈ ناپا جاتا ہے جہاں تک `cargo test` پہنچتا ہے: جن ٹیسٹس کو چلتا ہوا Godot انجن درکار ہو، وہ اس میں شامل نہیں۔
- صرف Linux پر (`rsync`، `nice`، `ionice`، `systemd-run`)۔

## معیار

یہ چیکس روزانہ ایک بار اور ضرورت پڑنے پر CI میں چلتے ہیں، اور اوپر والا CI بیج ان کا نتیجہ دکھاتا ہے: Python 3.14 پر `pytest`، `mypy --strict`، `black --check` اور `isort --check`۔ مقامی طور پر:

```sh
uv run pytest && uv run mypy && uv run black --check . && uv run isort --check .
```

## لائسنس

لائسنس MIT ہے، دیکھیں [LICENSE](LICENSE)۔
