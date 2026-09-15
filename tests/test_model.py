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

from python.model.calculator import (
    Assignment,
    Calculator,
    ErrorKind,
    Failure,
    Success,
)
from python.model.variable import VariableManager, is_sympy_name, validate_name
from python.settings import SettingsStore
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
