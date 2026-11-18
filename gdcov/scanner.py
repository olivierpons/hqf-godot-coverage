"""Finds the executable lines of a GDScript file and inserts hit probes on them.

A probe is a call that records one hit and returns ``true``; it is written on the same
physical line as the code it measures, so line numbers of the instrumented copy match
the original file. Three forms exist:

- ``stmt``: ``<PROBE>; <statement>`` in front of a statement of a function body;
- ``elif``: ``elif <PROBE> and <condition>:`` (an ``elif`` cannot follow a ``;``);
- ``inline``: after the colon of a one-line body (``func f(): return 1``,
  ``else: x += 1``, a ``match`` pattern ``1: return x``, a property ``get: return _x``).

Only lines inside function bodies (``func``, property ``get``/``set``, lambdas declared
as a statement) are measured. Not measured: class-level member initialisers, and the
statements of a multi-line lambda written inside brackets (``connect(func(): ...)``),
which are part of the enclosing statement's line.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

ProbeKind = Literal["stmt", "elif", "inline"]
BlockKind = Literal["func", "class", "property", "match", "block"]

_FUNC_HEADER = re.compile(r"^(?:@\w+(?:\([^)]*\))?\s+)*(?:static\s+)?func\s+(\w+)")
_CLASS_HEADER = re.compile(r"^class\s+(\w+)")
_PROPERTY_HEADER = re.compile(r"^(?:@\w+(?:\([^)]*\))?\s+)*(?:static\s+)?var\s+(\w+)")
_ACCESSOR = re.compile(r"^(?:(get)\s*:|(set)\s*\()")
_TRIPLE_QUOTES = ('"""', "'''")
TAB_WIDTH = 4


@dataclass(frozen=True)
class Probe:
    """One measured line.

    Attributes:
        line: 1-based physical line of the original file.
        col: 0-based column where the probe text is inserted.
        kind: Which probe form is inserted at ``col``.
        function: Qualified name of the enclosing function (``Inner.method``,
            ``health.set``).
    """

    line: int
    col: int
    kind: ProbeKind
    function: str


@dataclass(frozen=True)
class Function:
    """A named function, property accessor or inner-class method.

    Attributes:
        name: Qualified name, as in [Probe.function].
        line: 1-based line of its header.
    """

    name: str
    line: int


@dataclass
class ScanResult:
    """Probes in file order, and every function header found."""

    probes: list[Probe] = field(default_factory=list)
    functions: list[Function] = field(default_factory=list)


@dataclass
class _Block:
    indent: int
    kind: BlockKind = "block"
    name: str = ""


@dataclass
class _LexState:
    quote: str | None = None
    raw: bool = False
    depth: int = 0
    backslash: bool = False

    def continues(self) -> bool:
        return self.quote is not None or self.depth > 0 or self.backslash


@dataclass
class _PhysicalLine:
    """Lexical facts of one physical line, read with the state left by the line before.

    ``colons`` holds the columns of colons outside strings, comments and brackets;
    ``last`` is the column of the last character that is neither blank nor comment,
    -1 when there is none.
    """

    colons: list[int]
    last: int


def _lex_line(text: str, state: _LexState) -> _PhysicalLine:
    colons: list[int] = []
    last = -1
    i = 0
    state.backslash = False
    while i < len(text):
        ch = text[i]
        if state.quote is not None:
            last = i
            if ch == "\\" and not state.raw:
                i += 2
                continue
            if text.startswith(state.quote, i):
                i += len(state.quote)
                last = i - 1
                state.quote = None
                continue
            i += 1
            continue
        if ch == "#":
            break
        if ch in " \t\r":
            i += 1
            continue
        last = i
        if ch == "\\" and text[i + 1 :].strip() == "":
            state.backslash = True
            break
        if ch in "\"'":
            triple = text[i : i + 3]
            state.quote = triple if triple in _TRIPLE_QUOTES else ch
            state.raw = i > 0 and text[i - 1] == "r"
            i += len(state.quote)
            continue
        if ch in "([{":
            state.depth += 1
        elif ch in ")]}":
            state.depth = max(0, state.depth - 1)
        elif ch == ":" and state.depth == 0:
            colons.append(i)
        i += 1
    return _PhysicalLine(colons, last)


def _indent_width(text: str) -> int:
    width = 0
    for ch in text:
        if ch == "\t":
            width += TAB_WIDTH
        elif ch == " ":
            width += 1
        else:
            break
    return width


@dataclass
class _Logical:
    """A logical line: its first physical line plus its continuation lines."""

    start: int
    indent: int
    ws: int
    text: str
    lines: list[tuple[int, _PhysicalLine]]

    def opens_block(self) -> bool:
        __, last = self.lines[-1]
        return bool(last.colons) and last.colons[-1] == last.last

    def inline_colon(self) -> tuple[int, int] | None:
        """Line and column of the first top-level colon followed by code on its line."""
        for number, physical in self.lines:
            if physical.colons:
                col = physical.colons[0]
                return (number, col) if physical.last > col else None
        return None


def _logical_lines(source: str) -> list[_Logical]:
    state = _LexState()
    result: list[_Logical] = []
    for number, text in enumerate(source.split("\n"), start=1):
        continuation = state.continues()
        physical = _lex_line(text, state)
        if continuation:
            result[-1].lines.append((number, physical))
            continue
        stripped = text.lstrip(" \t")
        if physical.last < 0:
            continue
        logical = _Logical(
            start=number,
            indent=_indent_width(text),
            ws=len(text) - len(stripped),
            text=stripped,
            lines=[(number, physical)],
        )
        result.append(logical)
    return result


def _qualified(stack: list[_Block], name: str) -> str:
    parts = [b.name for b in stack if b.kind in ("class", "property")]
    return ".".join([*parts, name])


def _function_of(stack: list[_Block]) -> str | None:
    names: list[str] = []
    for block in stack:
        if block.kind in ("class", "property", "func"):
            names.append(block.name)
        if block.kind == "func":
            return ".".join(names)
    return None


def _add_inline(result: ScanResult, logical: _Logical, function: str) -> None:
    where = logical.inline_colon()
    if where is not None:
        line, col = where
        result.probes.append(Probe(line, col + 1, "inline", function))


def _header(
    result: ScanResult,
    stack: list[_Block],
    logical: _Logical,
    name: str,
    kind: BlockKind,
) -> None:
    qualified = _qualified(stack, name)
    result.functions.append(Function(qualified, logical.start))
    if logical.opens_block():
        stack.append(_Block(logical.indent, kind, name))
    else:
        _add_inline(result, logical, qualified)


def scan(source: str) -> ScanResult:
    """Lists the probes to insert in [param source] and the functions it declares."""
    result = ScanResult()
    stack: list[_Block] = []
    for logical in _logical_lines(source):
        while stack and stack[-1].indent >= logical.indent:
            stack.pop()
        text = logical.text
        top = stack[-1] if stack else None
        function = _function_of(stack)
        if (header := _FUNC_HEADER.match(text)) is not None:
            _header(result, stack, logical, header.group(1), "func")
        elif top is not None and top.kind == "match":
            if logical.opens_block():
                stack.append(_Block(logical.indent))
            elif function is not None:
                _add_inline(result, logical, function)
        elif top is not None and top.kind == "property":
            if (accessor := _ACCESSOR.match(text)) is not None:
                name = accessor.group(1) or accessor.group(2)
                _header(result, stack, logical, name, "func")
        elif function is None:
            if (klass := _CLASS_HEADER.match(text)) is not None:
                if logical.opens_block():
                    stack.append(_Block(logical.indent, "class", klass.group(1)))
            elif (prop := _PROPERTY_HEADER.match(text)) is not None:
                if logical.opens_block():
                    stack.append(_Block(logical.indent, "property", prop.group(1)))
        elif text.startswith("@"):
            continue
        else:
            _statement(result, stack, logical, function)
    return result


def _statement(
    result: ScanResult, stack: list[_Block], logical: _Logical, function: str
) -> None:
    text = logical.text
    if re.match(r"elif\b", text):
        result.probes.append(Probe(logical.start, logical.ws + 4, "elif", function))
    elif re.match(r"else\s*:", text):
        _add_inline(result, logical, function)
    else:
        result.probes.append(Probe(logical.start, logical.ws, "stmt", function))
    if logical.opens_block():
        is_match = re.match(r"match\b", text) is not None
        stack.append(
            _Block(logical.indent, "match") if is_match else _Block(logical.indent)
        )


def probe_text(kind: ProbeKind, call: str) -> str:
    """Text inserted for a probe of [param kind] whose hit expression is [param call]."""
    if kind == "stmt":
        return f"{call}; "
    if kind == "elif":
        return f" {call} and"
    return f" {call};"


def instrument(source: str, const_name: str, first_id: int) -> tuple[str, list[Probe]]:
    """Returns [param source] with probes inserted, and its probes in id order.

    The probe of index ``k`` calls ``<const_name>.h(<first_id + k>)``; a logical line
    holds at most one probe, so insertions never shift each other. The caller
    appends the declaration of ``const_name`` to the file.
    """
    probes = scan(source).probes
    lines = source.split("\n")
    for offset, probe in enumerate(probes):
        call = f"{const_name}.h({first_id + offset})"
        text = lines[probe.line - 1]
        insert = probe_text(probe.kind, call)
        lines[probe.line - 1] = text[: probe.col] + insert + text[probe.col :]
    return "\n".join(lines), probes
