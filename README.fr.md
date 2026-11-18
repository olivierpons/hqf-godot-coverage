# hqf-godot-coverage

[![CI](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml/badge.svg)](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776ab.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Godot 4](https://img.shields.io/badge/Godot-4-478cbf.svg?logo=godotengine&logoColor=white)](https://godotengine.org/)

🇬🇧 [English](README.md) · 🇫🇷 [Français](README.fr.md) · 🇨🇳 [简体中文](README.zh-CN.md) · 🇮🇳 [हिन्दी](README.hi.md) · 🇪🇸 [Español](README.es.md) · 🇸🇦 [العربية](README.ar.md) · 🇧🇩 [বাংলা](README.bn.md) · 🇧🇷 [Português](README.pt-BR.md) · 🇮🇩 [Bahasa Indonesia](README.id.md) · 🇵🇰 [اردو](README.ur.md)

Couverture de code pour les jeux Godot 4 :

- `gdcov` : couverture par ligne du code GDScript, mesurée pendant l’exécution des suites de tests du projet en mode headless ;
- `rust_cov.zsh` : couverture par ligne et par région d’une crate Rust (une GDExtension [godot-rust](https://godot-rust.github.io/) ou n’importe quelle autre) lors d’un `cargo test`, avec la liste des fonctions qu’aucun test n’a jamais exécutées.

## Fonctionnement de gdcov

1. **instrument** : le projet est copié dans `OUT/project` (par rsync, en excluant `.git`, les répertoires `target` de Cargo, `mutants.out*` et `__pycache__`). Dans chaque fichier `.gd` de la copie, sauf ceux qui sont exclus, un appel de sonde est ajouté sur la même ligne que chaque instruction d’un corps de fonction : les numéros de ligne ne bougent pas, pas plus que ceux cités dans les messages d’erreur. Les sondes comptent les passages dans des compteurs statiques de `res://__gdcov/rt.gd`. `OUT/coverage_map.json` relie chaque sonde à son fichier, à sa ligne et à sa fonction.
2. **run** : chaque suite s’exécute sur la copie avec `godot --headless --audio-driver Dummy --path OUT/project --script res://<suite>`, en priorité la plus basse (`nice -n 19 ionice -c 3`, voir plus bas), plusieurs en parallèle. À la sortie de son arbre de scène, chaque suite écrit ses compteurs dans `OUT/hits/`.
3. **report** : les fichiers de compteurs sont fusionnés avec la carte des sondes pour produire des rapports texte, JSON et HTML.

Une suite est un script qui étend `SceneTree` et qu’on lance avec `--script` ; par défaut, ce sont tous les `tests/test_*.gd`. Le projet d’origine n’est jamais modifié.

Mesuré : les instructions des corps de `func`, les corps `get`/`set` des propriétés, les corps tenant sur une seule ligne (`func f(): return 1`, `else: x`, motifs de `match`), les lambdas déclarées comme instructions.
Non mesuré : les initialisations au niveau de la classe, et les instructions d’une lambda multiligne écrite entre parenthèses (`connect(func(): ...)`), qui sont comptées avec la ligne qui les englobe.

## Prérequis

- Linux, Python 3.14, [uv](https://docs.astral.sh/uv/), `rsync` ;
- un binaire Godot 4 : celui indiqué par `-g/--godot`, sinon `godot` dans le `PATH`, sinon le plus récent des `~/godot/Godot_v4*-stable_linux.x86_64` ;
- pour Rust : `cargo install cargo-llvm-cov rustfilt`, `rustup component add llvm-tools-preview` pour la chaîne d’outils de la crate, et une session utilisateur systemd (pour le plafond de mémoire décrit plus bas).

## Installation

```sh
uv tool install git+https://github.com/olivierpons/hqf-godot-coverage
```

Vous obtenez ainsi les commandes `gdcov` et `gdcov-rustfuncs`. Depuis un clone du dépôt : `uv sync`, puis `uv run gdcov --help`.

## Utilisation avec GDScript

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

| Option | Signification |
| --- | --- |
| `-p, --project DIR` | projet à mesurer (par défaut : le répertoire courant) |
| `-o, --out DIR` | répertoire de l’exécution, créé par gdcov (obligatoire) |
| `-e, --exclude GLOB` | script à ne pas instrumenter, chemin relatif au projet (par défaut : `tests/*`) |
| `-T, --tests GLOB` | suites à lancer, chemin relatif au projet, `**` parcourt les sous-répertoires (par défaut : `tests/test_*.gd`) |
| `-s, --skip GLOB` | suite à ne pas lancer, chemin relatif au projet |
| `-u, --suite PATH` | ne lancer que cette suite (remplace `--tests` et `--skip`) |
| `-g, --godot PATH` | binaire Godot |
| `-j, --jobs N` | nombre de suites lancées en parallèle (par défaut : 2) |
| `-t, --timeout S` | délai en secondes avant l’arrêt forcé d’une suite (par défaut : 1800) |
| `-N, --no-nice` | lancer les suites en priorité normale au lieu de `nice -n 19 ionice -c 3` (voir la section « Priorité la plus basse, activée par défaut » plus bas) |
| `-m, --summary REGEX` | résumé d’une suite : dernière correspondance de REGEX dans sa sortie (par défaut : sa dernière ligne non vide) |
| `-d, --depth N` | nombre de niveaux de répertoires d’une zone du rapport (par défaut : 1) |

Les options `-e`, `-s` et `-u` peuvent être répétées. `gdcov all` vide d’abord `OUT/hits` ; `run` lancé seul conserve les compteurs précédents, si bien que plusieurs exécutions se cumulent. Code de sortie : 0, ou 1 si une suite a échoué ou dépassé le délai (le rapport est écrit malgré tout).

### Fichiers produits

| Fichier | Contenu |
| --- | --- |
| `OUT/summary.txt` | le total, par zone, par fichier, puis les fonctions jamais exécutées, des plus grandes aux plus petites, et les suites avec leur code de sortie, leur durée et leur résumé |
| `OUT/coverage.json` | les mêmes chiffres, dans un format exploitable par programme |
| `OUT/html/index.html` | les zones et les fichiers, avec une page par script où chaque ligne est marquée comme exécutée (avec son nombre de passages), non exécutée ou non mesurée |
| `OUT/suites.json` | un enregistrement par suite exécutée |
| `OUT/logs/` | la sortie de chaque suite |
| `OUT/project/`, `OUT/hits/`, `OUT/coverage_map.json` | la copie instrumentée, les compteurs bruts, la carte des sondes |

## Priorité la plus basse, activée par défaut

Les deux outils lancent leurs processus avec `nice -n 19 ionice -c 3` : la priorité processeur la plus basse et la classe d’E/S idle. Une mesure de couverture fait tourner plusieurs processus Godot ou cargo pendant des minutes, souvent pendant que vous continuez à travailler sur la même machine ; en priorité la plus basse, ces processus ne prennent que le temps processeur et les accès disque dont rien d’autre n’a besoin, si bien que l’éditeur, le navigateur et le bureau restent réactifs, et l’exécution dure simplement plus longtemps quand la machine est chargée. La classe d’E/S idle compte autant que `nice` : à elles seules, de grosses écritures sur le disque peuvent bloquer un poste de travail, surtout sur un disque chiffré.

Sur une machine qui n’a rien d’autre à faire (un runner de CI, un serveur de compilation), la priorité basse ne fait que ralentir l’exécution : désactivez-la avec `-N` / `--no-nice` (`gdcov all -N ...`, `zsh rust_cov.zsh -N CRATE_DIR OUT_DIR`). Pour `rust_cov.zsh`, le plafond de mémoire et `-j 1` restent appliqués dans tous les cas.

## Utilisation avec Rust

```sh
zsh rust_cov.zsh /path/to/crate /path/to/rust_run
zsh rust_cov.zsh /path/to/crate /path/to/rust_run --features foo
zsh rust_cov.zsh -N /path/to/crate /path/to/rust_run   # normal priority
```

Les arguments placés après le répertoire de sortie sont transmis à l’exécution des tests. Le script écrit dans le répertoire de sortie `summary.txt` (par fichier), `missing_lines.txt`, `html/index.html`, `coverage.json`, `lcov.info` et `never_executed.txt`. Ce dernier liste les fonctions de la crate dont toutes les instances monomorphisées ont un compteur à zéro, des plus longues aux plus courtes, avec leurs noms décodés (demangling). `gdcov-rustfuncs -j coverage.json -r /path/to/crate` réaffiche cette liste à partir d’un export.

Chaque appel à cargo s’exécute en priorité la plus basse (sauf avec `-N`), dans un scope systemd utilisateur limité à 3 Go de mémoire, sans swap (`systemd-run --user --scope -p MemoryMax=3G -p MemorySwapMax=0`), et la compilation utilise `-j 1` : sans ces limites, la compilation instrumentée d’une grosse crate occupe tous les cœurs et assez de mémoire pour bloquer un poste de travail. Un appel à cargo qui dépasse le plafond est tué et le script s’arrête ; pour relever ce plafond, modifiez `capped` dans le script.

## Limites

- Couverture par ligne uniquement : pas de couverture des branches ni des conditions pour GDScript.
- L’analyseur de GDScript travaille ligne par ligne, ce n’est pas un vrai parseur : plusieurs instructions séparées par `;` sur une même ligne comptent pour une seule ligne.
- Les compteurs sont écrits à la sortie de l’arbre de scène d’une suite : une suite qui plante ou atteint le délai perd ses compteurs pour cette exécution.
- Le hook de sortie est installé par la première sonde exécutée une fois que l’arbre a une racine : une suite qui fait tout son travail dans `_init()` et quitte depuis cette fonction n’écrit aucun compteur ; utilisez `_initialize()` ou `_process()`.
- Seuls comptent les scripts exécutés par les suites ; les scènes ouvertes par l’éditeur et les builds exportés ne sont pas mesurés.
- Pour les crates godot-rust, seul le code atteint par `cargo test` est mesuré : les tests qui ont besoin d’un moteur Godot en cours d’exécution n’en font pas partie.
- Linux uniquement (`rsync`, `nice`, `ionice`, `systemd-run`).

## Qualité

Contrôles lancés par la CI (badge ci-dessus) une fois par jour et à la demande : `pytest`, `mypy --strict`, `black --check` et `isort --check` sous Python 3.14. En local :

```sh
uv run pytest && uv run mypy && uv run black --check . && uv run isort --check .
```

## Licence

MIT, voir [LICENSE](LICENSE).
