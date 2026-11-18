# hqf-godot-coverage

[![CI](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml/badge.svg)](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776ab.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Godot 4](https://img.shields.io/badge/Godot-4-478cbf.svg?logo=godotengine&logoColor=white)](https://godotengine.org/)

🇬🇧 [English](README.md) · 🇫🇷 [Français](README.fr.md) · 🇨🇳 [简体中文](README.zh-CN.md) · 🇮🇳 [हिन्दी](README.hi.md) · 🇪🇸 [Español](README.es.md) · 🇸🇦 [العربية](README.ar.md) · 🇧🇩 [বাংলা](README.bn.md) · 🇧🇷 [Português](README.pt-BR.md) · 🇮🇩 [Bahasa Indonesia](README.id.md) · 🇵🇰 [اردو](README.ur.md)

Code coverage untuk game Godot 4:

- `gdcov`: line coverage kode GDScript, diukur selagi test suite headless milik proyek dijalankan;
- `rust_cov.zsh`: line coverage dan region coverage sebuah crate Rust (GDExtension buatan [godot-rust](https://godot-rust.github.io/) atau crate lain apa pun) saat `cargo test` dijalankan, lengkap dengan daftar fungsi yang belum pernah dijalankan oleh satu tes pun.

## Cara Kerja gdcov

1. **instrument**: proyek disalin ke `OUT/project` (dengan rsync, tanpa `.git`, direktori `target` milik Cargo, `mutants.out*`, dan `__pycache__`). Di setiap file `.gd` dalam salinan itu, kecuali yang dikecualikan, sebuah panggilan probe ditulis pada baris yang sama dengan setiap pernyataan di badan fungsi, sehingga nomor baris (dan juga pesan error) tidak bergeser. Probe mencatat jumlah eksekusi (hit) di penghitung statis dalam `res://__gdcov/rt.gd`. `OUT/coverage_map.json` memetakan setiap probe kembali ke file, baris, dan fungsinya.
2. **run**: setiap suite dijalankan pada salinan itu dengan `godot --headless --audio-driver Dummy --path OUT/project --script res://<suite>`, dengan prioritas idle (`nice -n 19 ionice -c 3`, lihat di bawah), beberapa sekaligus. Begitu scene tree-nya berakhir, suite menulis isi penghitungnya ke `OUT/hits/`.
3. **report**: file hit digabungkan dengan peta probe menjadi laporan dalam format teks, JSON, dan HTML.

Suite adalah skrip yang mewarisi `SceneTree` dan dijalankan dengan `--script`; secara default, semua `tests/test_*.gd`. Proyek aslinya tidak pernah diubah.

Yang diukur: pernyataan di badan `func`, badan `get`/`set` milik properti, badan satu baris (`func f(): return 1`, `else: x`, pola `match`), serta lambda yang dideklarasikan sebagai pernyataan. Yang tidak diukur: inisialisasi di tingkat kelas, serta pernyataan di dalam lambda multibaris yang ditulis di dalam tanda kurung (`connect(func(): ...)`), yang dihitung sebagai bagian dari baris yang memuatnya.

## Persyaratan

- Linux, Python 3.14, [uv](https://docs.astral.sh/uv/), `rsync`;
- binary Godot 4: `-g/--godot`, jika tidak ada maka `godot` di `PATH`, jika tidak ada juga maka versi terbaru dari `~/godot/Godot_v4*-stable_linux.x86_64`;
- untuk Rust: `cargo install cargo-llvm-cov rustfilt`, `rustup component add llvm-tools-preview` untuk toolchain yang dipakai crate tersebut, serta sesi pengguna systemd (dibutuhkan untuk batas memori yang dijelaskan di bawah).

## Instalasi

```sh
uv tool install git+https://github.com/olivierpons/hqf-godot-coverage
```

Perintah ini menginstal `gdcov` dan `gdcov-rustfuncs`. Dari hasil clone repositori: `uv sync`, lalu `uv run gdcov --help`.

## Penggunaan GDScript

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

| Opsi | Arti |
| --- | --- |
| `-p, --project DIR` | proyek yang diukur (default: direktori saat ini) |
| `-o, --out DIR` | direktori run, akan dibuat otomatis (wajib) |
| `-e, --exclude GLOB` | skrip yang tidak diinstrumentasi, path relatif terhadap proyek (default: `tests/*`) |
| `-T, --tests GLOB` | suite yang dijalankan, path relatif terhadap proyek, `**` mencakup subdirektori secara rekursif (default: `tests/test_*.gd`) |
| `-s, --skip GLOB` | suite yang tidak dijalankan, path relatif terhadap proyek |
| `-u, --suite PATH` | hanya jalankan suite ini (menggantikan `--tests` dan `--skip`) |
| `-g, --godot PATH` | binary Godot |
| `-j, --jobs N` | jumlah suite yang berjalan bersamaan (default: 2) |
| `-t, --timeout S` | jumlah detik sebelum suite dihentikan paksa (default: 1800) |
| `-N, --no-nice` | jalankan suite dengan prioritas normal, bukan dengan `nice -n 19 ionice -c 3` (lihat bagian tentang prioritas idle di bawah) |
| `-m, --summary REGEX` | ringkasan suite: kecocokan terakhir REGEX dalam output-nya (default: baris terakhirnya yang tidak kosong) |
| `-d, --depth N` | jumlah tingkat direktori dalam satu area laporan (default: 1) |

`-e`, `-s`, dan `-u` dapat diulang. `gdcov all` mengosongkan `OUT/hits` terlebih dahulu; `run` yang dijalankan sendiri tetap menyimpan hit sebelumnya, sehingga hasil beberapa run terakumulasi. Exit code: 0, atau 1 jika ada suite yang gagal atau melewati batas waktu (laporan tetap ditulis).

### File Output

| File | Isi |
| --- | --- |
| `OUT/summary.txt` | total, per area, per file, lalu fungsi yang tidak pernah dieksekusi (yang terbesar lebih dulu), lalu daftar suite beserta exit code, durasi, dan ringkasannya |
| `OUT/coverage.json` | angka yang sama, dalam format yang dapat dibaca mesin |
| `OUT/html/index.html` | area dan file, satu halaman per skrip dengan setiap baris ditandai sebagai dieksekusi (beserta jumlahnya), tidak dieksekusi, atau tidak diukur |
| `OUT/suites.json` | satu entri untuk setiap suite yang dijalankan |
| `OUT/logs/` | output setiap suite |
| `OUT/project/`, `OUT/hits/`, `OUT/coverage_map.json` | salinan yang sudah diinstrumentasi, penghitung mentah, peta probe |

## Prioritas Idle sebagai Default

Kedua tool menjalankan prosesnya dengan `nice -n 19 ionice -c 3`: prioritas CPU terendah dan kelas I/O idle. Satu run coverage membuat beberapa proses Godot atau cargo sibuk selama beberapa menit, sering kali saat Anda tetap bekerja di mesin yang sama; dengan prioritas idle, proses-proses itu hanya memakai waktu CPU dan akses disk yang tidak diminta proses lain, sehingga editor, browser, dan desktop tetap responsif, dan run hanya menjadi lebih lama saat mesin sedang sibuk. Kelas I/O idle sama pentingnya dengan `nice`: penulisan disk yang berat saja sudah bisa membuat desktop macet, terutama pada disk terenkripsi.

Pada mesin yang tidak punya pekerjaan lain (runner CI, server build), prioritas idle hanya memperlambat run: matikan dengan `-N` / `--no-nice` (`gdcov all -N ...`, `zsh rust_cov.zsh -N CRATE_DIR OUT_DIR`). Untuk `rust_cov.zsh`, batas memori dan `-j 1` tetap berlaku dalam kedua kasus.

## Penggunaan Rust

```sh
zsh rust_cov.zsh /path/to/crate /path/to/rust_run
zsh rust_cov.zsh /path/to/crate /path/to/rust_run --features foo
zsh rust_cov.zsh -N /path/to/crate /path/to/rust_run   # normal priority
```

Argumen setelah direktori output diteruskan ke run tes. Di dalam direktori output, skrip menulis: `summary.txt` (per file), `missing_lines.txt`, `html/index.html`, `coverage.json`, `lcov.info`, dan `never_executed.txt`, yaitu daftar fungsi crate yang hitungan seluruh instance monomorfiknya nol, diurutkan dari yang terpanjang, dengan nama yang sudah di-demangle. `gdcov-rustfuncs -j coverage.json -r /path/to/crate` mencetak ulang daftar itu dari file hasil ekspor.

Setiap pemanggilan cargo berjalan dengan prioritas idle (kecuali dengan `-N`) di dalam scope pengguna systemd yang dibatasi memori 3 GB tanpa swap (`systemd-run --user --scope -p MemoryMax=3G -p MemorySwapMax=0`), dan build memakai `-j 1`: tanpa pembatasan ini, build terinstrumentasi dari crate besar akan memakai semua core dan cukup banyak memori untuk membuat desktop macet. Pemanggilan cargo yang melampaui batas akan dihentikan paksa dan skrip berhenti; untuk menaikkan batas, ubah `capped` di dalam skrip.

## Batasan

- Hanya line coverage: tidak ada branch coverage maupun condition coverage untuk GDScript.
- Pemindai GDScript bekerja per baris, bukan parser lengkap: beberapa pernyataan yang digabung dengan `;` dalam satu baris dihitung sebagai satu baris.
- Hit ditulis saat scene tree milik suite berakhir: suite yang crash atau melewati batas waktu kehilangan hit-nya untuk run tersebut.
- Exit hook dipasang oleh probe pertama yang berjalan setelah tree memiliki root: suite yang mengerjakan semuanya di `_init()` lalu keluar di sana tidak menulis hit apa pun; gunakan `_initialize()` atau `_process()`.
- Hanya skrip yang dijalankan oleh suite yang dihitung; scene yang dibuka di editor dan build hasil ekspor tidak diukur.
- Untuk crate godot-rust, hanya kode yang dijangkau oleh `cargo test` yang diukur: tes yang membutuhkan engine Godot yang sedang berjalan tidak termasuk di dalamnya.
- Hanya untuk Linux (`rsync`, `nice`, `ionice`, `systemd-run`).

## Kualitas

Dijalankan di CI sekali sehari dan kapan pun diminta, hasilnya terlihat pada badge di atas: `pytest`, `mypy --strict`, `black --check`, dan `isort --check` pada Python 3.14. Secara lokal:

```sh
uv run pytest && uv run mypy && uv run black --check . && uv run isort --check .
```

## Lisensi

MIT, lihat [LICENSE](LICENSE).
