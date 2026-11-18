# hqf-godot-coverage

[![CI](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml/badge.svg)](https://github.com/olivierpons/hqf-godot-coverage/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776ab.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Godot 4](https://img.shields.io/badge/Godot-4-478cbf.svg?logo=godotengine&logoColor=white)](https://godotengine.org/)

🇬🇧 [English](README.md) · 🇫🇷 [Français](README.fr.md) · 🇨🇳 [简体中文](README.zh-CN.md) · 🇮🇳 [हिन्दी](README.hi.md) · 🇪🇸 [Español](README.es.md) · 🇸🇦 [العربية](README.ar.md) · 🇧🇩 [বাংলা](README.bn.md) · 🇧🇷 [Português](README.pt-BR.md) · 🇮🇩 [Bahasa Indonesia](README.id.md) · 🇵🇰 [اردو](README.ur.md)

Cobertura de código para jogos feitos com Godot 4:

- `gdcov`: cobertura por linha do código GDScript, medida enquanto as suítes de teste do projeto rodam em modo headless;
- `rust_cov.zsh`: cobertura por linha e por região de um crate Rust (uma GDExtension [godot-rust](https://godot-rust.github.io/) ou qualquer outro) durante o `cargo test`, com a lista das funções que nenhum teste chegou a executar.

## Funcionamento do gdcov

1. **instrument**: o projeto é copiado para `OUT/project` (via rsync, excluindo `.git`, os diretórios `target` do Cargo, `mutants.out*` e `__pycache__`). Em cada arquivo `.gd` da cópia, exceto nos excluídos, uma chamada de sonda é inserida na mesma linha de cada instrução do corpo de uma função; assim, os números de linha não mudam, nem os que aparecem nas mensagens de erro. As sondas contam as execuções em contadores estáticos de `res://__gdcov/rt.gd`. O `OUT/coverage_map.json` associa cada sonda ao seu arquivo, à sua linha e à sua função.
2. **run**: cada suíte roda na cópia com `godot --headless --audio-driver Dummy --path OUT/project --script res://<suite>`, na prioridade mais baixa (`nice -n 19 ionice -c 3`, veja mais abaixo), várias ao mesmo tempo. Quando sua árvore de cena termina, cada suíte grava seus contadores em `OUT/hits/`.
3. **report**: os arquivos de contadores são combinados com o mapa de sondas para gerar relatórios em texto, JSON e HTML.

Uma suíte é um script que estende `SceneTree` e é executado com `--script`; por padrão, são todos os `tests/test_*.gd`. O projeto original nunca é modificado.

O que é medido: as instruções dos corpos de `func`, os corpos `get`/`set` das propriedades, os corpos de uma linha só (`func f(): return 1`, `else: x`, padrões de `match`) e as lambdas declaradas como instruções.
O que não é medido: os inicializadores no nível da classe e as instruções de uma lambda de várias linhas escrita entre parênteses (`connect(func(): ...)`), que contam como a linha que a contém.

## Requisitos

- Linux, Python 3.14, [uv](https://docs.astral.sh/uv/), `rsync`;
- um binário do Godot 4: o indicado em `-g/--godot`, ou então `godot` no `PATH`, ou então o mais recente entre os `~/godot/Godot_v4*-stable_linux.x86_64`;
- para Rust: `cargo install cargo-llvm-cov rustfilt`, `rustup component add llvm-tools-preview` para a toolchain do crate e uma sessão de usuário do systemd (para o limite de memória descrito mais abaixo).

## Instalação

```sh
uv tool install git+https://github.com/olivierpons/hqf-godot-coverage
```

Isso instala os comandos `gdcov` e `gdcov-rustfuncs`. A partir de um clone do repositório: `uv sync` e depois `uv run gdcov --help`.

## Uso com GDScript

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

| Opção | Significado |
| --- | --- |
| `-p, --project DIR` | projeto a medir (padrão: o diretório atual) |
| `-o, --out DIR` | diretório da execução, criado pelo gdcov (obrigatório) |
| `-e, --exclude GLOB` | script que não deve ser instrumentado, caminho relativo ao projeto (padrão: `tests/*`) |
| `-T, --tests GLOB` | suítes a executar, caminho relativo ao projeto, `**` percorre os subdiretórios (padrão: `tests/test_*.gd`) |
| `-s, --skip GLOB` | suíte que não deve ser executada, caminho relativo ao projeto |
| `-u, --suite PATH` | executar só esta suíte (substitui `--tests` e `--skip`) |
| `-g, --godot PATH` | binário do Godot |
| `-j, --jobs N` | número de suítes executadas ao mesmo tempo (padrão: 2) |
| `-t, --timeout S` | segundos até uma suíte ser encerrada à força (padrão: 1800) |
| `-N, --no-nice` | executar as suítes na prioridade normal em vez de `nice -n 19 ionice -c 3` (veja mais abaixo a seção sobre a prioridade mais baixa) |
| `-m, --summary REGEX` | resumo de uma suíte: última correspondência de REGEX na saída dela (padrão: a última linha não vazia da saída) |
| `-d, --depth N` | níveis de diretório de uma área do relatório (padrão: 1) |

As opções `-e`, `-s` e `-u` podem ser repetidas. O `gdcov all` esvazia `OUT/hits` primeiro; o `run` sozinho mantém os contadores anteriores, então várias execuções se somam. Código de saída: 0, ou 1 quando uma suíte falha ou estoura o tempo limite (o relatório é gravado mesmo assim).

### Arquivos gerados

| Arquivo | Conteúdo |
| --- | --- |
| `OUT/summary.txt` | o total, por área e por arquivo; depois, as funções nunca executadas, da maior para a menor, e as suítes com código de saída, duração e resumo |
| `OUT/coverage.json` | os mesmos números, em formato legível por máquina |
| `OUT/html/index.html` | as áreas e os arquivos, com uma página por script em que cada linha aparece marcada como executada (com o número de execuções), não executada ou não medida |
| `OUT/suites.json` | um registro por suíte executada |
| `OUT/logs/` | a saída de cada suíte |
| `OUT/project/`, `OUT/hits/`, `OUT/coverage_map.json` | a cópia instrumentada, os contadores brutos, o mapa de sondas |

## Prioridade mais baixa, ativada por padrão

As duas ferramentas iniciam seus processos com `nice -n 19 ionice -c 3`: a prioridade de CPU mais baixa e a classe de E/S idle. Uma medição de cobertura mantém vários processos do Godot ou do cargo ocupados por minutos, muitas vezes enquanto você continua trabalhando na mesma máquina; na prioridade mais baixa, esses processos só usam o tempo de CPU e o acesso ao disco que nenhum outro processo está pedindo, então o editor, o navegador e o desktop continuam respondendo bem, e a execução só demora mais quando a máquina está ocupada. A classe de E/S idle importa tanto quanto o `nice`: só a escrita pesada em disco já pode travar um desktop, principalmente num disco criptografado.

Numa máquina que não tem mais nada para fazer (um runner de CI, um servidor de build), a prioridade baixa só deixa a execução mais lenta: desative-a com `-N` / `--no-nice` (`gdcov all -N ...`, `zsh rust_cov.zsh -N CRATE_DIR OUT_DIR`). No `rust_cov.zsh`, o limite de memória e o `-j 1` continuam valendo nos dois casos.

## Uso com Rust

```sh
zsh rust_cov.zsh /path/to/crate /path/to/rust_run
zsh rust_cov.zsh /path/to/crate /path/to/rust_run --features foo
zsh rust_cov.zsh -N /path/to/crate /path/to/rust_run   # normal priority
```

Os argumentos que vêm depois do diretório de saída são repassados à execução dos testes. O script grava no diretório de saída `summary.txt` (por arquivo), `missing_lines.txt`, `html/index.html`, `coverage.json`, `lcov.info` e `never_executed.txt`. Este último lista as funções do crate cujas instâncias monomorfizadas têm todas contagem zero, da mais longa para a mais curta, com os nomes já legíveis (após o demangling). `gdcov-rustfuncs -j coverage.json -r /path/to/crate` mostra essa lista de novo a partir de uma exportação.

Cada chamada ao cargo roda na prioridade mais baixa (a não ser com `-N`), dentro de um escopo de usuário do systemd limitado a 3 GB de memória, sem swap (`systemd-run --user --scope -p MemoryMax=3G -p MemorySwapMax=0`), e o build usa `-j 1`: sem esses limites, o build instrumentado de um crate grande ocupa todos os núcleos e memória suficiente para travar um desktop. Uma chamada ao cargo que passa do limite é encerrada e o script para; para aumentar esse limite, edite `capped` no script.

## Limitações

- Só cobertura por linha: não há cobertura de ramos nem de condições para GDScript.
- O analisador de GDScript trabalha linha por linha e não é um parser completo: várias instruções unidas por `;` numa mesma linha contam como uma só.
- Os contadores são gravados quando a árvore de cena de uma suíte termina: uma suíte que falha abruptamente ou estoura o tempo limite perde os contadores daquela execução.
- O hook de saída é instalado pela primeira sonda executada depois que a árvore tem uma raiz: uma suíte que faz todo o trabalho em `_init()` e sai dali não grava nenhum contador; use `_initialize()` ou `_process()`.
- Só contam os scripts executados pelas suítes; cenas abertas pelo editor e builds exportados não são medidos.
- Em crates godot-rust, só é medido o código alcançado pelo `cargo test`: os testes que precisam de um motor Godot em execução ficam de fora.
- Só Linux (`rsync`, `nice`, `ionice`, `systemd-run`).

## Qualidade

A CI (veja o selo acima) roda estas verificações uma vez por dia e sob demanda, com Python 3.14: `pytest`, `mypy --strict`, `black --check` e `isort --check`. Localmente:

```sh
uv run pytest && uv run mypy && uv run black --check . && uv run isort --check .
```

## Licença

MIT, veja [LICENSE](LICENSE).
