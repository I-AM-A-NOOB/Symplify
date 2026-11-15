"""Contract tests for the UI/worker protocol DTOs (plain Python, no Qt).

Run from the repository root:

    uv run python -m tests.test_protocol

The protocol is the boundary the Store and Compute workers will share. These
tests lock the wire shape, the revision rules and the ``ScopeState`` recovery
paths so a worker can be built against them before the UI changes.
"""

import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from python.worker_protocol import (  # noqa: E402
    DEFAULT_TRANSFORMATIONS,
    KNOWN_TRANSFORMATIONS,
    CommitRequest,
    ParsePolicy,
    PlotSpec,
    ProtocolError,
    ResultView,
    ScopeChange,
    ScopeConflictError,
    ScopeDelta,
    ScopeGapError,
    ScopeSnapshot,
    ScopeStaleError,
    ScopeState,
    StoreEntry,
    StoreEntryCandidate,
    StoreReply,
    VariableView,
    VariantView,
)


def entry(name, revision, **fields):
    """A StoreEntry with display defaults; fields override the defaults."""
    values = {
        "srepr": f"Integer({revision})",
        "display": str(revision),
        "type_label": "Integer",
        "latex": str(revision),
        "valid": True,
    }
    values.update(fields)
    return StoreEntry(name=name, revision=revision, **values)


def wire(value):
    """Serialize through JSON exactly as a Store snapshot would, then restore."""
    data = json.loads(json.dumps(value.to_dict()))
    return type(value).from_dict(data)


def assert_raises(exc_type, fn, label):
    try:
        fn()
    except exc_type:
        return
    raise AssertionError(f"{label}: expected {exc_type.__name__}")


# --------------------------------------------------------------------------
# DTO shape and JSON round trips
# --------------------------------------------------------------------------

def test_store_entry_round_trips_and_projects_a_variable_view():
    original = entry("x", 3, srepr="Symbol('x')", display="x", type_label="Symbol")
    assert wire(original) == original

    view = original.view()
    assert view == VariableView(
        name="x", expression="x", type_label="Symbol", valid=True, revision=3,
        latex="3", warning="")
    assert wire(view) == view


def test_an_invalid_store_entry_keeps_raw_text_without_a_srepr():
    original = entry(
        "x", 4, srepr="", display="sin(", type_label="Invalid", latex="", valid=False)
    assert wire(original) == original
    assert wire(original.view()).valid is False


def test_store_entry_rejects_malformed_wire_data():
    def wrong_schema(data):
        data["schema"] = 2

    def missing_name(data):
        del data["name"]

    def bool_revision(data):
        data["revision"] = True

    def negative_revision(data):
        data["revision"] = -1

    def non_string_display(data):
        data["display"] = 1

    def valid_without_srepr(data):
        data["srepr"] = ""

    for label, mutate in (
        ("schema", wrong_schema),
        ("missing name", missing_name),
        ("bool revision", bool_revision),
        ("negative revision", negative_revision),
        ("display type", non_string_display),
        ("valid without srepr", valid_without_srepr),
    ):
        data = entry("x", 1).to_dict()
        mutate(data)
        assert_raises(
            ProtocolError, lambda data=data: StoreEntry.from_dict(data), label)


def test_result_view_round_trips_with_variants_and_a_plot_program():
    program = {
        "schema": 2,
        "text": "x**2",
        "kind": "adaptive",
        "args": ["x"],
        "glsl": {},
        "numpy": "def f(x):\n    return x**2",
        "math": "def f(x):\n    return x**2",
        "error": "",
    }
    original = ResultView(
        request_id=7,
        expression="diff(x**2, x)",
        text="2*x",
        latex="2 x",
        is_error=False,
        error_message="",
        hint="",
        variants=(VariantView("numeric", "2.0", "2.0"),),
        plot=(PlotSpec("f", "result", program),),
        scope_revision=4,
        profile_id="default",
    )
    assert wire(original) == original
    assert wire(original).plot[0].program == program

    failure = ResultView(
        request_id=8,
        expression="sin(",
        text="",
        latex="",
        is_error=True,
        error_message="Syntax error",
        hint="",
        variants=(),
        plot=(),
        scope_revision=4,
        profile_id="default",
        error_kind="SYNTAX",
        entry=StoreEntryCandidate(
            name="x",
            srepr="Integer(1)",
            display="1",
            type_label="Integer",
            latex="x = 1",
        ),
    )
    assert wire(failure) == failure
    assert wire(failure).error_kind == "SYNTAX"
    assert wire(failure).entry.name == "x"


def test_result_view_defaults_the_optional_fields_of_the_wire_format():
    data = ResultView(
        request_id=1,
        expression="1 + 1",
        text="2",
        latex="2",
        is_error=False,
        error_message="",
        hint="",
        variants=(),
        plot=(),
        scope_revision=0,
        profile_id="default",
    ).to_dict()
    for key in ("hint", "variants", "plot", "profile_id", "error_kind"):
        del data[key]
    restored = ResultView.from_dict(data)
    assert restored.hint == ""
    assert restored.variants == ()
    assert restored.plot == ()
    assert restored.profile_id == "default"
    assert restored.error_kind == ""


def test_variant_and_plot_specs_round_trip_directly():
    variant = VariantView("factor", "x*(x + 1)", "x (x + 1)")
    assert wire(variant) == variant

    source = {"schema": 2, "text": "x", "kind": "adaptive", "args": ["x"], "glsl": {}}
    spec = PlotSpec("f", "result", source)
    source["text"] = "mutated"
    assert spec.program["text"] == "x"
    assert wire(spec) == spec


def test_result_view_rejects_a_list_where_a_frozen_tuple_belongs():
    assert_raises(
        ProtocolError,
        lambda: ResultView(
            request_id=1,
            expression="1 + 1",
            text="2",
            latex="2",
            is_error=False,
            error_message="",
            hint="",
            variants=[],
            plot=(),
            scope_revision=0,
            profile_id="default",
        ),
        "list variants",
    )


# --------------------------------------------------------------------------
# Scope revisions, deltas and full recovery
# --------------------------------------------------------------------------

def test_a_delta_applies_incrementally_and_advances_the_revision():
    state = ScopeState()
    state.apply(ScopeDelta(0, 1, (ScopeChange("x", 1, entry("x", 1)),)))
    state.apply(ScopeDelta(1, 2, (ScopeChange("y", 2, entry("y", 2)),)))
    state.apply(
        ScopeDelta(
            2,
            4,
            (
                ScopeChange("x", 4, entry("x", 4, display="4")),
                ScopeChange("z", 3, entry("z", 3)),
            ),
        )
    )

    assert state.revision == 4
    assert [item.name for item in state.entries()] == ["x", "y", "z"]
    assert state.entry("x").revision == 4
    assert state.entry("x").display == "4"
    assert state.entry("z").revision == 3

    state.apply(ScopeDelta(4, 5, (ScopeChange("y", 5, None),)))
    assert state.revision == 5
    assert state.entry("y") is None


def test_a_later_delta_for_the_same_name_wins():
    state = ScopeState()
    state.apply(
        ScopeDelta(0, 1, (ScopeChange("x", 1, entry("x", 1, display="1")),)))
    state.apply(
        ScopeDelta(1, 2, (ScopeChange("x", 2, entry("x", 2, display="2")),)))
    assert state.entry("x").revision == 2
    assert state.entry("x").display == "2"


def test_a_stale_or_gapped_delta_is_refused_without_mutation():
    state = ScopeState(3, (entry("x", 2),))

    assert_raises(
        ScopeStaleError,
        lambda: state.apply(
            ScopeDelta(2, 4, (ScopeChange("x", 4, entry("x", 4)),))),
        "stale delta",
    )
    assert_raises(
        ScopeGapError,
        lambda: state.apply(
            ScopeDelta(4, 5, (ScopeChange("x", 5, entry("x", 5)),))),
        "gapped delta",
    )
    assert state.revision == 3
    assert state.entry("x").revision == 2


def test_a_conflicting_change_does_not_half_apply_the_delta():
    state = ScopeState(2, (entry("x", 2),))
    delta = ScopeDelta(
        2,
        3,
        (
            ScopeChange("y", 3, entry("y", 3)),
            ScopeChange("missing", 3, None),
        ),
    )
    assert_raises(ScopeConflictError, lambda: state.apply(delta), "remove absent name")
    assert state.revision == 2
    assert state.entry("y") is None
    assert state.entry("missing") is None


def test_delta_validation_rejects_duplicates_and_out_of_range_revisions():
    assert_raises(
        ProtocolError,
        lambda: ScopeDelta(2, 1, ()),
        "base after revision",
    )
    assert_raises(
        ProtocolError,
        lambda: ScopeDelta(
            0,
            2,
            (
                ScopeChange("x", 1, entry("x", 1)),
                ScopeChange("x", 2, entry("x", 2)),
            ),
        ),
        "duplicate name",
    )
    assert_raises(
        ProtocolError,
        lambda: ScopeDelta(1, 2, (ScopeChange("x", 1, entry("x", 1)),)),
        "change at the base revision",
    )
    assert_raises(
        ProtocolError,
        lambda: ScopeDelta(0, 2, (ScopeChange("x", 3, entry("x", 3)),)),
        "change past the revision",
    )
    assert_raises(
        ProtocolError,
        lambda: ScopeChange("x", 1, entry("y", 1)),
        "entry name mismatch",
    )
    assert_raises(
        ProtocolError,
        lambda: ScopeChange("x", 1, entry("x", 2)),
        "entry revision mismatch",
    )


def test_a_delta_with_a_removal_round_trips_through_json():
    delta = ScopeDelta(
        1,
        2,
        (
            ScopeChange("x", 2, entry("x", 2)),
            ScopeChange("y", 2, None),
        ),
    )
    assert wire(delta) == delta
    assert wire(delta).changes[1].entry is None


def test_a_snapshot_is_the_full_recovery_path():
    snapshot = ScopeSnapshot(10, (entry("x", 7), entry("y", 10)))
    state = ScopeState.from_snapshot(snapshot)
    assert state.revision == 10
    assert [item.name for item in state.entries()] == ["x", "y"]
    assert state.snapshot() == snapshot
    assert wire(snapshot) == snapshot

    state.reset(ScopeSnapshot(12, (entry("z", 12),)))
    assert state.revision == 12
    assert [item.name for item in state.entries()] == ["z"]


def test_snapshot_validation_rejects_duplicates_and_future_entries():
    assert_raises(
        ProtocolError,
        lambda: ScopeSnapshot(2, (entry("x", 1), entry("x", 2))),
        "duplicate entries",
    )
    assert_raises(
        ProtocolError,
        lambda: ScopeSnapshot(2, (entry("x", 3),)),
        "entry newer than snapshot",
    )
    assert_raises(
        ProtocolError,
        lambda: ScopeState(2, (entry("x", 3),)),
        "state entry newer than state",
    )


def test_store_candidate_commit_and_reply_round_trip():
    candidate = StoreEntryCandidate(
        name="x",
        srepr="Symbol('x')",
        display="x",
        type_label="Symbol",
        latex="x",
        warning="x is a plotting variable.",
    )
    assert wire(candidate) == candidate
    assert candidate.to_entry(4) == entry("x", 4, srepr="Symbol('x')", display="x",
                                          type_label="Symbol", latex="x",
                                          warning="x is a plotting variable.")

    request = CommitRequest(expected_revision=4, entry=candidate)
    assert wire(request) == request

    delta = ScopeDelta(4, 5, (ScopeChange("x", 5, candidate.to_entry(5)),))
    reply = StoreReply(ok=True, revision=5, delta=delta)
    assert wire(reply) == reply
    assert wire(StoreReply(ok=False, revision=4, message="conflict")) == \
        StoreReply(ok=False, revision=4, message="conflict")


def test_store_protocol_rejects_bad_candidates_and_replies():
    assert_raises(
        ProtocolError,
        lambda: StoreEntryCandidate(
            name="x", srepr="", display="x", type_label="Symbol", latex="x"),
        "valid candidate without srepr",
    )
    assert_raises(
        ProtocolError,
        lambda: CommitRequest(
            expected_revision=-1,
            entry=StoreEntryCandidate(
                name="x", srepr="Symbol('x')", display="x",
                type_label="Symbol", latex="x"),
        ),
        "negative expected revision",
    )
    assert_raises(
        ProtocolError,
        lambda: StoreReply(
            ok=True,
            revision=5,
            delta=ScopeDelta(3, 4, (ScopeChange("x", 4, entry("x", 4)),)),
        ),
        "reply revision mismatch",
    )


# --------------------------------------------------------------------------
# ParsePolicy placeholder
# --------------------------------------------------------------------------

def test_parse_policy_defaults_match_the_current_parser():
    policy = ParsePolicy()
    assert policy.profile_id == "default"
    assert policy.evaluate is True
    assert policy.transformations == DEFAULT_TRANSFORMATIONS
    assert set(policy.transformations) <= set(KNOWN_TRANSFORMATIONS)
    assert wire(policy) == policy


def test_parse_policy_round_trips_a_restricted_profile():
    policy = ParsePolicy(
        profile_id="no-implicit",
        transformations=("auto_symbol", "convert_xor"),
        evaluate=False,
    )
    assert wire(policy) == policy


def test_parse_policy_rejects_names_outside_the_allowlist_and_bad_order():
    assert_raises(ProtocolError, lambda: ParsePolicy(""), "empty profile")
    assert_raises(ProtocolError, lambda: ParsePolicy("bad profile"), "profile spaces")
    assert_raises(ProtocolError, lambda: ParsePolicy(profile_id=1), "profile type")
    assert_raises(
        ProtocolError,
        lambda: ParsePolicy(transformations=("call_everything",)),
        "unknown transformation",
    )
    assert_raises(
        ProtocolError,
        lambda: ParsePolicy(transformations=("auto_symbol", "auto_symbol")),
        "duplicate transformation",
    )
    assert_raises(
        ProtocolError,
        lambda: ParsePolicy(transformations=("convert_xor", "implicit_multiplication")),
        "wrong order",
    )
    assert_raises(
        ProtocolError,
        lambda: ParsePolicy(transformations=["auto_symbol"]),
        "list instead of tuple",
    )
    assert_raises(ProtocolError, lambda: ParsePolicy(evaluate=1), "non-boolean evaluate")


def test_parse_policy_wire_defaults_are_compatible_with_future_additions():
    policy = ParsePolicy.from_dict({"schema": 1, "profile_id": "default"})
    assert policy.transformations == DEFAULT_TRANSFORMATIONS
    assert policy.evaluate is True


# --------------------------------------------------------------------------
# Boundary proof
# --------------------------------------------------------------------------

def test_the_protocol_module_imports_neither_qt_nor_sympy():
    script = (
        "import json, sys\n"
        "import python.worker_protocol\n"
        "print(json.dumps(sorted(name for name in ('sympy', 'PySide6') "
        "if name in sys.modules)))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) == []


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
