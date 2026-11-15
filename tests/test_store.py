"""Contract tests for the variable Store (zero Qt, zero SymPy).

Run from the repository root:

    uv run python -m tests.test_store

The Store is the single writer of variable state. These tests lock its
revision allocation, its stale-writer rejection, the deltas it hands to the
Compute cache, and its optional JSON snapshot.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from python.names import SYMPY_VERSION  # noqa: E402
from python.store_client import StoreClient, StoreClientError  # noqa: E402
from python.store_worker import VariableStore  # noqa: E402
from python.worker_protocol import (  # noqa: E402
    CommitRequest,
    ScopeSnapshot,
    ScopeState,
    StoreEntry,
    StoreEntryCandidate,
)


class _FakeConnection:
    def __init__(self, message=None, ready=False):
        self.message = message
        self.ready = ready

    def send(self, message):
        pass

    def poll(self, timeout):
        return self.ready

    def recv(self):
        return self.message


class _FakeWorker:
    def __init__(self, connection):
        self.connection = connection
        self.stopped = 0

    def ensure(self):
        return self.connection

    def stop(self, wait=True):
        self.stopped += 1


def temp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="symplify_store_test_"))


def assert_raises(exc_type, fn, label):
    try:
        fn()
    except exc_type:
        return
    raise AssertionError(f"{label}: expected {exc_type.__name__}")


def candidate(name, *, display=None, warning="", valid=True, srepr=None):
    return StoreEntryCandidate(
        name=name,
        srepr=f"Symbol('{name}')" if srepr is None else srepr,
        display=name if display is None else display,
        type_label="Symbol" if valid else "Invalid",
        latex=name if valid else "",
        warning=warning,
        valid=valid,
    )


def commit(store, name, expected, **fields):
    return store.commit(CommitRequest(expected, candidate(name, **fields)))


# --------------------------------------------------------------------------
# Revisions and deltas
# --------------------------------------------------------------------------

def test_commit_assigns_revisions_and_returns_the_delta():
    store = VariableStore()
    first = commit(store, "x", 0)
    second = commit(store, "y", 1)

    assert first.ok and first.revision == 1
    assert first.delta is not None
    assert first.delta.base_revision == 0
    assert first.delta.revision == 1
    assert first.delta.changes[0].entry.name == "x"
    assert second.ok and second.revision == 2
    assert [entry.name for entry in store.entries()] == ["x", "y"]
    assert store.snapshot() == store.snapshot()


def test_a_stale_commit_is_rejected_without_mutating():
    store = VariableStore()
    commit(store, "x", 0)

    stale = commit(store, "y", 0)

    assert stale.ok is False
    assert stale.revision == 1
    assert stale.delta is None
    assert "revision conflict" in stale.message
    assert store.entry("y") is None
    assert store.revision == 1

    assert commit(store, "y", 1).ok
    assert store.revision == 2


def test_an_invalid_candidate_is_stored_as_an_invalid_entry():
    store = VariableStore()
    reply = store.commit(
        CommitRequest(
            0,
            candidate("x", display="sin(", valid=False, srepr=""),
        )
    )
    assert reply.ok
    entry = store.entry("x")
    assert entry is not None
    assert entry.valid is False
    assert entry.srepr == ""
    assert entry.display == "sin("


def test_a_commit_with_an_invalid_name_is_rejected():
    store = VariableStore()
    reply = commit(store, "1bad", 0)
    assert reply.ok is False
    assert reply.revision == 0
    assert "invalid variable name" in reply.message
    assert store.entries() == ()


def test_rename_preserves_position_and_srepr_and_clears_name_derived_text():
    store = VariableStore()
    commit(store, "x", 0, warning="x is a plotting variable.")
    commit(store, "y", 1)
    before = store.snapshot()

    reply = store.rename("x", "z", 2)

    assert reply.ok and reply.revision == 3
    assert reply.delta is not None
    assert [entry.name for entry in store.entries()] == ["z", "y"]
    renamed = store.entry("z")
    assert renamed is not None
    assert renamed.srepr == before.entries[0].srepr
    assert renamed.display == before.entries[0].display
    assert renamed.latex == ""
    assert renamed.warning == ""
    assert {change.name for change in reply.delta.changes} == {"x", "z"}
    assert reply.delta.changes[0].entry is None


def test_rename_rejects_invalid_missing_and_duplicate_names():
    store = VariableStore()
    commit(store, "x", 0)
    commit(store, "y", 1)

    for reply, expected in (
        (store.rename("x", "1bad", 2), "invalid variable name"),
        (store.rename("x", "y", 2), "already exists"),
        (store.rename("missing", "z", 2), "no variable named"),
    ):
        assert reply.ok is False
        assert reply.revision == 2
        assert expected in reply.message
    assert [entry.name for entry in store.entries()] == ["x", "y"]
    assert store.revision == 2

    no_op = store.rename("x", "x", 2)
    assert no_op.ok and no_op.delta is None
    assert store.revision == 2


def test_delete_and_clear_emit_tombstones():
    store = VariableStore()
    commit(store, "x", 0)
    commit(store, "y", 1)

    deleted = store.delete("x", 2)
    assert deleted.ok and deleted.revision == 3
    assert deleted.delta is not None
    assert deleted.delta.changes[0].name == "x"
    assert deleted.delta.changes[0].entry is None
    assert [entry.name for entry in store.entries()] == ["y"]

    cleared = store.clear(3)
    assert cleared.ok and cleared.revision == 4
    assert cleared.delta is not None
    assert [change.name for change in cleared.delta.changes] == ["y"]
    assert store.entries() == ()

    no_op = store.clear(4)
    assert no_op.ok and no_op.delta is None
    assert store.revision == 4


def test_a_scope_state_tracks_every_reply():
    store = VariableStore()
    state = ScopeState.from_snapshot(store.snapshot())

    sequence = [
        commit(store, "x", state.revision),
        commit(store, "y", state.revision + 1),
        store.rename("x", "z", state.revision + 2),
        store.delete("y", state.revision + 3),
        store.clear(state.revision + 4),
    ]
    for reply in sequence:
        assert reply.ok, reply.message
        assert reply.delta is not None
        state.apply(reply.delta)

    assert state.snapshot() == store.snapshot()


# --------------------------------------------------------------------------
# Optional JSON snapshot
# --------------------------------------------------------------------------

def test_the_store_client_replaces_a_worker_after_a_timeout():
    client = StoreClient()
    worker = _FakeWorker(_FakeConnection(ready=False))
    client._worker = worker

    assert_raises(
        StoreClientError, lambda: client.snapshot(), "timed-out store request")
    assert worker.stopped == 1
    assert client.timeout_count == 1
    assert "did not answer" in client.last_error


def test_the_store_client_rejects_a_mismatched_reply_and_stops():
    client = StoreClient()
    worker = _FakeWorker(
        _FakeConnection((999, "snapshot", ScopeSnapshot(0, ())), ready=True)
    )
    client._worker = worker

    assert_raises(
        StoreClientError, lambda: client.snapshot(), "mismatched store reply")
    assert worker.stopped == 1
    assert "expected" in client.last_error


def test_a_snapshot_carries_the_sympy_version():
    path = temp_dir() / "variables.json"
    store = VariableStore(path)
    commit(store, "x", 0)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["sympy_version"] == SYMPY_VERSION
    assert data["snapshot"]["revision"] == 1


def test_a_snapshot_from_another_sympy_version_is_set_aside():
    path = temp_dir() / "variables.json"
    snapshot = ScopeSnapshot(
        1, (candidate("x", srepr="Integer(1)").to_entry(1),))
    path.write_text(json.dumps({
        "sympy_version": "0.0.0",
        "snapshot": snapshot.to_dict(),
    }), encoding="utf-8")

    store = VariableStore(path)

    assert "SymPy 0.0.0" in store.load_error
    assert store.entries() == ()
    assert (path.parent / "variables.json.corrupt").exists()


def test_an_unversioned_legacy_snapshot_still_loads():
    path = temp_dir() / "variables.json"
    path.write_text(json.dumps(ScopeSnapshot(
        1, (candidate("x", srepr="Integer(1)").to_entry(1),)).to_dict()),
        encoding="utf-8")

    store = VariableStore(path)

    assert store.load_error == ""
    assert store.entry("x") is not None


def test_a_snapshot_round_trips_through_disk():
    path = temp_dir() / "variables.json"
    first = VariableStore(path)
    commit(first, "x", 0, warning="x is a plotting variable.")
    assert path.exists()

    second = VariableStore(path)
    assert second.load_error == ""
    assert second.snapshot() == first.snapshot()
    loaded = second.entry("x")
    assert loaded is not None
    assert loaded.warning == "x is a plotting variable."
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_a_corrupt_snapshot_is_set_aside_and_reported():
    path = temp_dir() / "variables.json"
    path.write_text("{not json", encoding="utf-8")

    store = VariableStore(path)

    assert "not loaded" in store.load_error
    assert store.entries() == ()
    assert (path.parent / "variables.json.corrupt").exists()
    assert path.exists() is False

    assert commit(store, "x", 0).ok
    assert path.exists()
    assert VariableStore(path).entry("x") is not None


def test_a_snapshot_with_an_invalid_name_is_set_aside():
    path = temp_dir() / "variables.json"
    snapshot = ScopeSnapshot(
        1,
        (
            StoreEntry(
                name="1bad",
                srepr="Integer(1)",
                display="1",
                type_label="Integer",
                latex="1",
                revision=1,
                valid=True,
            ),
        ),
    )
    path.write_text(json.dumps(snapshot.to_dict()), encoding="utf-8")

    store = VariableStore(path)

    assert "invalid variable name" in store.load_error
    assert store.entries() == ()
    assert (path.parent / "variables.json.corrupt").exists()


def test_a_failed_snapshot_write_keeps_the_in_memory_state():
    root = temp_dir()
    blocker = root / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    path = blocker / "variables.json"

    store = VariableStore(path)
    reply = commit(store, "x", 0)

    assert reply.ok
    assert "not written" in reply.message
    assert store.entry("x") is not None


# --------------------------------------------------------------------------
# Boundary proof
# --------------------------------------------------------------------------

def test_the_store_module_imports_neither_qt_nor_sympy():
    script = (
        "import json, sys\n"
        "import python.store_worker\n"
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
