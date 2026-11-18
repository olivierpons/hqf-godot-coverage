"""Tests of gdcov.scanner: which lines get probes, of which form, and the rewrite."""

import pytest

from gdcov.scanner import (
    Function,
    Probe,
    _indent_width,
    _lex_line,
    _LexState,
    instrument,
    probe_text,
    scan,
)


def _lex(text: str) -> tuple[list[int], int, _LexState]:
    state = _LexState()
    line = _lex_line(text, state)
    return line.colons, line.last, state


@pytest.mark.parametrize(
    ("text", "colons", "last"),
    [
        (":", [0], 0),
        ("a:\r", [1], 1),
        ("a:\t ", [1], 1),
        ('"\\"":', [4], 4),
        ('r"\\":', [4], 4),
        ('"\\":r', [], 4),
        ('a = "x"', [], 6),
        ("f(a: b): # c: d", [7], 7),
        ("{k: v}:", [6], 6),
        ("a: X", [1], 3),
        ("X: a", [1], 3),
        ("(X:", [], 2),
        ("", [], -1),
        ("  # only", [], -1),
    ],
)
def test_lex_line(text: str, colons: list[int], last: int) -> None:
    assert _lex(text)[:2] == (colons, last)


def test_lex_line_state() -> None:
    assert _lex("a \\")[2] == _LexState(None, False, 0, True)
    assert _lex("a \\ \t")[2].backslash
    assert not _lex("a \\x")[2].backslash
    assert _lex("(a, [b")[2].depth == 2
    assert _lex("a))")[2].depth == 0
    assert _lex('"""abc')[2] == _LexState('"""', False, 0, False)
    assert _lex('x = """abc')[2] == _LexState('"""', False, 0, False)
    assert _lex('"\\')[:2] == ([], 1)
    assert _lex("r'abc")[2] == _LexState("'", True, 0, False)
    assert _lex("'a' + r'b' + 'c")[2] == _LexState("'", False, 0, False)
    state = _LexState(quote='"', raw=False, depth=1, backslash=True)
    line = _lex_line('end" ) :', state)
    assert (line.colons, state) == ([7], _LexState(None, False, 0, False))


def test_lex_state_continues() -> None:
    assert not _LexState().continues()
    assert _LexState(quote='"').continues()
    assert _LexState(depth=1).continues()
    assert _LexState(backslash=True).continues()


def test_indent_width() -> None:
    assert _indent_width("") == 0
    assert _indent_width("x") == 0
    assert _indent_width("\t\tx") == 8
    assert _indent_width("  \tx ") == 6
    assert _indent_width("\t") == 4


def test_code_at_column_zero_closes_a_function() -> None:
    source = "func f() -> void:\n\tpass\nx\n\tpass\n"
    assert [p.line for p in scan(source).probes] == [2]


def test_statement_column_counts_only_tabs_and_spaces() -> None:
    source = "func f() -> void:\n\t\x0cpass\n\tXa = 1\n"
    assert [(p.line, p.col) for p in scan(source).probes] == [(2, 1), (3, 1)]


def test_one_line_function_with_type_colon_is_inline() -> None:
    source = "func f(a: int) -> int: return a\nvar x: int = 1\n"
    assert scan(source).probes == [Probe(1, 22, "inline", "f")]


SAMPLE = """\
extends Node
## Doc.

var plain: int = compute()
var health: int = 3:
\tget:
\t\treturn health
\tset(value):
\t\thealth = value

func _ready() -> void:
\tvar n: int = 0  # comment: with colon
\tfor i: int in 3:
\t\tn += i
\tif n > 1:
\t\tpass
\telif n == 0:
\t\tprint("zero")
\telse:
\t\tprint("x")
\telse: print("y")
\tmatch n:
\t\t1, 2:
\t\t\tprint("small")
\t\t_: print("other")
\t@warning_ignore("unused")
\tvar f := func(y: int) -> int:
\t\treturn y
\tconnect("x", func() -> void:
\t\tprint("in lambda")
\t)

static func one() -> int: return 1

class Inner:
\tvar d: Dictionary = {
\t\t"k": 1,
\t}
\tfunc g() -> String:
\t\treturn "a: b # not a comment"
"""


def test_scan_probes_lines_kinds_and_functions() -> None:
    probes = scan(SAMPLE).probes
    assert [(p.line, p.kind, p.function) for p in probes] == [
        (7, "stmt", "health.get"),
        (9, "stmt", "health.set"),
        (12, "stmt", "_ready"),
        (13, "stmt", "_ready"),
        (14, "stmt", "_ready"),
        (15, "stmt", "_ready"),
        (16, "stmt", "_ready"),
        (17, "elif", "_ready"),
        (18, "stmt", "_ready"),
        (20, "stmt", "_ready"),
        (21, "inline", "_ready"),
        (22, "stmt", "_ready"),
        (24, "stmt", "_ready"),
        (25, "inline", "_ready"),
        (27, "stmt", "_ready"),
        (28, "stmt", "_ready"),
        (29, "stmt", "_ready"),
        (33, "inline", "one"),
        (40, "stmt", "Inner.g"),
    ]


def test_scan_columns() -> None:
    by_line = {p.line: p.col for p in scan(SAMPLE).probes}
    assert by_line[7] == 2
    assert by_line[12] == 1
    assert by_line[17] == 5
    assert by_line[21] == len("\telse:")
    assert by_line[25] == len("\t\t_:")
    assert by_line[33] == len("static func one() -> int:")


def test_scan_functions() -> None:
    assert scan(SAMPLE).functions == [
        Function("health.get", 6),
        Function("health.set", 8),
        Function("_ready", 11),
        Function("one", 33),
        Function("Inner.g", 39),
    ]


def test_instrument_keeps_line_count_and_inserts_calls() -> None:
    text, probes = instrument(SAMPLE, "_C", 10)
    lines = text.split("\n")
    assert len(lines) == len(SAMPLE.split("\n"))
    assert lines[6] == "\t\t_C.h(10); return health"
    assert lines[16] == "\telif _C.h(17) and n == 0:"
    assert lines[20] == '\telse: _C.h(20); print("y")'
    assert lines[32] == "static func one() -> int: _C.h(27); return 1"
    assert lines[39] == '\t\t_C.h(28); return "a: b # not a comment"'
    assert len(probes) == 19


def test_probe_text_forms() -> None:
    assert probe_text("stmt", "C.h(1)") == "C.h(1); "
    assert probe_text("elif", "C.h(1)") == " C.h(1) and"
    assert probe_text("inline", "C.h(1)") == " C.h(1);"


def test_multiline_strings_and_backslash_are_continuations() -> None:
    source = (
        "func f() -> void:\n"
        '\tvar s: String = """first\n'
        "func not_a_function():\n"
        '\tlast"""\n'
        "\tvar t: int = 1 + \\\n"
        "\t\t2\n"
        "\tvar u: String = 'it''s'\n"
        '\tvar r: String = r"a\\"\n'
        "\treturn\n"
    )
    result = scan(source)
    assert [p.line for p in result.probes] == [2, 5, 7, 8, 9]
    assert result.functions == [Function("f", 1)]


def test_escaped_quote_inside_string() -> None:
    source = 'func f() -> void:\n\tvar s: String = "a\\"b: (c"\n\tpass\n'
    assert [p.line for p in scan(source).probes] == [2, 3]


def test_triple_single_quotes() -> None:
    source = "func f() -> void:\n\tvar s: String = '''a\nb'''\n\tpass\n"
    assert [p.line for p in scan(source).probes] == [2, 4]


def test_multiline_signature_and_inline_body_on_later_line() -> None:
    source = "func f(\n\ta: int,\n) -> int: return a\nfunc g(\n\tb: int,\n) -> int:\n\treturn b\n"
    probes = scan(source).probes
    assert probes == [
        Probe(3, len(") -> int:"), "inline", "f"),
        Probe(7, 1, "stmt", "g"),
    ]


def test_brackets_never_go_negative() -> None:
    source = "func f() -> void:\n\tvar x: int = 1)\n\tpass\n"
    assert [p.line for p in scan(source).probes] == [2, 3]


def test_annotated_static_function_and_property_with_annotation() -> None:
    source = (
        "@export var speed: float = 1.0:\n"
        "\tset(v):\n"
        "\t\tspeed = v\n"
        '@rpc("any_peer") static func ping() -> void:\n'
        "\tpass\n"
    )
    result = scan(source)
    assert [(p.line, p.function) for p in result.probes] == [
        (3, "speed.set"),
        (5, "ping"),
    ]


def test_inline_accessor() -> None:
    source = "var x: int:\n\tget: return 1\n\tset(v): pass\n"
    probes = scan(source).probes
    assert [(p.line, p.kind, p.function, p.col) for p in probes] == [
        (2, "inline", "x.get", 5),
        (3, "inline", "x.set", 8),
    ]


def test_property_without_block_and_other_property_lines() -> None:
    source = (
        "var a: int\nvar b: int:\n\tget = _get_b\nfunc _get_b() -> int:\n\treturn 1\n"
    )
    result = scan(source)
    assert [(p.line, p.function) for p in result.probes] == [(5, "_get_b")]
    assert result.functions == [Function("_get_b", 4)]


def test_setter_and_getter_names_assigned_are_not_headers() -> None:
    source = "var a: int:\n\tset = _set_a, get = _get_a\nvar b: int:\n\tsetup = 1\n"
    assert scan(source).functions == []


def test_accessor_headers_with_spaces() -> None:
    source = "var a: int:\n\tget :\n\t\treturn 1\n\tset (v):\n\t\tpass\n"
    assert scan(source).functions == [Function("a.get", 2), Function("a.set", 4)]


def test_match_pattern_without_enclosing_function_is_ignored() -> None:
    source = "func f(n: int) -> void:\n\tmatch n:\n\t\t1: pass\n\t\t2:\n\t\t\tpass\n"
    probes = scan(source).probes
    assert [(p.line, p.kind) for p in probes] == [
        (2, "stmt"),
        (3, "inline"),
        (5, "stmt"),
    ]


def test_class_level_code_is_not_measured() -> None:
    source = "class A:\n\tvar x: int = 1\nclass B extends A:\n\tpass\nenum E { A, B }\n"
    assert scan(source).probes == []


def test_spaces_indentation() -> None:
    source = "func f() -> void:\n    if true:\n        pass\n    pass\nfunc g() -> void:\n  pass\n"
    probes = scan(source).probes
    assert [(p.line, p.col, p.function) for p in probes] == [
        (2, 4, "f"),
        (3, 8, "f"),
        (4, 4, "f"),
        (6, 2, "g"),
    ]


def test_mixed_tab_counts_as_four_columns() -> None:
    source = "func f() -> void:\n\tif true:\n\t    pass\n\tpass\n"
    probes = scan(source).probes
    assert [(p.line, p.col) for p in probes] == [(2, 1), (3, 5), (4, 1)]


def test_nested_inner_class_function_names() -> None:
    source = "class A:\n\tclass B:\n\t\tfunc f() -> void:\n\t\t\tpass\n"
    assert scan(source).probes == [Probe(4, 3, "stmt", "A.B.f")]


def test_else_with_spaces_and_elif_paren() -> None:
    source = "func f(x: int) -> void:\n\tif x:\n\t\tpass\n\telif(x > 1):\n\t\tpass\n\telse :\n\t\tpass\n"
    text, __ = instrument(source, "C", 0)
    assert text.split("\n")[3] == "\telif C.h(2) and(x > 1):"
    assert text.split("\n")[5] == "\telse :"


def test_elsewhere_is_a_statement_not_else() -> None:
    source = "func f() -> void:\n\telsewhere()\n\telifant()\n"
    assert [p.kind for p in scan(source).probes] == ["stmt", "stmt"]


def test_matchbox_is_not_a_match_block() -> None:
    source = "func f() -> void:\n\tif matchbox:\n\t\tpass\n"
    assert [p.kind for p in scan(source).probes] == ["stmt", "stmt"]


def test_two_probes_on_one_line_are_inserted_right_to_left() -> None:
    source = "func f() -> void:\n\tpass\n"
    text, __ = instrument(source, "C", 0)
    assert text == "func f() -> void:\n\tC.h(0); pass\n"


def test_comment_only_and_blank_lines_do_not_close_blocks() -> None:
    source = "func f() -> void:\n\tpass\n# top comment\n\n\tpass\n"
    assert [p.function for p in scan(source).probes] == ["f", "f"]


def test_backslash_inside_comment_is_not_a_continuation() -> None:
    source = "func f() -> void:\n\tpass # ends with \\\n\tpass\n"
    assert [p.line for p in scan(source).probes] == [2, 3]


def test_backslash_followed_by_code_is_not_a_continuation() -> None:
    source = (
        'func f() -> void:\n\tvar s: String = "x" + str(1) \\ \n\t\t+ "y"\n\tpass\n'
    )
    assert [p.line for p in scan(source).probes] == [2, 4]


def test_static_var_property_and_func_after_property() -> None:
    source = "static var s: int:\n\tget:\n\t\treturn 1\nfunc f() -> void:\n\tpass\n"
    assert [(p.line, p.function) for p in scan(source).probes] == [
        (3, "s.get"),
        (5, "f"),
    ]


def test_accessor_with_annotation_prefix_is_not_a_header() -> None:
    source = "var x: int:\n\tgetter_like = 1\n"
    assert scan(source) == scan(source)
    assert scan(source).functions == []


def test_lambda_statement_inside_match_branch() -> None:
    source = (
        "func f(n: int) -> void:\n"
        "\tmatch n:\n"
        "\t\t1:\n"
        "\t\t\tmatch n:\n"
        "\t\t\t\t1:\n"
        "\t\t\t\t\tpass\n"
    )
    assert [p.line for p in scan(source).probes] == [2, 4, 6]
