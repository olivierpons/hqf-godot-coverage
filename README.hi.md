# hqf-godot-coverage

[![CI](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml/badge.svg)](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776ab.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Godot 4](https://img.shields.io/badge/Godot-4-478cbf.svg?logo=godotengine&logoColor=white)](https://godotengine.org/)

🇬🇧 [English](README.md) · 🇫🇷 [Français](README.fr.md) · 🇨🇳 [简体中文](README.zh-CN.md) · 🇮🇳 [हिन्दी](README.hi.md) · 🇪🇸 [Español](README.es.md) · 🇸🇦 [العربية](README.ar.md) · 🇧🇩 [বাংলা](README.bn.md) · 🇧🇷 [Português](README.pt-BR.md) · 🇮🇩 [Bahasa Indonesia](README.id.md) · 🇵🇰 [اردو](README.ur.md)

Godot 4 गेम्स के लिए कोड कवरेज:

- `gdcov`: प्रोजेक्ट के headless टेस्ट सूट चलते समय GDScript का लाइन कवरेज मापता है;
- `rust_cov.zsh`: `cargo test` के दौरान किसी Rust crate का लाइन और रीजन कवरेज मापता है (चाहे वह [godot-rust](https://godot-rust.github.io/) GDExtension हो या कोई और crate), साथ ही उन फ़ंक्शन की सूची देता है जिन्हें किसी भी टेस्ट ने कभी नहीं चलाया।

## gdcov कैसे काम करता है

1. **instrument**: प्रोजेक्ट को `OUT/project` में कॉपी किया जाता है (rsync से, `.git`, Cargo की `target` डायरेक्टरी, `mutants.out*` और `__pycache__` को छोड़कर)। कॉपी की हर `.gd` फ़ाइल में (बाहर रखी गई फ़ाइलों को छोड़कर) फ़ंक्शन बॉडी के हर स्टेटमेंट वाली लाइन पर ही एक प्रोब कॉल लिखी जाती है, ताकि लाइन नंबर न खिसकें और एरर मैसेज भी सही लाइन बताते रहें। प्रोब हिट की गिनती `res://__gdcov/rt.gd` के स्टैटिक काउंटरों में रखते हैं। `OUT/coverage_map.json` हर प्रोब को उसकी फ़ाइल, लाइन और फ़ंक्शन से जोड़ता है।
2. **run**: हर सूट कॉपी पर `godot --headless --audio-driver Dummy --path OUT/project --script res://<suite>` से चलता है, idle प्राथमिकता पर (`nice -n 19 ionice -c 3`, नीचे देखें), और कई सूट एक साथ चलते हैं। जब किसी सूट का सीन ट्री बंद होता है, तो वह अपने काउंटर `OUT/hits/` में लिख देता है।
3. **report**: हिट फ़ाइलों को प्रोब मैप के साथ मिलाकर टेक्स्ट, JSON और HTML रिपोर्ट बनाई जाती हैं।

सूट एक ऐसी स्क्रिप्ट है जो `SceneTree` को extend करती है और `--script` से चलाई जाती है; डिफ़ॉल्ट रूप से हर `tests/test_*.gd` एक सूट है। मूल प्रोजेक्ट में कभी कोई बदलाव नहीं किया जाता।

मापे जाते हैं: `func` बॉडी के स्टेटमेंट, प्रॉपर्टी की `get`/`set` बॉडी, एक लाइन वाली बॉडी (`func f(): return 1`, `else: x`, `match` पैटर्न), और स्टेटमेंट के रूप में लिखे गए लैम्ब्डा।
नहीं मापे जाते: क्लास-स्तर के इनिशियलाइज़र, और ब्रैकेट के अंदर लिखे कई लाइनों वाले लैम्ब्डा (`connect(func(): ...)`) के स्टेटमेंट, जो उस लाइन में गिने जाते हैं जिसके अंदर वे लिखे हैं।

## ज़रूरतें

- Linux, Python 3.14, [uv](https://docs.astral.sh/uv/), `rsync`;
- Godot 4 का बाइनरी: `-g/--godot`, वरना `PATH` पर मौजूद `godot`, वरना सबसे नया `~/godot/Godot_v4*-stable_linux.x86_64`;
- Rust के लिए: `cargo install cargo-llvm-cov rustfilt`, crate के toolchain के लिए `rustup component add llvm-tools-preview`, और एक systemd यूज़र सेशन (नीचे बताई गई मेमोरी सीमा के लिए)।

## इंस्टॉलेशन

```sh
uv tool install git+https://github.com/olivierpons/hqf-godot-coverage
```

इससे `gdcov` और `gdcov-rustfuncs` कमांड इंस्टॉल हो जाते हैं। क्लोन से चलाने के लिए: पहले `uv sync`, फिर `uv run gdcov --help`।

## GDScript के लिए उपयोग

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

| विकल्प | मतलब |
| --- | --- |
| `-p, --project DIR` | जिस प्रोजेक्ट को मापना है (डिफ़ॉल्ट: मौजूदा डायरेक्टरी) |
| `-o, --out DIR` | रन डायरेक्टरी, जो बना दी जाती है (ज़रूरी) |
| `-e, --exclude GLOB` | वह स्क्रिप्ट जिसे इंस्ट्रुमेंट नहीं करना है, प्रोजेक्ट के सापेक्ष पाथ (डिफ़ॉल्ट: `tests/*`) |
| `-T, --tests GLOB` | चलाए जाने वाले सूट, प्रोजेक्ट के सापेक्ष पाथ, `**` सब-डायरेक्टरी में भी खोजता है (डिफ़ॉल्ट: `tests/test_*.gd`) |
| `-s, --skip GLOB` | वह सूट जिसे नहीं चलाना है, प्रोजेक्ट के सापेक्ष पाथ |
| `-u, --suite PATH` | सिर्फ़ यही सूट चलाता है (`--tests` और `--skip` को ओवरराइड करता है) |
| `-g, --godot PATH` | Godot बाइनरी |
| `-j, --jobs N` | एक साथ चलने वाले सूट की संख्या (डिफ़ॉल्ट: 2) |
| `-t, --timeout S` | कितने सेकंड बाद सूट को बंद कर दिया जाए (डिफ़ॉल्ट: 1800) |
| `-N, --no-nice` | सूट को `nice -n 19 ionice -c 3` के बजाय सामान्य प्राथमिकता पर चलाता है (नीचे idle प्राथमिकता वाला हिस्सा देखें) |
| `-m, --summary REGEX` | सूट का सारांश: उसके आउटपुट में REGEX का आख़िरी मैच (डिफ़ॉल्ट: आउटपुट की आख़िरी ग़ैर-ख़ाली लाइन) |
| `-d, --depth N` | रिपोर्ट के एक एरिया में डायरेक्टरी के कितने स्तर हों (डिफ़ॉल्ट: 1) |

`-e`, `-s` और `-u` कई बार दिए जा सकते हैं। `gdcov all` पहले `OUT/hits` को ख़ाली करता है; अकेला `run` पिछले हिट रखता है, इसलिए कई रन के नतीजे जुड़ते जाते हैं। एग्ज़िट कोड: 0, या 1 अगर कोई सूट फ़ेल हुआ या टाइमआउट हो गया (रिपोर्ट फिर भी लिखी जाती है)।

### आउटपुट फ़ाइलें

| फ़ाइल | सामग्री |
| --- | --- |
| `OUT/summary.txt` | कुल, हर एरिया और हर फ़ाइल का कवरेज, फिर कभी न चले फ़ंक्शन (सबसे बड़े पहले), और हर सूट का एग्ज़िट कोड, अवधि और सारांश |
| `OUT/coverage.json` | यही आँकड़े, मशीन से पढ़े जा सकने वाले रूप में |
| `OUT/html/index.html` | एरिया और फ़ाइलें, हर स्क्रिप्ट का एक पेज, जिसमें हर लाइन पर हिट (गिनती के साथ), मिस या न मापी गई का निशान है |
| `OUT/suites.json` | हर सूट रन का एक रिकॉर्ड |
| `OUT/logs/` | हर सूट का आउटपुट |
| `OUT/project/`, `OUT/hits/`, `OUT/coverage_map.json` | इंस्ट्रुमेंट की गई कॉपी, कच्चे काउंटर, प्रोब मैप |

## डिफ़ॉल्ट रूप से idle प्राथमिकता

दोनों टूल अपनी प्रोसेस `nice -n 19 ionice -c 3` के साथ शुरू करते हैं: सबसे कम CPU प्राथमिकता और idle I/O क्लास। कवरेज का एक रन कई मिनट तक Godot या cargo की कई प्रोसेस को व्यस्त रखता है, और अक्सर उसी दौरान आप उसी मशीन पर काम करते रहते हैं; idle प्राथमिकता पर ये प्रोसेस CPU का सिर्फ़ वही समय और डिस्क तक सिर्फ़ वही पहुँच लेती हैं जो कोई और नहीं माँग रहा, इसलिए एडिटर, ब्राउज़र और डेस्कटॉप तुरंत प्रतिक्रिया देते रहते हैं, और मशीन व्यस्त हो तो रन बस कुछ ज़्यादा समय लेता है। I/O की idle क्लास भी `nice` जितनी ही अहम है: अकेले डिस्क पर भारी लिखाई भी डेस्कटॉप को फ़्रीज़ कर सकती है, ख़ासकर एन्क्रिप्टेड डिस्क पर।

जिस मशीन पर कोई और काम न हो (CI रनर, बिल्ड सर्वर), वहाँ कम प्राथमिकता सिर्फ़ रन को धीमा करती है: इसे `-N` / `--no-nice` से बंद करें (`gdcov all -N ...`, `zsh rust_cov.zsh -N CRATE_DIR OUT_DIR`)। `rust_cov.zsh` में मेमोरी सीमा और `-j 1` दोनों ही स्थितियों में लागू रहते हैं।

## Rust के लिए उपयोग

```sh
zsh rust_cov.zsh /path/to/crate /path/to/rust_run
zsh rust_cov.zsh /path/to/crate /path/to/rust_run --features foo
zsh rust_cov.zsh -N /path/to/crate /path/to/rust_run   # normal priority
```

आउटपुट डायरेक्टरी के बाद दिए गए आर्ग्युमेंट टेस्ट रन को भेजे जाते हैं। स्क्रिप्ट आउटपुट डायरेक्टरी में ये फ़ाइलें लिखती है: `summary.txt` (हर फ़ाइल के हिसाब से), `missing_lines.txt`, `html/index.html`, `coverage.json`, `lcov.info`, और `never_executed.txt`। आख़िरी फ़ाइल में crate के वे फ़ंक्शन होते हैं जिनके हर monomorphised इंस्टेंस की गिनती शून्य है, सबसे लंबे पहले, नाम demangle किए हुए। `gdcov-rustfuncs -j coverage.json -r /path/to/crate` किसी एक्सपोर्ट से यही सूची दोबारा प्रिंट करता है।

हर cargo कॉल idle प्राथमिकता पर (जब तक `-N` न दिया जाए), एक systemd यूज़र scope के अंदर चलती है, जिसकी मेमोरी सीमा 3 GB है और swap बंद है (`systemd-run --user --scope -p MemoryMax=3G -p MemorySwapMax=0`); बिल्ड `-j 1` के साथ होता है। ऐसा न हो तो किसी बड़े crate का इंस्ट्रुमेंटेड बिल्ड सारे कोर घेर लेता है और इतनी मेमोरी खा जाता है कि डेस्कटॉप फ़्रीज़ हो जाए। सीमा पार करने वाली cargo कॉल बंद कर दी जाती है और स्क्रिप्ट रुक जाती है; सीमा बढ़ानी हो तो स्क्रिप्ट में `capped` बदलें।

## सीमाएँ

- सिर्फ़ लाइन कवरेज: GDScript के लिए ब्रांच या कंडीशन कवरेज नहीं है।
- GDScript स्कैनर लाइन के आधार पर काम करता है, पूरा पार्सर नहीं है: एक लाइन में `;` से जुड़े कई स्टेटमेंट एक ही लाइन गिने जाते हैं।
- हिट तब लिखे जाते हैं जब सूट का सीन ट्री बंद होता है: जो सूट क्रैश हो जाए या टाइमआउट तक पहुँच जाए, उसके उस रन के हिट खो जाते हैं।
- एग्ज़िट हुक वह पहला प्रोब सेट करता है जो ट्री को रूट मिलने के बाद चलता है: जो सूट अपना सारा काम `_init()` में करके वहीं बंद हो जाए, वह कोई हिट नहीं लिखता; उसकी जगह `_initialize()` या `_process()` का इस्तेमाल करें।
- सिर्फ़ वही स्क्रिप्ट गिनी जाती हैं जिन्हें सूट चलाते हैं; एडिटर में खोले गए सीन या एक्सपोर्ट किए गए बिल्ड नहीं मापे जाते।
- godot-rust crate में सिर्फ़ वही कोड मापा जाता है जहाँ तक `cargo test` पहुँचता है: जिन टेस्ट को चलते हुए Godot इंजन की ज़रूरत होती है, वे इसमें शामिल नहीं हैं।
- सिर्फ़ Linux (`rsync`, `nice`, `ionice`, `systemd-run`)।

## गुणवत्ता

ऊपर वाला CI बैज इन जाँचों का नतीजा दिखाता है, जो रोज़ एक बार और ज़रूरत पड़ने पर चलती हैं: Python 3.14 पर `pytest`, `mypy --strict`, `black --check` और `isort --check`। अपनी मशीन पर:

```sh
uv run pytest && uv run mypy && uv run black --check . && uv run isort --check .
```

## लाइसेंस

MIT, देखें [LICENSE](LICENSE)।
