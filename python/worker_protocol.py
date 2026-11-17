"""The UI/worker protocol: plain-data DTOs for variables, results and scope sync.

This module is deliberately **zero Qt and zero SymPy**. The variable Store
worker imports it, and importing :mod:`python.model` would pull SymPy in
with the calculator. Everything here is a frozen dataclass of strings, integers,
booleans and plain dicts, so the same objects cross a pickled worker pipe and
serialize to JSON for a Store snapshot.

The boundary:

- :class:`StoreEntry` is what the Store owns: the recoverable ``srepr`` plus the
  display strings, type label, LaTeX and revision. ``srepr`` never comes from
  user input; it is produced by the Compute worker.
- :class:`VariableView`, :class:`ResultView` and :class:`VariantView` are what
  the UI sees. None carries a SymPy object.
- :class:`ScopeSnapshot` is the whole scope; :class:`ScopeDelta` is a span of
  store revisions with only the entries that changed. :class:`ScopeState` is the
  string half of the Compute worker's cache: it applies either one, refusing a
  stale delta, a revision gap, or a conflicting change.
- :class:`ParsePolicy` is the parser profile carried with each Compute request:
  an ordered allowlist of transformation names plus a diagnostic ``profile_id``.
  The Store never sees it; existing values are restored from ``srepr`` and are
  independent of the policy.

Every DTO carries ``schema`` in its wire dict. Fields are only ever added; a
reader defaults the ones it does not know. Serialization never imports SymPy, so
``json.dumps(entry.to_dict())`` is safe in the Store worker.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

__all__ = [
    "Assignment",
    "CommitRequest",
    "DEFAULT_TRANSFORMATIONS",
    "ErrorKind",
    "KNOWN_TRANSFORMATIONS",
    "ParsePolicy",
    "PlotSpec",
    "ProtocolError",
    "ResultView",
    "SCHEMA",
    "ScopeChange",
    "ScopeConflictError",
    "ScopeDelta",
    "ScopeError",
    "ScopeGapError",
    "ScopeSnapshot",
    "ScopeStaleError",
    "ScopeState",
    "StoreEntry",
    "StoreEntryCandidate",
    "StoreReply",
    "VariableView",
    "VariantView",
]

#: Bumped when a field changes meaning (never when one is added).
SCHEMA = 1


class ErrorKind(Enum):
    """Why a request could not be answered.

    Lives here, with the protocol, so the UI can read a failure kind without
    importing the SymPy calculator. The model re-exports it.

    Attributes:
        SYNTAX: the text is not parseable as an expression.
        UNKNOWN_NAME: a name used as a call that resolves to no function, or an
            augmented assignment to a variable that does not exist.
        INVALID_NAME: an assignment target that is not a legal variable name.
        UNSUPPORTED: a well-formed request this model does not implement.
        INTERNAL: sympy raised something that is not a syntax problem — a bug
            in the request's domain or in this layer, never the user's typo.
        TIMEOUT: the request exceeded the backend's deadline and was cancelled;
            raised by the frontend/backend boundary, never by the model itself.
    """

    SYNTAX = auto()
    UNKNOWN_NAME = auto()
    INVALID_NAME = auto()
    UNSUPPORTED = auto()
    INTERNAL = auto()
    TIMEOUT = auto()


@dataclass(frozen=True)
class Assignment:
    """A write to the variable store, as a request rather than a string.

    ``expression`` stays *text* so the expression language (implicit
    multiplication, ``^``, paren-less application) is parsed by exactly one
    parser. Reassembling the write into a new expression string — the previous
    implementation built ``f"{name} {op[0]} ({value})"`` — is what turned
    ``x += 1`` on an undefined ``x`` into the self-referential binding
    ``x = x + 1``.

    Attributes:
        target: Variable name to write.
        op: ``'='`` or an augmented operator (``'+='``, ``'-='``, ``'*='``,
            ``'/='``, ``'%='``).
        expression: The right-hand side, as the user typed it.
    """

    target: str
    op: str = "="
    expression: str = ""


#: The fixed parser transformation vocabulary. The Compute worker will map these
#: names to SymPy's transformation objects; the UI may only choose from it.
#: Names, not callables: a settings file must never smuggle code into the parser.
KNOWN_TRANSFORMATIONS = (
    "lambda_notation",
    "auto_symbol",
    "repeated_decimals",
    "auto_number",
    "factorial_notation",
    "split_symbols",
    "implicit_multiplication",
    "convert_xor",
    "implicit_application",
    "function_exponentiation",
)

#: What the current parser does. Kept here so a default request names exactly
#: the behaviour it expects instead of depending on the worker's build.
DEFAULT_TRANSFORMATIONS = (
    "lambda_notation",
    "auto_symbol",
    "repeated_decimals",
    "auto_number",
    "factorial_notation",
    "implicit_multiplication",
    "convert_xor",
)

_PROFILE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
_MISSING = object()


class ProtocolError(ValueError):
    """A malformed protocol object or wire dict."""


class ScopeError(ProtocolError):
    """A delta cannot be applied to the scope state it names."""


class ScopeStaleError(ScopeError):
    """The delta starts before the state's revision (the caller is behind)."""


class ScopeGapError(ScopeError):
    """The delta starts after the state's revision (changes are missing)."""


class ScopeConflictError(ScopeError):
    """The delta changes a name in a way the current scope cannot accept."""


def _field(data: Mapping[str, Any], key: str, default: Any = _MISSING) -> Any:
    if key in data:
        return data[key]
    if default is _MISSING:
        raise ProtocolError(f"missing field {key!r}")
    return default


def _text(
    data: Mapping[str, Any], key: str, *, default: Any = _MISSING, allow_empty: bool = True
) -> str:
    value = _field(data, key, default)
    if not isinstance(value, str):
        raise ProtocolError(f"field {key!r} must be a string, got {type(value).__name__}")
    if not allow_empty and not value:
        raise ProtocolError(f"field {key!r} must not be empty")
    return value


def _revision(data: Mapping[str, Any], key: str, *, default: Any = _MISSING) -> int:
    value = _field(data, key, default)
    return _as_revision(value, key)


def _boolean(data: Mapping[str, Any], key: str, *, default: Any = _MISSING) -> bool:
    value = _field(data, key, default)
    if not isinstance(value, bool):
        raise ProtocolError(f"field {key!r} must be a boolean, got {type(value).__name__}")
    return value


def _as_revision(value: Any, field: str) -> int:
    # bool is an int in Python; a True revision is a bug, not a number.
    value = _as_int(value, field)
    if value < 0:
        raise ProtocolError(f"{field} must not be negative, got {value}")
    return value


def _as_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProtocolError(f"{field} must be an integer, got {type(value).__name__}")
    return value


def _as_name(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ProtocolError(f"{field} must be a string, got {type(value).__name__}")
    if not value:
        raise ProtocolError(f"{field} must not be empty")
    return value


def _check_schema(data: Mapping[str, Any]) -> None:
    if not isinstance(data, Mapping):
        raise ProtocolError(f"wire data must be an object, got {type(data).__name__}")
    schema = _field(data, "schema")
    if schema != SCHEMA:
        raise ProtocolError(f"unsupported protocol schema {schema!r}; this build speaks {SCHEMA}")


def _items(
    data: Mapping[str, Any],
    key: str,
    parse: Callable[[Mapping[str, Any]], Any],
    *,
    default: Any = _MISSING,
) -> tuple[Any, ...]:
    raw = _field(data, key, default)
    if not isinstance(raw, (list, tuple)):
        raise ProtocolError(f"field {key!r} must be a list")
    values = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ProtocolError(f"{key}[{index}] must be an object")
        values.append(parse(item))
    return tuple(values)


def _profile(value: Any) -> str:
    if not isinstance(value, str):
        raise ProtocolError(f"profile_id must be a string, got {type(value).__name__}")
    if not _PROFILE_ID.match(value):
        raise ProtocolError(
            f"profile_id {value!r} must start with a letter or digit and contain only "
            "letters, digits, '_', '.' and '-'"
        )
    return value


def _check_entry_parts(
    name: str,
    srepr: str,
    display: str,
    type_label: str,
    latex: str,
    warning: str,
    valid: bool,
) -> None:
    """The invariants a stored entry and its uncommitted candidate share."""
    _as_name(name, "name")
    for field, value in (
        ("srepr", srepr),
        ("display", display),
        ("type_label", type_label),
        ("latex", latex),
        ("warning", warning),
    ):
        if not isinstance(value, str):
            raise ProtocolError(f"{field} must be a string, got {type(value).__name__}")
    if not isinstance(valid, bool):
        raise ProtocolError(f"valid must be a boolean, got {type(valid).__name__}")
    if valid and not srepr:
        raise ProtocolError(f"a valid entry for {name!r} requires a srepr")


@dataclass(frozen=True)
class StoreEntry:
    """One variable as the Store owns it.

    ``srepr`` is the recoverable SymPy spelling and is only ever produced by the
    Compute worker. ``display`` is what the UI shows; for an invalid entry it is
    the user's raw text. A valid entry must have an ``srepr``; an invalid one
    has none to recover. ``warning`` is a display-ready sentence the Compute
    worker derived while committing (a shadowed builtin, a plotting variable),
    so the UI never needs SymPy's name table to explain a write.
    """

    name: str
    srepr: str
    display: str
    type_label: str
    latex: str
    revision: int
    valid: bool
    warning: str = ""

    def __post_init__(self) -> None:
        _check_entry_parts(
            self.name, self.srepr, self.display, self.type_label,
            self.latex, self.warning, self.valid,
        )
        _as_revision(self.revision, "revision")

    def view(self) -> VariableView:
        """The UI-facing projection of this entry (no srepr, no SymPy)."""
        return VariableView(
            name=self.name,
            expression=self.display,
            type_label=self.type_label,
            valid=self.valid,
            revision=self.revision,
            latex=self.latex,
            warning=self.warning,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "name": self.name,
            "srepr": self.srepr,
            "display": self.display,
            "type_label": self.type_label,
            "latex": self.latex,
            "revision": self.revision,
            "valid": self.valid,
            "warning": self.warning,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> StoreEntry:
        _check_schema(data)
        return cls(
            name=_text(data, "name", allow_empty=False),
            srepr=_text(data, "srepr"),
            display=_text(data, "display"),
            type_label=_text(data, "type_label"),
            latex=_text(data, "latex"),
            revision=_revision(data, "revision"),
            valid=_boolean(data, "valid"),
            warning=_text(data, "warning", default=""),
        )


@dataclass(frozen=True)
class StoreEntryCandidate:
    """One computed variable that the UI may ask the Store to commit.

    It is a :class:`StoreEntry` without the revision the Store assigns; keeping
    the two shapes apart means a candidate can never be mistaken for committed
    state, and the Store remains the only writer of revisions.
    """

    name: str
    srepr: str
    display: str
    type_label: str
    latex: str
    valid: bool = True
    warning: str = ""

    def __post_init__(self) -> None:
        _check_entry_parts(
            self.name, self.srepr, self.display, self.type_label,
            self.latex, self.warning, self.valid,
        )

    def to_entry(self, revision: int) -> StoreEntry:
        """The committed entry at ``revision`` (the Store's next one)."""
        return StoreEntry(
            name=self.name,
            srepr=self.srepr,
            display=self.display,
            type_label=self.type_label,
            latex=self.latex,
            revision=revision,
            valid=self.valid,
            warning=self.warning,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "name": self.name,
            "srepr": self.srepr,
            "display": self.display,
            "type_label": self.type_label,
            "latex": self.latex,
            "valid": self.valid,
            "warning": self.warning,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> StoreEntryCandidate:
        _check_schema(data)
        return cls(
            name=_text(data, "name", allow_empty=False),
            srepr=_text(data, "srepr"),
            display=_text(data, "display"),
            type_label=_text(data, "type_label"),
            latex=_text(data, "latex"),
            warning=_text(data, "warning", default=""),
            valid=_boolean(data, "valid", default=True),
        )


@dataclass(frozen=True)
class CommitRequest:
    """A candidate write guarded by the Store revision the UI last saw.

    ``expected_revision`` makes a stale editor a conflict instead of a silent
    overwrite: the Store refuses the write and returns its current revision.
    """

    expected_revision: int
    entry: StoreEntryCandidate

    def __post_init__(self) -> None:
        _as_revision(self.expected_revision, "expected_revision")
        if not isinstance(self.entry, StoreEntryCandidate):
            raise ProtocolError("entry must be a StoreEntryCandidate")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "expected_revision": self.expected_revision,
            "entry": self.entry.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CommitRequest:
        _check_schema(data)
        entry = _field(data, "entry")
        if not isinstance(entry, Mapping):
            raise ProtocolError("field 'entry' must be an object")
        return cls(
            expected_revision=_revision(data, "expected_revision"),
            entry=StoreEntryCandidate.from_dict(entry),
        )


@dataclass(frozen=True)
class VariableView:
    """A variable row the UI may render: strings and a revision, nothing else.

    ``latex`` is the details panel's typeset source (empty when SymPy could not
    typeset it); ``warning`` is the Store's precomputed explanation, so neither
    the row nor the panel needs SymPy in the UI process.
    """

    name: str
    expression: str
    type_label: str
    valid: bool
    revision: int
    latex: str = ""
    warning: str = ""

    def __post_init__(self) -> None:
        _as_name(self.name, "name")
        for field, value in (
            ("expression", self.expression),
            ("type_label", self.type_label),
            ("latex", self.latex),
            ("warning", self.warning),
        ):
            if not isinstance(value, str):
                raise ProtocolError(f"{field} must be a string, got {type(value).__name__}")
        if not isinstance(self.valid, bool):
            raise ProtocolError("valid must be a boolean")
        _as_revision(self.revision, "revision")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "name": self.name,
            "expression": self.expression,
            "type_label": self.type_label,
            "valid": self.valid,
            "revision": self.revision,
            "latex": self.latex,
            "warning": self.warning,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> VariableView:
        _check_schema(data)
        return cls(
            name=_text(data, "name", allow_empty=False),
            expression=_text(data, "expression"),
            type_label=_text(data, "type_label"),
            valid=_boolean(data, "valid"),
            revision=_revision(data, "revision"),
            latex=_text(data, "latex", default=""),
            warning=_text(data, "warning", default=""),
        )


@dataclass(frozen=True)
class VariantView:
    """One alternative form of a result, as display data only.

    ``kind`` stays a plain string because the card's vocabulary may grow; the UI
    translates known kinds and ignores unknown ones.
    """

    kind: str
    expression: str
    latex: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind:
            raise ProtocolError("kind must be a non-empty string")
        if not isinstance(self.expression, str):
            raise ProtocolError("expression must be a string")
        if not isinstance(self.latex, str):
            raise ProtocolError("latex must be a string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "kind": self.kind,
            "expression": self.expression,
            "latex": self.latex,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> VariantView:
        _check_schema(data)
        return cls(
            kind=_text(data, "kind", allow_empty=False),
            expression=_text(data, "expression"),
            latex=_text(data, "latex"),
        )


@dataclass(frozen=True)
class PlotSpec:
    """One curve to draw: a label, a role and qmlmathplot's plain Program dict.

    ``program`` is exactly ``qmlmathplot.protocol.Program.to_dict()`` (GLSL,
    numpy and math source strings). It is plain data, so this module still needs
    neither qmlmathplot nor SymPy.
    """

    label: str
    role: str
    program: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.label, str):
            raise ProtocolError("label must be a string")
        if not isinstance(self.role, str):
            raise ProtocolError("role must be a string")
        if not isinstance(self.program, Mapping):
            raise ProtocolError("program must be an object")
        # Copy so a frozen DTO does not share a mutable dict with its caller.
        object.__setattr__(self, "program", dict(self.program))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "label": self.label,
            "role": self.role,
            "program": dict(self.program),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PlotSpec:
        _check_schema(data)
        program = _field(data, "program")
        if not isinstance(program, Mapping):
            raise ProtocolError("field 'program' must be an object")
        return cls(
            label=_text(data, "label"),
            role=_text(data, "role"),
            program=dict(program),
        )


@dataclass(frozen=True)
class ResultView:
    """A calculation outcome the UI can display without SymPy.

    ``text`` is the display expression (``str(value)`` for a success, empty for a
    failure); ``latex`` is the typeset source. ``plot`` carries plain
    :class:`PlotSpec` rows, and ``scope_revision`` says which Store revision the
    answer was computed against. ``error_kind`` is the ``ErrorKind`` member name
    (``"TIMEOUT"``, ``"INVALID_NAME"``, …) for a failure and empty for a success:
    the UI's follow-up decisions must not re-derive it from the message.
    """

    request_id: int
    expression: str
    text: str
    latex: str
    is_error: bool
    error_message: str
    hint: str
    variants: tuple[VariantView, ...]
    plot: tuple[PlotSpec, ...]
    scope_revision: int
    profile_id: str
    error_kind: str = ""
    #: An assignment's string-only Store candidate. ``None`` for a read or a
    #: failure; the UI commits it and never touches the SymPy value.
    entry: StoreEntryCandidate | None = None

    def __post_init__(self) -> None:
        _as_int(self.request_id, "request_id")
        if not isinstance(self.expression, str):
            raise ProtocolError("expression must be a string")
        if not isinstance(self.text, str):
            raise ProtocolError("text must be a string")
        if not isinstance(self.latex, str):
            raise ProtocolError("latex must be a string")
        if not isinstance(self.is_error, bool):
            raise ProtocolError("is_error must be a boolean")
        if not isinstance(self.error_message, str):
            raise ProtocolError("error_message must be a string")
        if not isinstance(self.hint, str):
            raise ProtocolError("hint must be a string")
        if not isinstance(self.variants, tuple) or not all(
            isinstance(item, VariantView) for item in self.variants
        ):
            raise ProtocolError("variants must be a tuple of VariantView")
        if not isinstance(self.plot, tuple) or not all(
            isinstance(item, PlotSpec) for item in self.plot
        ):
            raise ProtocolError("plot must be a tuple of PlotSpec")
        _as_revision(self.scope_revision, "scope_revision")
        _profile(self.profile_id)
        if not isinstance(self.error_kind, str):
            raise ProtocolError("error_kind must be a string")
        if self.entry is not None and not isinstance(self.entry, StoreEntryCandidate):
            raise ProtocolError("entry must be a StoreEntryCandidate or None")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "request_id": self.request_id,
            "expression": self.expression,
            "text": self.text,
            "latex": self.latex,
            "is_error": self.is_error,
            "error_message": self.error_message,
            "hint": self.hint,
            "variants": [variant.to_dict() for variant in self.variants],
            "plot": [spec.to_dict() for spec in self.plot],
            "scope_revision": self.scope_revision,
            "profile_id": self.profile_id,
            "error_kind": self.error_kind,
            "entry": None if self.entry is None else self.entry.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ResultView:
        _check_schema(data)
        entry = _field(data, "entry", None)
        if entry is not None and not isinstance(entry, Mapping):
            raise ProtocolError("field 'entry' must be an object or null")
        return cls(
            request_id=_as_int(_field(data, "request_id"), "request_id"),
            expression=_text(data, "expression"),
            text=_text(data, "text"),
            latex=_text(data, "latex"),
            is_error=_boolean(data, "is_error"),
            error_message=_text(data, "error_message"),
            hint=_text(data, "hint", default=""),
            variants=_items(data, "variants", VariantView.from_dict, default=()),
            plot=_items(data, "plot", PlotSpec.from_dict, default=()),
            scope_revision=_revision(data, "scope_revision"),
            profile_id=_text(data, "profile_id", default="default", allow_empty=False),
            error_kind=_text(data, "error_kind", default=""),
            entry=None if entry is None else StoreEntryCandidate.from_dict(entry),
        )


@dataclass(frozen=True)
class ScopeChange:
    """One name's transition inside a :class:`ScopeDelta`.

    ``entry`` is the new StoreEntry, or ``None`` for a removal. Its name and
    revision must agree with this change, so a caller cannot add a mismatched
    entry and leave the cache keyed by the wrong revision.
    """

    name: str
    revision: int
    entry: StoreEntry | None = None

    def __post_init__(self) -> None:
        _as_name(self.name, "name")
        _as_revision(self.revision, "revision")
        if self.entry is None:
            return
        if not isinstance(self.entry, StoreEntry):
            raise ProtocolError("entry must be a StoreEntry or None")
        if self.entry.name != self.name:
            raise ProtocolError(
                f"change for {self.name!r} carries an entry for {self.entry.name!r}"
            )
        if self.entry.revision != self.revision:
            raise ProtocolError(
                f"change for {self.name!r} says revision {self.revision}, "
                f"entry says {self.entry.revision}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "name": self.name,
            "revision": self.revision,
            "entry": None if self.entry is None else self.entry.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ScopeChange:
        _check_schema(data)
        raw = _field(data, "entry")
        if raw is not None and not isinstance(raw, Mapping):
            raise ProtocolError("field 'entry' must be an object or null")
        return cls(
            name=_text(data, "name", allow_empty=False),
            revision=_revision(data, "revision"),
            entry=None if raw is None else StoreEntry.from_dict(raw),
        )


@dataclass(frozen=True)
class ScopeDelta:
    """Changes from ``base_revision`` (exclusive) to ``revision`` (inclusive).

    A receiver whose state is exactly at ``base_revision`` applies the changed
    entries and jumps to ``revision``. A receiver further behind has a gap and
    must ask for a :class:`ScopeSnapshot`; one further ahead has a stale delta.
    Names are unique within the delta, and every change's revision belongs to
    the span it claims.
    """

    base_revision: int
    revision: int
    changes: tuple[ScopeChange, ...]

    def __post_init__(self) -> None:
        _as_revision(self.base_revision, "base_revision")
        _as_revision(self.revision, "revision")
        if self.base_revision > self.revision:
            raise ProtocolError(
                f"delta base {self.base_revision} is after its revision {self.revision}"
            )
        if not isinstance(self.changes, tuple) or not all(
            isinstance(change, ScopeChange) for change in self.changes
        ):
            raise ProtocolError("changes must be a tuple of ScopeChange")
        names = set()
        for change in self.changes:
            if change.name in names:
                raise ProtocolError(f"delta changes {change.name!r} more than once")
            names.add(change.name)
            if not self.base_revision < change.revision <= self.revision:
                raise ProtocolError(
                    f"change for {change.name!r} at revision {change.revision} is outside "
                    f"({self.base_revision}, {self.revision}]"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "base_revision": self.base_revision,
            "revision": self.revision,
            "changes": [change.to_dict() for change in self.changes],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ScopeDelta:
        _check_schema(data)
        return cls(
            base_revision=_revision(data, "base_revision"),
            revision=_revision(data, "revision"),
            changes=_items(data, "changes", ScopeChange.from_dict),
        )


@dataclass(frozen=True)
class StoreReply:
    """The answer to a Store mutation.

    ``ok`` is False for a revision conflict or a rejected name; ``revision`` is
    always the Store's current revision, so a refused writer knows what to
    resync against. A successful mutation carries the exact ``delta`` a Compute
    cache should apply (``None`` for a no-op such as renaming to the same name).
    """

    ok: bool
    revision: int
    delta: ScopeDelta | None = None
    message: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.ok, bool):
            raise ProtocolError("ok must be a boolean")
        _as_revision(self.revision, "revision")
        if self.delta is not None:
            if not isinstance(self.delta, ScopeDelta):
                raise ProtocolError("delta must be a ScopeDelta or None")
            if self.delta.revision != self.revision:
                raise ProtocolError(
                    f"reply revision {self.revision} does not match "
                    f"delta revision {self.delta.revision}"
                )
        if not isinstance(self.message, str):
            raise ProtocolError("message must be a string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "ok": self.ok,
            "revision": self.revision,
            "delta": None if self.delta is None else self.delta.to_dict(),
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> StoreReply:
        _check_schema(data)
        raw = _field(data, "delta", None)
        if raw is not None and not isinstance(raw, Mapping):
            raise ProtocolError("field 'delta' must be an object or null")
        return cls(
            ok=_boolean(data, "ok"),
            revision=_revision(data, "revision"),
            delta=None if raw is None else ScopeDelta.from_dict(raw),
            message=_text(data, "message", default=""),
        )


@dataclass(frozen=True)
class ScopeSnapshot:
    """The whole scope at one revision — the full-recovery message.

    Entries are unique and no entry may be newer than the snapshot itself.
    """

    revision: int
    entries: tuple[StoreEntry, ...]

    def __post_init__(self) -> None:
        _as_revision(self.revision, "revision")
        if not isinstance(self.entries, tuple) or not all(
            isinstance(entry, StoreEntry) for entry in self.entries
        ):
            raise ProtocolError("entries must be a tuple of StoreEntry")
        names = set()
        for entry in self.entries:
            if entry.name in names:
                raise ProtocolError(f"snapshot contains {entry.name!r} more than once")
            names.add(entry.name)
            if entry.revision > self.revision:
                raise ProtocolError(
                    f"snapshot revision {self.revision} is older than {entry.name!r} "
                    f"at {entry.revision}"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "revision": self.revision,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ScopeSnapshot:
        _check_schema(data)
        return cls(
            revision=_revision(data, "revision"),
            entries=_items(data, "entries", StoreEntry.from_dict),
        )


class ScopeState:
    """The synced string scope: ``revision`` plus ``name -> StoreEntry``.

    This is the half of the Compute worker's cache that knows nothing about
    SymPy. The worker pairs it with its own ``name -> (revision, object)`` map;
    applying a delta here tells it exactly which names to ``sympify`` again, and
    :meth:`reset` is the one full rebuild after a worker restart or version gap.
    """

    def __init__(self, revision: int = 0, entries: Iterable[StoreEntry] = ()) -> None:
        self._revision = 0
        self._entries: dict[str, StoreEntry] = {}
        self.reset(ScopeSnapshot(revision, tuple(entries)))

    @property
    def revision(self) -> int:
        return self._revision

    def entry(self, name: str) -> StoreEntry | None:
        return self._entries.get(name)

    def entries(self) -> tuple[StoreEntry, ...]:
        """Every entry, in insertion order."""
        return tuple(self._entries.values())

    def snapshot(self) -> ScopeSnapshot:
        return ScopeSnapshot(self._revision, self.entries())

    def reset(self, snapshot: ScopeSnapshot) -> None:
        """Replace the whole state (a worker restart or a revision gap)."""
        if not isinstance(snapshot, ScopeSnapshot):
            raise ProtocolError("reset needs a ScopeSnapshot")
        self._revision = snapshot.revision
        self._entries = {entry.name: entry for entry in snapshot.entries}

    def check(self, delta: ScopeDelta) -> None:
        """Validate that ``delta`` can be applied, without changing anything.

        Callers that must prepare work before committing (the Compute cache
        restores entries) use this to reject a stale/gapped/conflicting delta
        before spending the work or touching their object map.
        """
        if not isinstance(delta, ScopeDelta):
            raise ProtocolError("apply needs a ScopeDelta")
        if delta.base_revision < self._revision:
            raise ScopeStaleError(
                f"delta starts at {delta.base_revision}, state is already at {self._revision}"
            )
        if delta.base_revision > self._revision:
            raise ScopeGapError(
                f"delta starts at {delta.base_revision}, state is at {self._revision}; "
                "a full snapshot is required"
            )
        for change in delta.changes:
            current = self._entries.get(change.name)
            if change.entry is None:
                if current is None:
                    raise ScopeConflictError(
                        f"delta removes {change.name!r}, which the scope does not have"
                    )
            if current is not None and current.revision >= change.revision:
                raise ScopeConflictError(
                    f"delta changes {change.name!r} at revision {change.revision}, "
                    f"but the scope already has revision {current.revision}"
                )

    def apply(self, delta: ScopeDelta) -> None:
        """Apply one delta atomically; raise before mutating on any conflict."""
        self.check(delta)
        for change in delta.changes:
            if change.entry is None:
                del self._entries[change.name]
            else:
                self._entries[change.name] = change.entry
        self._revision = delta.revision

    @classmethod
    def from_snapshot(cls, snapshot: ScopeSnapshot) -> ScopeState:
        return cls(snapshot.revision, snapshot.entries)


@dataclass(frozen=True)
class ParsePolicy:
    """The parser configuration carried with one Compute request.

    ``transformations`` is an ordered subsequence of
    :data:`KNOWN_TRANSFORMATIONS` — names only, never callables, and never
    ``global_dict``/``local_dict``. ``profile_id`` is logged with results so a
    later build can tell which rules produced an answer. ``evaluate`` remains
    reserved; this app always sends ``True``.
    """

    profile_id: str = "default"
    transformations: tuple[str, ...] = DEFAULT_TRANSFORMATIONS
    evaluate: bool = True

    def __post_init__(self) -> None:
        _profile(self.profile_id)
        if not isinstance(self.transformations, tuple):
            raise ProtocolError("transformations must be a tuple of names")
        if not all(isinstance(name, str) for name in self.transformations):
            raise ProtocolError("transformations must contain strings only")
        if len(set(self.transformations)) != len(self.transformations):
            raise ProtocolError("transformations must not repeat a name")
        unknown = [name for name in self.transformations if name not in KNOWN_TRANSFORMATIONS]
        if unknown:
            raise ProtocolError(f"unknown transformations: {', '.join(unknown)}")
        order = {name: index for index, name in enumerate(KNOWN_TRANSFORMATIONS)}
        if tuple(sorted(self.transformations, key=order.__getitem__)) != self.transformations:
            raise ProtocolError("transformations must follow KNOWN_TRANSFORMATIONS order")
        if not isinstance(self.evaluate, bool):
            raise ProtocolError("evaluate must be a boolean")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "profile_id": self.profile_id,
            "transformations": list(self.transformations),
            "evaluate": self.evaluate,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ParsePolicy:
        _check_schema(data)
        raw = _field(data, "transformations", DEFAULT_TRANSFORMATIONS)
        if not isinstance(raw, (list, tuple)):
            raise ProtocolError("field 'transformations' must be a list")
        return cls(
            profile_id=_text(data, "profile_id", default="default", allow_empty=False),
            transformations=tuple(raw),
            evaluate=_boolean(data, "evaluate", default=True),
        )
