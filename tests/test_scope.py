"""Compute-side scope cache and ``srepr`` restoration tests.

Run from the repository root:

    uv run python -m tests.test_scope

The cache is tested with a fake restorer, so its revision bookkeeping and
"parse only what changed" rule are independent of SymPy. The restoration corpus
then checks the one real SymPy dependency the worker uses.
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import sympy as sp  # noqa: E402

from python.model.srepr import SreprError, restore_srepr  # noqa: E402
from python.scope_cache import ScopeCache  # noqa: E402
from python.worker_protocol import (  # noqa: E402
    ScopeChange,
    ScopeDelta,
    ScopeGapError,
    ScopeSnapshot,
    ScopeStaleError,
    StoreEntry,
)

X = sp.Symbol("x")


def entry(name, revision, text=None, *, valid=True):
    """A StoreEntry whose srepr is ``text`` (a fake string unless overwritten)."""
    return StoreEntry(
        name=name,
        srepr=(text if text is not None else f"S:{name}") if valid else "",
        display=name,
        type_label="Symbol" if valid else "Invalid",
        latex="",
        revision=revision,
        valid=valid,
    )


def recorder():
    calls = []

    def restore(text):
        calls.append(text)
        return f"obj:{text}"

    return calls, restore


def test_a_snapshot_restores_every_valid_entry_once():
    calls, restore = recorder()
    cache = ScopeCache(restore)
    snapshot = ScopeSnapshot(
        3,
        (
            entry("x", 1, "X"),
            entry("y", 2, "Y"),
            entry("bad", 3, valid=False),
        ),
    )

    cache.restore(snapshot)

    assert calls == ["X", "Y"]
    assert cache.revision == 3
    assert cache.scope() == {"x": "obj:X", "y": "obj:Y"}
    assert cache.entry("bad") is None


def test_a_delta_restores_only_the_changed_entries():
    calls, restore = recorder()
    cache = ScopeCache(restore)
    cache.restore(ScopeSnapshot(1, (entry("x", 1, "X"), entry("y", 1, "Y"))))
    calls.clear()

    cache.apply(
        ScopeDelta(
            1,
            3,
            (
                ScopeChange("x", 2, entry("x", 2, "X2")),
                ScopeChange("z", 3, entry("z", 3, "Z")),
            ),
        )
    )

    assert calls == ["X2", "Z"]
    assert cache.revision == 3
    assert cache.scope() == {"x": "obj:X2", "y": "obj:Y", "z": "obj:Z"}


def test_a_delta_removes_tombstones_and_invalid_entries():
    calls, restore = recorder()
    cache = ScopeCache(restore)
    cache.restore(
        ScopeSnapshot(
            2,
            (entry("x", 1, "X"), entry("y", 2, "Y")),
        )
    )
    calls.clear()

    cache.apply(
        ScopeDelta(
            2,
            4,
            (
                ScopeChange("x", 3, None),
                ScopeChange("y", 4, entry("y", 4, valid=False)),
            ),
        )
    )

    assert calls == []
    assert cache.revision == 4
    assert cache.scope() == {}


def test_a_stale_or_gapped_delta_does_not_change_the_cache():
    calls, restore = recorder()
    cache = ScopeCache(restore)
    snapshot = ScopeSnapshot(2, (entry("x", 2, "X"),))
    cache.restore(snapshot)
    calls.clear()

    for delta in (
        ScopeDelta(1, 3, (ScopeChange("x", 3, entry("x", 3, "X3")),)),
        ScopeDelta(3, 4, (ScopeChange("x", 4, entry("x", 4, "X4")),)),
    ):
        try:
            cache.apply(delta)
        except (ScopeStaleError, ScopeGapError):
            pass
        else:
            raise AssertionError("a stale/gapped delta was accepted")

    assert calls == []
    assert cache.revision == 2
    assert cache.scope() == {"x": "obj:X"}


def test_a_failed_restore_does_not_partially_update_the_cache():
    def restore(text):
        if text == "bad":
            raise SreprError("cannot restore")
        return f"obj:{text}"

    cache = ScopeCache(restore)
    cache.restore(ScopeSnapshot(1, (entry("x", 1, "X"),)))

    try:
        cache.apply(
            ScopeDelta(
                1,
                3,
                (
                    ScopeChange("x", 2, entry("x", 2, "GOOD")),
                    ScopeChange("y", 3, entry("y", 3, "bad")),
                ),
            )
        )
    except SreprError:
        pass
    else:
        raise AssertionError("a failed restore was accepted")

    assert cache.revision == 1
    assert cache.scope() == {"x": "obj:X"}

    try:
        cache.restore(
            ScopeSnapshot(4, (entry("x", 4, "GOOD"), entry("y", 4, "bad")))
        )
    except SreprError:
        pass
    else:
        raise AssertionError("a failed full restore was accepted")

    assert cache.revision == 1
    assert cache.scope() == {"x": "obj:X"}


def test_the_legacy_mapping_replaces_the_cache_and_is_copied():
    cache = ScopeCache(lambda text: f"obj:{text}")
    cache.restore(ScopeSnapshot(2, (entry("x", 2, "X"),)))

    returned = cache.sync({"x": 1, "y": 2})

    assert cache.revision == 0
    assert returned == {"x": 1, "y": 2}
    returned["z"] = 3
    assert cache.scope() == {"x": 1, "y": 2}


def test_the_srepr_corpus_round_trips():
    corpus = (
        sp.Integer(1),
        sp.Rational(1, 2),
        sp.Float("1.25", precision=53),
        X,
        sp.Symbol("x", positive=True),
        sp.Dummy("d"),
        X + 1,
        2 * X,
        X**-1,
        sp.sin(X),
        sp.Function("f")(X),
        sp.Matrix([[1, 2], [3, 4]]),
        sp.ImmutableMatrix([[1, 2], [3, 4]]),
        sp.FiniteSet(1, 2),
        sp.Interval(0, 1),
        sp.Union(sp.Interval(0, 1), sp.FiniteSet(2)),
        sp.oo,
        -sp.oo,
        sp.zoo,
        sp.nan,
        sp.pi,
        sp.E,
        sp.I,
        sp.true,
        sp.false,
        sp.RootOf(X**3 - 2, 0),
        sp.Tuple(1, 2),
        sp.Dict({1: 2}),
        sp.Lambda(X, X + 1),
        sp.Integral(X**2, X),
        sp.Derivative(sp.sin(X), X),
        sp.Eq(X, 1),
        sp.Lt(X, 2),
        sp.Poly(X**2 + 1, X),
        sp.EmptySet,
        sp.Reals,
        sp.GoldenRatio,
    )
    for value in corpus:
        text = sp.srepr(value)
        restored = restore_srepr(text)
        assert sp.srepr(restored) == text, text


def test_srepr_restoration_rejects_code_and_unsupported_nodes():
    for text in (
        "__import__('os')",
        "Symbol('x').__class__",
        "(lambda: 1)()",
        "open('x')",
        "Symbol('x') + 1",
        "Symbol('x', positive=__import__('os'))",
        "Symbol",
        "",
    ):
        try:
            restore_srepr(text)
        except SreprError:
            pass
        else:
            raise AssertionError(f"unsafe srepr accepted: {text!r}")


def test_result_payload_converts_success_failure_variants_and_plot():
    from python.model.calculator import Assignment, Calculator
    from python.model.variants import variants as make_variants
    from python.plot_programs import with_plot
    from python.result_payload import (
        assignment_candidate,
        result_view,
        variant_views,
    )

    calculator = Calculator()
    success = calculator.assign(Assignment("a", "=", "2 + 3"), {})
    view = result_view(
        success, 7, scope_revision=3,
        entry=assignment_candidate("a", success.value),
    )
    assert view.text == "5"
    assert view.is_error is False
    assert view.entry is not None and view.entry.name == "a"
    assert view.scope_revision == 3
    assert variant_views(make_variants(calculator.evaluate("sqrt(2)", {}).value))

    failure = calculator.evaluate("1 +", {})
    failed = result_view(failure, 8, scope_revision=3)
    assert failed.is_error is True
    assert failed.error_kind == "SYNTAX"
    assert failed.error_message

    plotted = with_plot(calculator.evaluate("x**2", {}))
    plot_view = result_view(plotted, 9)
    assert plot_view.plot
    assert plot_view.plot[0].label == "x**2"
    assert plot_view.plot[0].program["text"] == "x**2"


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
