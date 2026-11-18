# hqf-godot-coverage

[![CI](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml/badge.svg)](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776ab.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Godot 4](https://img.shields.io/badge/Godot-4-478cbf.svg?logo=godotengine&logoColor=white)](https://godotengine.org/)

🇬🇧 [English](README.md) · 🇫🇷 [Français](README.fr.md) · 🇨🇳 [简体中文](README.zh-CN.md) · 🇮🇳 [हिन्दी](README.hi.md) · 🇪🇸 [Español](README.es.md) · 🇸🇦 [العربية](README.ar.md) · 🇧🇩 [বাংলা](README.bn.md) · 🇧🇷 [Português](README.pt-BR.md) · 🇮🇩 [Bahasa Indonesia](README.id.md) · 🇵🇰 [اردو](README.ur.md)

أداتان لقياس تغطية الشيفرة في ألعاب Godot 4:

- الأداة `gdcov`: تقيس تغطية الأسطر في شيفرة GDScript أثناء تشغيل مجموعات اختبار المشروع في وضع headless (بلا واجهة رسومية)؛
- السكربت `rust_cov.zsh`: يقيس تغطية الأسطر والمناطق (regions) في حزمة Rust (crate)، سواء كانت امتداد GDExtension مبنيًّا بـ[godot-rust](https://godot-rust.github.io/) أو أي حزمة أخرى، عند تشغيل `cargo test`، ويعطي قائمة الدوال التي لم يشغّلها أي اختبار قط.

## آلية عمل gdcov

1. مرحلة **instrument**: يُنسخ المشروع إلى `OUT/project` بواسطة rsync، مع استبعاد `.git` ومجلدات `target` الخاصة بـCargo و`mutants.out*` و`__pycache__`. وفي كل ملف `.gd` من النسخة، ما عدا الملفات المستبعدة، يُكتب استدعاء مِجَسّ (probe) على السطر نفسه الذي تقع فيه كل تعليمة من جسم الدالة، فلا تتغيّر أرقام الأسطر، ولا تتغيّر معها رسائل الأخطاء. تَعُدّ المجسّات مرات التنفيذ في عدّادات ثابتة (static) داخل `res://__gdcov/rt.gd`، ويربط الملف `OUT/coverage_map.json` كل مجسّ بملفه وسطره ودالته.
2. مرحلة **run**: تُشغَّل كل مجموعة اختبار على النسخة بالأمر `godot --headless --audio-driver Dummy --path OUT/project --script res://<suite>`، بأدنى أولوية (`nice -n 19 ionice -c 3`، انظر أدناه)، وتعمل عدة مجموعات في آنٍ واحد. وعندما تنتهي شجرة المشهد (scene tree) الخاصة بمجموعة ما، تكتب المجموعة عدّاداتها في `OUT/hits/`.
3. مرحلة **report**: تُدمج ملفات مرات التنفيذ مع خريطة المجسّات لإنتاج تقارير بصيغة نصية وبصيغتَي JSON وHTML.

مجموعة الاختبار سكربت يرث من `SceneTree` ويُشغَّل بالخيار `--script`؛ والمجموعات الافتراضية هي كل ملفات `tests/test_*.gd`. ولا يُعدَّل المشروع الأصلي أبدًا.

ما يُقاس: تعليمات أجسام الدوال `func`، وأجسام `get`/`set` في الخصائص، والأجسام المكتوبة على سطر واحد (`func f(): return 1` و`else: x` وأنماط `match`)، ودوال lambda المعرَّفة بوصفها تعليمات مستقلة. ما لا يُقاس: المُهيِّئات على مستوى الصنف، وتعليمات دالة lambda متعددة الأسطر المكتوبة داخل أقواس (`connect(func(): ...)`)، إذ تُحسب ضمن السطر الذي يحتويها.

## المتطلبات

- نظام Linux، وPython 3.14، و[uv](https://docs.astral.sh/uv/)، و`rsync`؛
- برنامج Godot 4 التنفيذي: المحدَّد بالخيار `-g/--godot`، وإلا فالأمر `godot` الموجود في `PATH`، وإلا فأحدث نسخة من `~/godot/Godot_v4*-stable_linux.x86_64`؛
- لـRust: الأمر `cargo install cargo-llvm-cov rustfilt`، والأمر `rustup component add llvm-tools-preview` لسلسلة الأدوات (toolchain) التي تستخدمها الحزمة، وجلسة مستخدم systemd (لازمة لحدّ الذاكرة الموضَّح أدناه).

## التثبيت

```sh
uv tool install git+https://github.com/olivierpons/hqf-godot-coverage
```

يثبّت هذا الأمر الأداتين `gdcov` و`gdcov-rustfuncs`. ومن نسخة محلية (clone) من المستودع: نفّذ `uv sync`، ثم `uv run gdcov --help`.

## استخدام GDScript

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

| الخيار | المعنى |
| --- | --- |
| `-p, --project DIR` | المشروع المراد قياسه (الافتراضي: المجلد الحالي) |
| `-o, --out DIR` | مجلد التشغيل، يُنشأ تلقائيًّا (إلزامي) |
| `-e, --exclude GLOB` | سكربت لا تُضاف إليه مجسّات، بمسار نسبي إلى المشروع (الافتراضي: `tests/*`) |
| `-T, --tests GLOB` | مجموعات الاختبار المراد تشغيلها، بمسار نسبي إلى المشروع، والنمط `**` يشمل المجلدات الفرعية (الافتراضي: `tests/test_*.gd`) |
| `-s, --skip GLOB` | مجموعة اختبار لا تُشغَّل، بمسار نسبي إلى المشروع |
| `-u, --suite PATH` | تشغيل هذه المجموعة وحدها (يُلغي أثر `--tests` و`--skip`) |
| `-g, --godot PATH` | برنامج Godot التنفيذي |
| `-j, --jobs N` | عدد المجموعات التي تعمل في آنٍ واحد (الافتراضي: 2) |
| `-t, --timeout S` | عدد الثواني قبل إيقاف المجموعة قسرًا (الافتراضي: 1800) |
| `-N, --no-nice` | تشغيل المجموعات بالأولوية العادية بدلًا من `nice -n 19 ionice -c 3` (انظر أدناه القسم الخاص بالتشغيل بأدنى أولوية) |
| `-m, --summary REGEX` | ملخص المجموعة: آخر تطابق للتعبير REGEX في مخرجاتها (الافتراضي: آخر سطر غير فارغ فيها) |
| `-d, --depth N` | عدد مستويات المجلدات في كل قسم من التقرير (الافتراضي: 1) |

يمكن تكرار الخيارات `-e` و`-s` و`-u`. يُفرغ الأمر `gdcov all` المجلد `OUT/hits` أولًا، أما `run` وحده فيحتفظ بمرات التنفيذ السابقة، فتتراكم نتائج عدة تشغيلات. رمز الخروج 0، أو 1 إذا فشلت إحدى المجموعات أو تجاوزت المهلة (ويُكتب التقرير في الحالتين).

### ملفات المخرجات

| الملف | المحتوى |
| --- | --- |
| `OUT/summary.txt` | الإجمالي، ثم النتائج حسب القسم وحسب الملف، ثم الدوال التي لم تُنفَّذ قط مرتبةً من الأكبر إلى الأصغر، ثم مجموعات الاختبار مع رمز خروج كل منها ومدتها وملخصها |
| `OUT/coverage.json` | الأرقام نفسها بصيغة قابلة للقراءة آليًّا |
| `OUT/html/index.html` | الأقسام والملفات، وصفحة لكل سكربت يُوسَم فيها كل سطر بأنه مُنفَّذ (مع عدد مرات تنفيذه) أو غير مُنفَّذ أو غير مَقيس |
| `OUT/suites.json` | سجل واحد لكل تشغيل لمجموعة اختبار |
| `OUT/logs/` | مخرجات كل مجموعة اختبار |
| `OUT/project/`, `OUT/hits/`, `OUT/coverage_map.json` | النسخة المزوَّدة بالمجسّات، والعدّادات الخام، وخريطة المجسّات |

## التشغيل بأدنى أولوية افتراضيًّا

تُشغِّل الأداتان عملياتهما بالأمر `nice -n 19 ionice -c 3`، أي بأدنى أولوية للمعالج وبفئة الإدخال والإخراج الخاملة (idle). فقياس التغطية يُبقي عدة عمليات Godot أو cargo مشغولة لدقائق، وكثيرًا ما يحدث ذلك وأنت تواصل العمل على الجهاز نفسه؛ وبأدنى أولوية لا تأخذ هذه العمليات من وقت المعالج ومن الوصول إلى القرص إلا ما لا يطلبه غيرها، فيبقى المحرر والمتصفح وسطح المكتب سريعة الاستجابة، وكل ما في الأمر أن التشغيل يطول حين يكون الجهاز مشغولًا. وفئة الإدخال والإخراج الخاملة لا تقل أهمية عن `nice`: فالكتابة الكثيفة على القرص وحدها قد تجمّد سطح المكتب، ولا سيما على قرص مشفَّر.

أما على جهاز لا عمل آخر له (مشغِّل CI أو خادم بناء)، فالتشغيل بأدنى أولوية لا يفعل سوى إبطاء القياس: عطّله بالخيار `-N` / `--no-nice` (`gdcov all -N ...` و`zsh rust_cov.zsh -N CRATE_DIR OUT_DIR`). وفي `rust_cov.zsh` يبقى حد الذاكرة والخيار `-j 1` مطبَّقَين في الحالتين.

## استخدام Rust

```sh
zsh rust_cov.zsh /path/to/crate /path/to/rust_run
zsh rust_cov.zsh /path/to/crate /path/to/rust_run --features foo
zsh rust_cov.zsh -N /path/to/crate /path/to/rust_run   # normal priority
```

تُمرَّر الوسائط الواقعة بعد مجلد المخرجات إلى تشغيل الاختبارات. ويكتب السكربت في مجلد المخرجات الملفات التالية: `summary.txt` (النتائج حسب الملف)، و`missing_lines.txt`، و`html/index.html`، و`coverage.json`، و`lcov.info`، و`never_executed.txt` الذي يضم دوال الحزمة التي بقي عدّاد كل نسخة مُولَّدة منها (monomorphised instance) صفرًا، مرتبةً من الأطول إلى الأقصر، بأسماء مفكوكة الترميز (demangled). ويعيد الأمر `gdcov-rustfuncs -j coverage.json -r /path/to/crate` طباعة هذه القائمة انطلاقًا من ملف مُصدَّر.

يعمل كل استدعاء لـcargo بأدنى أولوية (ما لم يُستخدم `-N`) داخل نطاق (scope) مستخدم systemd محدود بـ3 GB من الذاكرة دون swap (`systemd-run --user --scope -p MemoryMax=3G -p MemorySwapMax=0`)، ويستخدم البناء الخيار `-j 1`، لأن بناء حزمة كبيرة مزوَّدة بالمجسّات يستهلك بخلاف ذلك كل أنوية المعالج وذاكرةً تكفي لتجميد سطح المكتب. وإذا تجاوز استدعاء لـcargo هذا الحد أُنهي قسرًا وتوقّف السكربت؛ ولرفع الحد، عدّل `capped` في السكربت.

## القيود

- تغطية الأسطر فقط: لا تغطية للفروع ولا للشروط في GDScript.
- يقرأ الماسح شيفرة GDScript سطرًا سطرًا، وليس محلِّلًا (parser) كاملًا: فالتعليمات المتعددة المفصولة بـ`;` على سطر واحد تُحسب سطرًا واحدًا.
- تُكتب مرات التنفيذ عند انتهاء شجرة المشهد الخاصة بالمجموعة: فالمجموعة التي تنهار أو تبلغ المهلة تفقد مرات تنفيذها في ذلك التشغيل.
- يُضبط خطّاف الخروج (exit hook) عند تنفيذ أول مجسّ بعد أن يصبح للشجرة جذر: فالمجموعة التي تؤدي كل عملها في `_init()` وتنتهي هناك لا تكتب شيئًا؛ استخدم `_initialize()` أو `_process()` بدلًا منها.
- لا تُحسب إلا السكربتات التي تشغّلها مجموعات الاختبار؛ أما المشاهد التي يفتحها المحرر والنسخ المُصدَّرة من اللعبة فلا تُقاس.
- في حزم godot-rust، لا يُقاس إلا ما يبلغه `cargo test` من الشيفرة: فالاختبارات التي تحتاج إلى محرك Godot قيد التشغيل ليست جزءًا منه.
- يعمل على Linux فقط (`rsync` و`nice` و`ionice` و`systemd-run`).

## الجودة

تُجرى الفحوص التالية، التي تعرض شارة CI أعلاه نتيجتها، مرة يوميًّا وعند الطلب: `pytest` و`mypy --strict` و`black --check` و`isort --check` على Python 3.14. ومحليًّا:

```sh
uv run pytest && uv run mypy && uv run black --check . && uv run isort --check .
```

## الترخيص

الترخيص MIT، انظر [LICENSE](LICENSE).
