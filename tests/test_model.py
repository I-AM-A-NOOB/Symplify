# coding: utf-8
"""Behaviour tests for the calculation model and its viewmodels.

Run from the repository root:

    uv run python -m tests.test_model

The file is also pytest-compatible (`pytest tests/` once pytest is a dev
dependency), but needs no test framework: it is plain asserts plus a runner.

These tests lock the *contract*, including the parts that are deliberately
permissive — sympy's defaults are indulged, unknown symbols stay symbolic, and
juxtaposition means multiplication. Locking those on purpose is the point: a
change to the parser transformations or the error handling must show up here as
a diff instead of as a surprise in the app.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sympy import Integer, Matrix, Rational, Symbol

from PySide6.QtCore import QObject
from PySide6.QtGui import QTextDocument

from python.brackets import DEFAULT_COLORS, parse_colors, spans
from python.code_style import DEFAULT_STYLES, CodeSpan, Style, color_for, surface, theme
from python.code_style import spans as code_spans
from python.code_style import to_rich_text
from python.code_themes import FAMILIES, VSCODE_BRACKET_COLORS
from python.model.lexer import TokenKind, tokenize
from python.model.calculator import (
    Assignment,
    Calculator,
    ErrorKind,
    Failure,
    Success,
)
from python.model.variable import VariableManager, is_sympy_name, validate_name
from python.settings import DEFAULTS, SettingsStore
from python.viewmodel.history_viewmodel import HistoryModel
from python.viewmodel.main_viewmodel import MainViewModel
from python.viewmodel.search import (
    HistoryFilterModel,
    HistorySearchMode,
    VariableSearchMode,
    VariablesFilterModel,
)
from python.viewmodel.variables_viewmodel import VariablesModel

X = Symbol("x")


def temp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="symplify_test_"))


def history_role(vm, row, role):
    """Read one history role, so tests can inspect what a card will show."""
    return vm.history.data(vm.history.index(row, 0), role)


def evaluate(text, scope=None):
    """Run an expression request through a fresh Calculator."""
    return Calculator().evaluate(text, scope or {})


def ok(text, scope=None):
    """Assert an expression succeeded and return its value."""
    result = evaluate(text, scope)
    assert isinstance(result, Success), f"{text!r} unexpectedly failed: {result!r}"
    return result.value


def bad(text, kind, scope=None):
    """Assert an expression failed with ``kind`` and return the Failure."""
    result = evaluate(text, scope)
    assert isinstance(result, Failure), f"{text!r} unexpectedly succeeded: {result!r}"
    assert result.kind is kind, f"{text!r} -> {result.kind}, expected {kind}"
    return result


def assign(target, op, expression, scope=None):
    """Run an assignment request through a fresh Calculator."""
    return Calculator().assign(Assignment(target, op, expression), scope or {})


# --------------------------------------------------------------------------
# Expression language: the semantics we deliberately indulge
# --------------------------------------------------------------------------

def test_juxtaposition_is_multiplication():
    assert ok("2x") == 2 * X


def test_caret_is_power():
    assert ok("x^2") == X**2


def test_unknown_symbol_stays_symbolic():
    assert ok("z + 1") == Symbol("z") + 1


def test_known_functions_resolve():
    assert ok("integrate(x**2, x)") == X**3 / 3


def test_matrix_constructor_is_allowed():
    assert ok("Matrix([[1, 2], [3, 4]])") == Matrix([[1, 2], [3, 4]])


def test_scope_values_are_visible():
    assert ok("a + 1", {"a": Integer(2)}) == 3


def test_numeric_juxtaposition_is_not_a_call():
    assert ok("2(x + 1)") == 2 * (X + 1)


def test_shadowed_function_is_indulged():
    """A variable named `sin` makes sin(x) mean 5*x — permissive by design."""
    assert ok("sin(x)", {"sin": Integer(5)}) == 5 * X


def test_call_to_scoped_name_is_juxtaposition():
    """f(x) with f in scope resolves to a value, so it stays multiplication."""
    assert ok("f(x)", {"f": Integer(2)}) == 2 * X


# --------------------------------------------------------------------------
# Unknown calls: reported instead of silently rewritten into a product
# --------------------------------------------------------------------------

def test_unknown_call_is_reported():
    failure = bad("bar(2)", ErrorKind.UNKNOWN_NAME)
    assert failure.message == "unknown function 'bar'"


def test_unknown_call_hint_mentions_multiplication():
    assert "multiplication" in bad("bar(2)", ErrorKind.UNKNOWN_NAME).hint


def test_typo_gets_a_suggestion():
    assert "solve" in bad("sovle(x**2 - 4, x)", ErrorKind.UNKNOWN_NAME).hint


def test_only_the_first_unknown_call_is_reported():
    failure = bad("foo(1) + bar(2)", ErrorKind.UNKNOWN_NAME)
    assert failure.message == "unknown function 'foo'"


def test_unknown_symbol_alone_is_fine():
    assert ok("z") == Symbol("z")


# --------------------------------------------------------------------------
# Failures are classified
# --------------------------------------------------------------------------

def test_syntax_error():
    assert bad("x +", ErrorKind.SYNTAX).expression == "x +"


def test_empty_input():
    failure = bad("   ", ErrorKind.SYNTAX)
    assert failure.message == "nothing to evaluate"


def test_domain_error_is_internal_not_syntax():
    """A shape mismatch is sympy's domain error, not a typo in the input."""
    assert bad(
        "Matrix([[1, 2], [3, 4]]) + Matrix([[1, 2]])", ErrorKind.INTERNAL
    )


def test_success_keeps_provenance():
    assert ok("  x + 1  ") == X + 1
    assert evaluate("  x + 1  ").expression == "  x + 1  "


# --------------------------------------------------------------------------
# Assignment requests
# --------------------------------------------------------------------------

def test_plain_assignment():
    result = assign("y", "=", "3")
    assert isinstance(result, Success) and result.value == 3
    assert result.expression == "y = 3"


def test_assignment_rhs_uses_the_expression_language():
    """The right-hand side stays text, so `2y` means 2*y."""
    assert assign("z", "=", "2y", {"y": Integer(3)}).value == 6


def test_augmented_assignment_needs_an_existing_variable():
    failure = assign("x", "+=", "1")
    assert failure.kind is ErrorKind.UNKNOWN_NAME
    assert "'x' is not defined" == failure.message


def test_augmented_operators():
    scope = {"y": Integer(3)}
    assert assign("y", "+=", "1", scope).value == 4
    assert assign("y", "-=", "1", scope).value == 2
    assert assign("y", "*=", "2", scope).value == 6
    assert assign("y", "/=", "2", scope).value == Rational(3, 2)
    assert assign("y", "%=", "2", scope).value == 1


def test_augmented_assignment_does_not_become_self_referential():
    """The old string splice stored `x = x + 1` for `x += 1`."""
    result = assign("x", "+=", "1", {"x": Integer(1)})
    assert result.value == 2


def test_invalid_target_is_rejected_before_evaluating():
    failure = assign("1x", "=", "5")
    assert failure.kind is ErrorKind.INVALID_NAME
    assert failure.expression == "1x = 5"


def test_keyword_target_is_rejected():
    assert assign("lambda", "=", "1").kind is ErrorKind.INVALID_NAME


def test_unsupported_operator():
    assert assign("y", "**=", "2").kind is ErrorKind.UNSUPPORTED


def test_assignment_failure_propagates_the_parse_error():
    assert assign("y", "=", "x +").kind is ErrorKind.SYNTAX


# --------------------------------------------------------------------------
# Names
# --------------------------------------------------------------------------

def test_validate_name_table():
    for name in ("x", "_a", "x1", "λ"):
        assert validate_name(name), name
    for name in ("1x", "lambda", "", "a b", "a-b"):
        assert not validate_name(name), name


def test_validate_name_rejects_unparseable_numerics():
    """`isalnum` admits superscripts/fractions, but sympy's tokenizer does not:
    a name that passes validation must stay referenceable in an expression."""
    assert not validate_name("x²")   # superscript two (No) is not an identifier
    assert not validate_name("x½")   # vulgar fraction (No) either
    assert validate_name("x٣")       # an Arabic-Indic digit (Nd) is a real one


def test_reserved_names_table():
    for name in ("solve", "sin", "Matrix", "E", "pi", "S"):
        assert is_sympy_name(name), name
    # Plain module attributes are not names an expression could collide with
    # (the old hasattr(sympy, name) probe flagged these).
    for name in ("x", "_a", "core", "printing"):
        assert not is_sympy_name(name), name


def test_variable_manager_crud():
    manager = VariableManager()
    manager.save("a", Integer(1))
    manager.save("b", Integer(2))
    assert manager.names() == ["a", "b"]
    assert manager.list_all() == {"a": Integer(1), "b": Integer(2)}
    assert manager.rename("a", "c") is True
    assert manager.names() == ["c", "b"]
    assert manager.delete("c") is True
    assert manager.exists("c") is False
    manager.clear()
    assert manager.list_all() == {}


def test_invalid_entries_are_excluded_from_evaluation():
    manager = VariableManager()
    manager.save("a", Integer(1))
    manager.save_invalid("b", "x +")
    assert manager.list_all() == {"a": Integer(1)}
    assert manager.entry("b").type_label == "Invalid"
    assert manager.entry("b").expr_str == "x +"


# --------------------------------------------------------------------------
# ViewModel invariants: a rejected write leaves no variable behind, but it does
# leave an error card (the input has to come back so a typo can be fixed)
# --------------------------------------------------------------------------

def new_vm():
    """A root viewmodel over a throwaway settings store (temp dir, no Qt app)."""
    store = SettingsStore(temp_dir() / "config.yaml")
    store.load()
    return MainViewModel(store)


def test_rejected_assignment_adds_an_error_card_and_no_variable():
    vm = new_vm()
    vm.calculator.calculateAssign("1x", "=", "5")
    assert vm.calculator.isError is True
    assert "invalid variable name" in vm.calculator.errorMessage
    assert vm.variables.model.count == 0
    assert vm.history.count == 1
    assert history_role(vm, 0, HistoryModel.ErrorRole) != ""
    assert history_role(vm, 0, HistoryModel.ResultRole) == ""


def test_undefined_augmented_assignment_adds_an_error_card():
    vm = new_vm()
    vm.calculator.calculateAssign("x", "+=", "1")
    assert vm.calculator.isError is True
    assert vm.variables.model.count == 0
    assert vm.history.count == 1
    assert "is not defined" in history_role(vm, 0, HistoryModel.ErrorRole)


def test_failed_code_request_records_input_and_reason():
    vm = new_vm()
    vm.calculator.calculate("bar(2)")
    assert vm.history.count == 1
    assert history_role(vm, 0, HistoryModel.ExpressionRole) == "bar(2)"
    assert history_role(vm, 0, HistoryModel.ModeRole) == "Code"
    error = history_role(vm, 0, HistoryModel.ErrorRole)
    assert "unknown function 'bar'" in error
    assert "multiplication" in error  # the hint travels with the message


def test_failed_assign_card_can_be_sent_back():
    """The card keeps name/op/expression, so Send to input can restore them."""
    vm = new_vm()
    vm.calculator.calculateAssign("y", "+=", "2z")
    assert vm.history.count == 1
    assert history_role(vm, 0, HistoryModel.ModeRole) == "Assign"
    assert history_role(vm, 0, HistoryModel.NameRole) == "y"
    assert history_role(vm, 0, HistoryModel.OpRole) == "+="
    assert history_role(vm, 0, HistoryModel.ExpressionRole) == "2z"
    assert history_role(vm, 0, HistoryModel.ErrorRole) != ""


def test_successful_assignment_writes_history_and_variable():
    vm = new_vm()
    vm.calculator.calculateAssign("y", "=", "3")
    vm.calculator.calculateAssign("y", "+=", "1")
    assert vm.history.count == 2
    assert vm.variables.model.count == 1
    assert vm.variables.model.cellAt(0, 0) == "y"
    assert vm.variables.model.cellAt(0, 1) == "4"
    assert vm.variables.model.cellAt(0, 2) == "Integer"
    assert history_role(vm, 0, HistoryModel.ErrorRole) == ""
    assert history_role(vm, 0, HistoryModel.ResultRole) == "4"


def test_unparsable_value_is_kept_as_an_invalid_entry():
    vm = new_vm()
    vm.calculator.calculateAssign("k", "=", "x +")
    assert vm.calculator.isError is True
    assert vm.variables.model.count == 1
    assert vm.variables.model.cellAt(0, 2) == "Invalid"
    assert vm.history.count == 1
    assert history_role(vm, 0, HistoryModel.ErrorRole) != ""


def test_code_mode_still_selects_and_reports():
    vm = new_vm()
    vm.calculator.calculate("2 + 2")
    assert vm.calculator.resultText == "4"
    assert vm.calculator.isError is False
    assert vm.history.count == 1


# --------------------------------------------------------------------------
# The variables table's inline edit path (also a write route)
#
# NOTE: keep the viewmodel in a variable. Chaining a PySide6 Property off a
# temporary (`MainViewModel().variables.model`) hands back the Property
# descriptor instead of the model on the Python side; the metaobject path QML
# uses is unaffected.
# --------------------------------------------------------------------------

def test_inline_edit_parses_and_saves():
    vm = new_vm()
    model = vm.variables.model
    model.save("a", Integer(1))
    assert model.setData(model.index(0, 1), "a + 1") is True
    assert model.cellAt(0, 1) == "2"
    assert model.cellAt(0, 2) == "Integer"


def test_inline_edit_failure_keeps_the_raw_input():
    vm = new_vm()
    model = vm.variables.model
    model.save("a", Integer(1))
    assert model.setData(model.index(0, 1), "x +") is True
    assert model.cellAt(0, 1) == "x +"
    assert model.cellAt(0, 2) == "Invalid"


def test_inline_rename():
    vm = new_vm()
    model = vm.variables.model
    model.save("a", Integer(1))
    assert model.setData(model.index(0, 0), "b") is True
    assert model.cellAt(0, 0) == "b"
    assert model.setData(model.index(0, 0), "1x") is False
    assert model.cellAt(0, 0) == "b"


# --------------------------------------------------------------------------
# Search filters (the pages' search boxes)
# --------------------------------------------------------------------------

def variable_filter():
    """A filter over three variables: alpha = 1, beta = 2, radius = 1/3."""
    manager = VariableManager()
    source = VariablesModel(manager)
    for name, value in [("alpha", Integer(1)), ("beta", Integer(2)),
                        ("radius", Rational(1, 3))]:
        source.save(name, value)
    model = VariablesFilterModel()
    model.setSourceModel(source)
    return model, source


def names(model):
    return [model.nameAt(row) for row in range(model.rowCount())]


def test_search_mode_order_matches_the_ui():
    """The combo boxes pass their index straight through, so order is a contract."""
    assert [m.name for m in VariableSearchMode] == ["FUZZY", "NAME", "VALUE", "TYPE"]
    assert [m.name for m in HistorySearchMode] == ["FUZZY", "EXPRESSION", "RESULT"]


def test_variable_filter_empty_query_shows_everything():
    model, _ = variable_filter()
    assert names(model) == ["alpha", "beta", "radius"]
    model.searchText = "zzz"
    assert names(model) == []
    model.searchText = ""
    assert names(model) == ["alpha", "beta", "radius"]


def test_variable_filter_is_case_insensitive():
    model, _ = variable_filter()
    model.searchText = "ALP"
    assert names(model) == ["alpha"]


def test_variable_filter_modes():
    model, _ = variable_filter()
    model.searchText = "2"
    assert names(model) == ["beta"]                  # fuzzy: value only
    model.searchMode = VariableSearchMode.NAME.value
    assert names(model) == []                        # no name holds 2
    model.searchMode = VariableSearchMode.VALUE.value
    assert names(model) == ["beta"]
    model.searchMode = VariableSearchMode.TYPE.value
    model.searchText = "rat"
    assert names(model) == ["radius"]                # Rational
    model.searchMode = VariableSearchMode.FUZZY.value
    assert names(model) == ["radius"]


def test_count_is_a_notifying_property():
    """QML binds to `count` reactively; it must announce every size change so a
    Clear button / empty-state text re-evaluates without a page rebuild."""
    history = HistoryModel()
    h_sizes = []
    history.countChanged.connect(lambda: h_sizes.append(history.count))
    history.add_item("x + 1", "x + 1")
    history.clear()
    assert h_sizes == [1, 0]

    variables = VariablesModel(VariableManager())
    v_sizes = []
    variables.countChanged.connect(lambda: v_sizes.append(variables.count))
    variables.save("x", Integer(1))
    variables.remove("x")
    assert v_sizes == [1, 0]


def test_brackets_take_a_layer_from_their_nesting_depth():
    """A pair shares a colour, and each level of nesting steps the layer."""
    assert [(start, layer) for start, _, layer in spans("(a[b{c}])")] == [
        (0, 0), (2, 1), (4, 2), (6, 2), (7, 1), (8, 0),
    ]


def test_brackets_cycle_through_the_palette():
    """Past the last colour the layers wrap, so deep nesting still alternates."""
    assert [layer for _, _, layer in spans("((((((x))))))")] == [0, 1, 2, 3, 4, 5, 5, 4, 3, 2, 1, 0]


def test_brackets_without_a_partner_are_errors_and_shift_nothing():
    """A stray bracket gets no layer — and must not take one from its neighbours."""
    assert spans(")[x]") == [(0, 1, None), (1, 1, 0), (3, 1, 0)]
    assert spans("(a") == [(0, 1, None)]          # never closed
    assert spans("a)b") == [(1, 1, None)]         # never opened


def test_brackets_reach_across_lines():
    """An expression may be typed over several lines; the pair still matches."""
    assert spans("(a\nb)") == [(0, 1, 0), (4, 1, 0)]


def test_bracket_markup_escapes_the_expression_around_the_spans():
    """The result feeds a rich-text `Text`, so the rest of the line is escaped."""
    assert to_rich_text("a < b & (c)") == (
        'a &lt; b &amp; '
        '<span style="color:#ff6b6b;">(</span>c<span style="color:#ff6b6b;">)</span>'
    )
    assert to_rich_text("") == ""


def test_lexer_covers_the_expression_with_tokens():
    assert [(token.start, token.length, token.kind) for token in tokenize("2*x + 1")] == [
        (0, 1, TokenKind.NUMBER),
        (1, 1, TokenKind.OPERATOR),
        (2, 1, TokenKind.NAME),
        (3, 1, TokenKind.SPACE),
        (4, 1, TokenKind.OPERATOR),
        (5, 1, TokenKind.SPACE),
        (6, 1, TokenKind.NUMBER),
    ]


def test_lexer_takes_the_longest_operator():
    """`**` must not lex as two `*`, or the colouring would split a power."""
    assert [(token.length, token.kind) for token in tokenize("a**b")] == [
        (1, TokenKind.NAME),
        (2, TokenKind.OPERATOR),
        (1, TokenKind.NAME),
    ]
    assert [(token.length, token.kind) for token in tokenize("a^b")] == [
        (1, TokenKind.NAME),
        (1, TokenKind.OPERATOR),
        (1, TokenKind.NAME),
    ]


def _names(text, scope=None):
    """The name-ish tokens of ``text`` as ``{source: kind}``."""
    wanted = (TokenKind.NAME, TokenKind.VARIABLE, TokenKind.CALLABLE, TokenKind.CONSTANT)
    return {
        text[token.start:token.start + token.length]: token.kind
        for token in tokenize(text, scope)
        if token.kind in wanted
    }


def test_lexer_resolves_names_against_the_scope():
    """A stored variable, a SymPy constant, a callable and a free symbol are
    four different colours — resolved in the order the parser resolves them."""
    assert _names("x + pi + sin(y)", {"x": Integer(1)}) == {
        "x": TokenKind.VARIABLE,
        "pi": TokenKind.CONSTANT,
        "sin": TokenKind.CALLABLE,
        "y": TokenKind.NAME,
    }


def test_lexer_follows_python_identifier_rules():
    """`λ` is a name, `²` is not part of one — the rule the parser tokenizes by."""
    assert [(token.kind, token.length) for token in tokenize("λ + x²")] == [
        (TokenKind.NAME, 1),
        (TokenKind.SPACE, 1),
        (TokenKind.OPERATOR, 1),
        (TokenKind.SPACE, 1),
        (TokenKind.NAME, 1),
        (TokenKind.UNKNOWN, 1),
    ]


def test_code_spans_merge_names_brackets_and_lexer_styles():
    """One span list for both renderers, brackets sitting on top of the text.

    A free symbol contributes nothing (its style is the control's own ink), and
    so does whitespace — but the operator is classified, and whether it gets
    painted is the palette's decision, not this function's.
    """
    assert [(span.start, span.style, span.layer) for span in code_spans("(1 + x)")] == [
        (0, Style.BRACKET, 0),
        (1, Style.NUMBER, None),
        (3, Style.OPERATOR, None),
        (6, Style.BRACKET, 0),
    ]


def test_code_markup_paints_the_merged_spans():
    """The read-only renderer paints exactly what the highlighter would."""
    assert to_rich_text("(1)") == (
        '<span style="color:#ff6b6b;">(</span>'
        "1"
        '<span style="color:#ff6b6b;">)</span>'
    )


def test_a_supplied_palette_paints_the_kinds():
    """The classification is always there; the colours are the caller's to set,
    which is what lets a themed palette (or Pygments) come later."""
    assert to_rich_text("(1)", styles={Style.NUMBER: "#123456"}) == (
        '<span style="color:#ff6b6b;">(</span>'
        '<span style="color:#123456;">1</span>'
        '<span style="color:#ff6b6b;">)</span>'
    )


def test_every_theme_family_answers_for_both_sides():
    """A family that cannot answer for one theme would leave the code bare the
    moment the UI flips — which is the whole point of pairing them."""
    for family, label in FAMILIES:
        for dark in (True, False):
            styles, brackets = theme(family, dark)
            side = "dark" if dark else "light"
            assert styles, f"{family} ({label}) has no {side} palette"
            assert all(color.startswith("#") for color in styles.values())
            assert all(color.startswith("#") for color in brackets), family


def test_a_theme_family_colours_the_kinds():
    """Spot checks against the extracted data. Dark+ numbers are its #b5cea8 —
    the same colour that theme gives its own `numberLiteral` semantic token —
    and Atom One Light's operators are its #a626a4, which One Dark does not name
    at all: a family may answer for a kind its sibling leaves alone."""
    one_dark, _ = theme("one", True)
    assert one_dark[Style.NUMBER] == "#d19a66"
    assert one_dark[Style.CALLABLE] == "#61afef"
    assert one_dark[Style.VARIABLE] == "#abb2bf"     # One Dark names it the foreground
    one_light, _ = theme("one", False)
    assert one_light[Style.OPERATOR] == "#a626a4"    # which One Dark does not name

    default, _ = theme("default", True)
    assert default[Style.NUMBER] == "#b5cea8"
    assert default[Style.CALLABLE] == "#569cd6"

    solarized, _ = theme("solarized", True)
    assert solarized[Style.CONSTANT] == "#b58900"


def test_a_family_that_names_its_own_bracket_colours_keeps_them():
    """Solarized brings its own editorBracketHighlight; its light half does not,
    and that half then follows VS Code the same way the rest of them do."""
    _, dark = theme("solarized", True)
    assert dark == ("#cdcdcd", "#b58900", "#d33682")
    _, light = theme("solarized", False)
    assert light == VSCODE_BRACKET_COLORS["light"]


def test_an_unknown_family_falls_back_instead_of_raising():
    """A config file can name a family this build does not have."""
    styles, brackets = theme("not-a-family", True)
    assert styles == DEFAULT_STYLES
    assert brackets == VSCODE_BRACKET_COLORS["dark"]


def test_the_family_reaches_the_renderer():
    """A kind the palette mentions is painted; one it omits is left alone."""
    dark, _ = theme("default", True)
    assert '<span style="color:#b5cea8;">1</span>' in to_rich_text("1", styles=dark)
    assert "<span" not in to_rich_text("x", styles=dark)        # a free symbol
    # Catppuccin names no `invalid`, so an unknown token stays the control's own.
    styles, brackets = theme("catppuccin", True)
    assert color_for(CodeSpan(0, 1, Style.UNKNOWN, None), styles, brackets) is None


class StubTextDocument(QObject):
    """What a QML ``TextArea.textDocument`` stands in for.

    The highlighter needs an object whose ``textDocument()`` hands back the
    ``QTextDocument`` the item edits; a ``QQuickTextDocument`` cannot be built
    from Python.
    """

    def __init__(self, text):
        super().__init__()
        self.doc = QTextDocument()
        self.doc.setPlainText(text)

    def textDocument(self):
        return self.doc

    def colors(self):
        """The colours painted on the first block, in text order."""
        return [entry.format.foreground().color().name()
                for entry in self.doc.firstBlock().layout().formats()]


def test_attaching_the_colouring_paints_the_named_family():
    """The path the app actually takes: the page hands over its document, the
    settings name the family, and the document comes back coloured.

    This is the seam the palette tests cannot see, and it is the one that broke:
    the slot read the settings through the wrong object, so every call raised
    inside QML, every input stayed uncoloured, and the suite stayed green.
    """
    store = SettingsStore(temp_dir() / "config.yaml")
    store.load()
    store.set("appearance.code_theme", "solarized")
    vm = MainViewModel(store)

    target = StubTextDocument("(1)")
    vm.attachCodeHighlighting(target, True)

    # Read the colours back off the document itself: the brackets take Solarized's
    # first bracket colour and the number its `constant.numeric`.
    colors = target.colors()
    assert "#cdcdcd" in colors, colors          # the bracketed pair
    assert "#d33682" in colors, colors          # the digit


def test_a_family_with_no_bracket_colours_follows_vscode():
    """A family that names no bracket colours still colourises brackets.

    Atom One is the default family and carries no ``editorBracketHighlight``, so
    following the code theme means VS Code's *registered defaults* for the kind —
    which is what VS Code itself does there — rather than a palette of our own.
    The seam must also not raise, because the highlighter recomputes *before*
    ``rehighlight()``: an exception there leaves the document painted with the
    previous text's formats and kills every later refresh (typing, pasting, a
    theme switch), which is exactly how the app lost its bracket colours and its
    highlighting at once.
    """
    store = SettingsStore(temp_dir() / "config.yaml")
    store.load()
    assert store.get("appearance.code_theme") == "one"      # the default family
    assert store.get("appearance.bracket_mode") == "theme"
    vm = MainViewModel(store)

    target = StubTextDocument("((1))")
    vm.attachCodeHighlighting(target, True)

    expected = VSCODE_BRACKET_COLORS["dark"]
    colors = target.colors()
    # Both ends of a pair share a colour, and the nesting steps the layer.
    assert colors[:2] == [expected[0], expected[1]], colors
    assert colors[-2:] == [expected[1], expected[0]], colors


def test_the_renderers_still_supply_a_palette_that_is_passed_none():
    """``color_for`` keeps a last-resort palette for a caller that passes none.

    ``theme()`` always answers with colours now (the family's own, or VS Code's
    defaults), so this is the seam a *direct* caller can still fall through — and
    reading an empty sequence as "a palette of zero colours" is the
    ZeroDivisionError that took the whole refresh path down with it."""
    styles, brackets = theme("one", True)
    assert brackets == VSCODE_BRACKET_COLORS["dark"]
    assert color_for(CodeSpan(0, 1, Style.BRACKET, 0), styles, ()) == DEFAULT_COLORS[0]
    assert DEFAULT_COLORS[0] in to_rich_text("(a)", styles=styles, bracket_colors=())


def test_a_custom_bracket_list_overrides_the_theme_and_keeps_only_what_it_can_use():
    """The setting's two modes, and what happens to a list that is half-typed."""
    vm = new_vm()
    assert parse_colors(" #FF0000 , nope, #00ff00 ,") == ("#ff0000", "#00ff00")

    # Following the code theme is the default; the family names none, so this is
    # VS Code's dark set.
    assert VSCODE_BRACKET_COLORS["dark"][0] in vm.highlighted("()", True)

    vm.settings.bracketMode = "custom"
    vm.settings.bracketColors = "#FF0000, nope, #00ff00"
    # The store normalises what it keeps, so the field shows what will be painted.
    assert vm.settings.bracketColors == "#ff0000,#00ff00"

    painted = vm.highlighted("(())", True)
    assert "#ff0000" in painted and "#00ff00" in painted
    assert VSCODE_BRACKET_COLORS["dark"][0] not in painted

    # A list that keeps nothing is repaired to the default palette — the same
    # rainbow `color_for` falls back to — so Custom never silently turns into
    # "follow the theme", and the field shows what is painted.
    vm.settings.bracketColors = "junk"
    assert vm.settings.bracketColors == ",".join(DEFAULT_COLORS)
    painted = vm.highlighted("(())", True)
    assert DEFAULT_COLORS[0] in painted and DEFAULT_COLORS[1] in painted
    assert VSCODE_BRACKET_COLORS["dark"][0] not in painted


def test_the_code_theme_setting_is_written_and_remembered():
    """The settings page's radio group writes this key, and reading it back is
    what the next page build colours from."""
    store = SettingsStore(temp_dir() / "config.yaml")
    store.load()
    vm = MainViewModel(store)
    settings = vm.settings
    assert settings.codeTheme == DEFAULTS["appearance"]["code_theme"]
    settings.codeTheme = "solarized"
    assert settings.codeTheme == "solarized"
    assert store.get("appearance.code_theme") == "solarized"


def test_every_family_carries_a_surface_for_both_sides():
    """The code box is painted in the family's own ``editor.background`` and text
    the palette leaves unpainted in its ``editor.foreground``, so a family that
    could not answer would leave a plainly UI-coloured box around themed code.

    Answering with ``""`` is allowed and meaningful — High Contrast Light states
    neither — which is why a consumer reads it as "no opinion", not as a value."""
    for family, label in FAMILIES:
        for dark in (True, False):
            background, ink, placeholder = surface(family, dark)
            assert isinstance(background, str), (family, label)
            assert isinstance(ink, str), (family, label)
            assert isinstance(placeholder, str), (family, label)
    assert surface("one", True) == ("#282c34", "#abb2bf", "#7a7c80")     # VSCode's derivation
    assert surface("solarized", False) == ("#fdf6e3", "#657b83", "#8f9b9a")   # the theme's own
    assert surface("highcontrast", False) == ("", "", "")    # nothing to say
    assert surface("not-a-family", True) == ("", "", "")


def test_the_highlighted_markup_survives_a_name():
    """The read-only labels' renderer, on an expression that *has* a name.

    `to_rich_text` takes the scope as a mapping, while the highlighter takes the
    provider so it can ask again on each keystroke. Handing the provider to both is
    the bug this holds down: the lexer then evaluates `name in <bound method>` and
    raises inside the QML binding. An expression of digits and brackets never
    reaches that lookup, which is exactly why the History cards looked right while
    every label holding a name was blank.
    """
    store = SettingsStore(temp_dir() / "config.yaml")
    store.load()
    vm = MainViewModel(store)
    markup = vm.highlighted("sin(x) + pi", True)          # callable, name, constant
    assert "<span" in markup, markup


def test_the_settings_viewmodel_hands_qml_the_surface():
    """What the page binds to: ``codeSurface(dark)`` is the map ``CodeSurface.qml``
    paints from. The argument is the *active* theme, as it is for the highlighter."""
    store = SettingsStore(temp_dir() / "config.yaml")
    store.load()
    vm = MainViewModel(store)
    settings = vm.settings
    settings.codeTheme = "solarized"
    assert settings.codeSurface(True) == {
        "background": "#002b36", "ink": "#839496", "placeholder": "#627a7d"}
    assert settings.codeSurface(False) == {
        "background": "#fdf6e3", "ink": "#657b83", "placeholder": "#8f9b9a"}


def test_variable_filter_reacts_to_later_writes():
    """An active query must hide a new non-matching row and drop matches on edit."""
    model, source = variable_filter()
    model.searchText = "alp"
    assert names(model) == ["alpha"]
    source.save("alphabet", Integer(0))              # matches -> appears
    assert names(model) == ["alpha", "alphabet"]
    source.save("gamma", Integer(0))                 # no match -> stays hidden
    assert names(model) == ["alpha", "alphabet"]
    assert source.count == 5
    source.save("alpha", Integer(9))                 # still matches -> stays
    assert names(model) == ["alpha", "alphabet"]
    model.searchText = "9"
    assert names(model) == ["alpha"]
    source.save("alpha", Integer(1))                 # stops matching -> dropped
    assert names(model) == []


def test_variable_filter_picks_up_removals_while_filtered():
    model, source = variable_filter()
    model.searchText = "a"
    assert names(model) == ["alpha", "beta", "radius"]
    source.remove("beta")
    assert names(model) == ["alpha", "radius"]


def history_filter():
    """A filter over an ok entry, an assignment and an error entry."""
    source = HistoryModel()
    source.add_item("x + 1", "x + 1", "Code", latex="x + 1")
    source.add_item("9", "9", "Assign", latex="9", name="y", op="=")
    source.add_item("bar(2)", "", "Code", error="unknown function 'bar'")
    model = HistoryFilterModel()
    model.setSourceModel(source)
    return model, source


def expressions(model):
    return [model.data(model.index(row, 0), HistoryModel.ExpressionRole)
            for row in range(model.rowCount())]


def test_history_filter_modes():
    model, _ = history_filter()
    assert expressions(model) == ["bar(2)", "9", "x + 1"]   # newest first

    # Expression mode searches the input line as the card renders it, so an
    # assignment is one whole `name op expression` statement and its name is
    # reachable through it (no separate name mode).
    model.searchMode = HistorySearchMode.EXPRESSION.value
    model.searchText = "y ="
    assert expressions(model) == ["9"]
    model.searchText = "y"
    assert expressions(model) == ["9"]
    model.searchText = "x + 1"
    assert expressions(model) == ["x + 1"]
    model.searchText = "unknown"                # a failure is not an expression
    assert expressions(model) == []

    # Result mode covers successes and failures alike.
    model.searchMode = HistorySearchMode.RESULT.value
    model.searchText = "x + 1"
    assert expressions(model) == ["x + 1"]
    model.searchText = "9"
    assert expressions(model) == ["9"]
    model.searchText = "unknown"
    assert expressions(model) == ["bar(2)"]
    model.searchText = "y ="                    # an expression, not a result
    assert expressions(model) == []


def test_history_filter_fuzzy_covers_every_field():
    model, _ = history_filter()
    model.searchText = "unknown"                      # the failure text
    assert expressions(model) == ["bar(2)"]
    model.searchText = "y"                            # the assignment statement
    assert expressions(model) == ["9"]
    model.searchText = ""                             # the computed result
    assert len(expressions(model)) == 3
    model.searchText = "x + 1"
    assert expressions(model) == ["x + 1"]


def test_history_filter_sees_new_entries():
    model, source = history_filter()
    model.searchText = "function"
    assert expressions(model) == ["bar(2)"]
    source.add_item("foo(1)", "", "Code", error="unknown function 'foo'")
    assert expressions(model) == ["foo(1)", "bar(2)"]
    source.add_item("2 + 2", "4", "Code", latex="4")   # no match -> hidden
    assert expressions(model) == ["foo(1)", "bar(2)"]
    source.clear()
    assert expressions(model) == []


def main() -> int:
    """Run every test_* function in this module."""
    tests = sorted(
        (name, obj)
        for name, obj in globals().items()
        if name.startswith("test_") and callable(obj)
    )
    failures = []
    for name, fn in tests:
        try:
            fn()
        except Exception as exc:
            failures.append(name)
            print(f"FAIL  {name}\n      {type(exc).__name__}: {exc}")
        else:
            print(f"PASS  {name}")
    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
