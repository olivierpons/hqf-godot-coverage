# hqf-godot-coverage

[![CI](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml/badge.svg)](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776ab.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Godot 4](https://img.shields.io/badge/Godot-4-478cbf.svg?logo=godotengine&logoColor=white)](https://godotengine.org/)

🇬🇧 [English](README.md) · 🇫🇷 [Français](README.fr.md) · 🇨🇳 [简体中文](README.zh-CN.md) · 🇮🇳 [हिन्दी](README.hi.md) · 🇪🇸 [Español](README.es.md) · 🇸🇦 [العربية](README.ar.md) · 🇧🇩 [বাংলা](README.bn.md) · 🇧🇷 [Português](README.pt-BR.md) · 🇮🇩 [Bahasa Indonesia](README.id.md) · 🇵🇰 [اردو](README.ur.md)

Cobertura de código para juegos de Godot 4:

- `gdcov`: cobertura por línea del código GDScript, medida mientras se ejecutan las suites de pruebas del proyecto en modo headless;
- `rust_cov.zsh`: cobertura por línea y por región de un crate de Rust (una GDExtension de [godot-rust](https://godot-rust.github.io/) o cualquier otro) durante un `cargo test`, junto con la lista de las funciones que ninguna prueba llegó a ejecutar.

## Funcionamiento de gdcov

1. **instrument**: el proyecto se copia en `OUT/project` (con rsync, excluyendo `.git`, los directorios `target` de Cargo, `mutants.out*` y `__pycache__`). En cada archivo `.gd` de la copia, salvo en los excluidos, se añade una llamada de sonda en la misma línea que cada instrucción del cuerpo de una función, de modo que los números de línea no cambian, ni tampoco los que aparecen en los mensajes de error. Las sondas cuentan las ejecuciones en contadores estáticos de `res://__gdcov/rt.gd`. `OUT/coverage_map.json` asocia cada sonda con su archivo, su línea y su función.
2. **run**: cada suite se ejecuta sobre la copia con `godot --headless --audio-driver Dummy --path OUT/project --script res://<suite>`, con la prioridad más baja (`nice -n 19 ionice -c 3`, véase más abajo), varias a la vez. Cuando su árbol de escena termina, cada suite escribe sus contadores en `OUT/hits/`.
3. **report**: los archivos de contadores se combinan con el mapa de sondas para generar informes en texto, JSON y HTML.

Una suite es un script que extiende `SceneTree` y se ejecuta con `--script`; por defecto, son todos los `tests/test_*.gd`. El proyecto original nunca se modifica.

Se mide: las instrucciones de los cuerpos de `func`, los cuerpos `get`/`set` de las propiedades, los cuerpos de una sola línea (`func f(): return 1`, `else: x`, patrones de `match`) y las lambdas declaradas como instrucciones.
No se mide: los inicializadores a nivel de clase ni las instrucciones de una lambda de varias líneas escrita entre paréntesis (`connect(func(): ...)`), que cuentan como la línea que la contiene.

## Requisitos

- Linux, Python 3.14, [uv](https://docs.astral.sh/uv/), `rsync`;
- un binario de Godot 4: el indicado con `-g/--godot`, o bien `godot` en el `PATH`, o bien el más reciente de los `~/godot/Godot_v4*-stable_linux.x86_64`;
- para Rust: `cargo install cargo-llvm-cov rustfilt`, `rustup component add llvm-tools-preview` para la cadena de herramientas del crate y una sesión de usuario de systemd (para el límite de memoria que se describe más abajo).

## Instalación

```sh
uv tool install git+https://github.com/olivierpons/hqf-godot-coverage
```

Así se instalan los comandos `gdcov` y `gdcov-rustfuncs`. Desde un clon del repositorio: `uv sync` y después `uv run gdcov --help`.

## Uso con GDScript

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

| Opción | Significado |
| --- | --- |
| `-p, --project DIR` | proyecto que se mide (por defecto: el directorio actual) |
| `-o, --out DIR` | directorio de la ejecución, creado por gdcov (obligatorio) |
| `-e, --exclude GLOB` | script que no se instrumenta, ruta relativa al proyecto (por defecto: `tests/*`) |
| `-T, --tests GLOB` | suites que se ejecutan, ruta relativa al proyecto, `**` recorre los subdirectorios (por defecto: `tests/test_*.gd`) |
| `-s, --skip GLOB` | suite que no se ejecuta, ruta relativa al proyecto |
| `-u, --suite PATH` | ejecutar solo esta suite (sustituye a `--tests` y `--skip`) |
| `-g, --godot PATH` | binario de Godot |
| `-j, --jobs N` | número de suites ejecutadas a la vez (por defecto: 2) |
| `-t, --timeout S` | segundos antes de forzar la terminación de una suite (por defecto: 1800) |
| `-N, --no-nice` | ejecutar las suites con prioridad normal en lugar de `nice -n 19 ionice -c 3` (véase más abajo la sección sobre la prioridad más baja) |
| `-m, --summary REGEX` | resumen de una suite: última coincidencia de REGEX en su salida (por defecto: su última línea no vacía) |
| `-d, --depth N` | niveles de directorio de una zona del informe (por defecto: 1) |

Las opciones `-e`, `-s` y `-u` se pueden repetir. `gdcov all` vacía primero `OUT/hits`; `run` por sí solo conserva los contadores anteriores, así que varias ejecuciones se acumulan. Código de salida: 0, o 1 si una suite falló o superó el tiempo límite (el informe se escribe de todos modos).

### Archivos generados

| Archivo | Contenido |
| --- | --- |
| `OUT/summary.txt` | el total, por zona y por archivo; después, las funciones nunca ejecutadas, de mayor a menor, y las suites con su código de salida, su duración y su resumen |
| `OUT/coverage.json` | las mismas cifras, en un formato legible por máquina |
| `OUT/html/index.html` | las zonas y los archivos, con una página por script en la que cada línea aparece marcada como ejecutada (con su número de ejecuciones), no ejecutada o no medida |
| `OUT/suites.json` | un registro por cada suite ejecutada |
| `OUT/logs/` | la salida de cada suite |
| `OUT/project/`, `OUT/hits/`, `OUT/coverage_map.json` | la copia instrumentada, los contadores sin procesar, el mapa de sondas |

## Prioridad más baja, activada por defecto

Las dos herramientas lanzan sus procesos con `nice -n 19 ionice -c 3`: la prioridad de CPU más baja y la clase de E/S idle. Una medición de cobertura mantiene ocupados varios procesos de Godot o de cargo durante minutos, a menudo mientras sigues trabajando en la misma máquina; con la prioridad más baja, esos procesos solo usan el tiempo de CPU y los accesos a disco que ningún otro proceso pide, así que el editor, el navegador y el escritorio siguen respondiendo con fluidez, y la ejecución simplemente tarda más cuando la máquina está ocupada. La clase de E/S idle importa tanto como `nice`: las escrituras intensivas en disco bastan por sí solas para congelar un equipo de escritorio, sobre todo si el disco está cifrado.

En una máquina que no tiene nada más que hacer (un runner de CI, un servidor de compilación), la prioridad baja solo ralentiza la ejecución: desactívala con `-N` / `--no-nice` (`gdcov all -N ...`, `zsh rust_cov.zsh -N CRATE_DIR OUT_DIR`). En `rust_cov.zsh`, el límite de memoria y `-j 1` se mantienen en ambos casos.

## Uso con Rust

```sh
zsh rust_cov.zsh /path/to/crate /path/to/rust_run
zsh rust_cov.zsh /path/to/crate /path/to/rust_run --features foo
zsh rust_cov.zsh -N /path/to/crate /path/to/rust_run   # normal priority
```

Los argumentos que van después del directorio de salida se pasan a la ejecución de las pruebas. El script escribe en el directorio de salida `summary.txt` (por archivo), `missing_lines.txt`, `html/index.html`, `coverage.json`, `lcov.info` y `never_executed.txt`. Este último enumera las funciones del crate cuyas instancias monomorfizadas tienen todas el contador a cero, de la más larga a la más corta, con los nombres ya legibles (tras el demangling). `gdcov-rustfuncs -j coverage.json -r /path/to/crate` vuelve a mostrar esa lista a partir de una exportación.

Cada llamada a cargo se ejecuta con la prioridad más baja (salvo con `-N`), dentro de un scope de usuario de systemd limitado a 3 GB de memoria y sin swap (`systemd-run --user --scope -p MemoryMax=3G -p MemorySwapMax=0`), y la compilación usa `-j 1`: sin estos límites, la compilación instrumentada de un crate grande ocupa todos los núcleos y memoria suficiente para congelar un equipo de escritorio. Una llamada a cargo que supera el límite se interrumpe y el script se detiene; para subir ese límite, edita `capped` en el script.

## Limitaciones

- Solo cobertura por línea: no hay cobertura de ramas ni de condiciones para GDScript.
- El analizador de GDScript trabaja línea a línea y no es un parser completo: varias instrucciones unidas con `;` en una misma línea cuentan como una sola.
- Los contadores se escriben cuando termina el árbol de escena de una suite: una suite que falla de forma abrupta o agota el tiempo límite pierde sus contadores de esa ejecución.
- El hook de salida lo instala la primera sonda que se ejecuta cuando el árbol ya tiene raíz: una suite que hace todo su trabajo en `_init()` y sale desde ahí no escribe ningún contador; usa `_initialize()` o `_process()`.
- Solo cuentan los scripts que ejecutan las suites; no se miden las escenas abiertas por el editor ni las builds exportadas.
- En los crates de godot-rust, solo se mide el código que alcanza `cargo test`: las pruebas que necesitan un motor Godot en ejecución quedan fuera.
- Solo Linux (`rsync`, `nice`, `ionice`, `systemd-run`).

## Calidad

La CI (ver el distintivo de arriba) ejecuta estas comprobaciones una vez al día y bajo demanda, con Python 3.14: `pytest`, `mypy --strict`, `isort --check` y `black --check`. En local:

```sh
uv run pytest && uv run mypy && uv run black --check . && uv run isort --check .
```

## Licencia

MIT; consulta [LICENSE](LICENSE).
