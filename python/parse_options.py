"""The user-visible subset of SymPy's parser transformations.

``ParsePolicy`` (worker protocol) carries the names; this module owns the
*policy* the settings page exposes and the default the app has always used.
It imports neither Qt nor SymPy, so the Store worker and settings load it
without pulling in the calculator.

Only syntax conveniences are exposed. ``auto_symbol``, ``auto_number`` and the
other tokenizer primitives stay fixed: turning them off would break variable
names and numeric literals rather than offer a meaningful choice.
"""

from __future__ import annotations

from collections.abc import Mapping

from .worker_protocol import (
    DEFAULT_TRANSFORMATIONS,
    KNOWN_TRANSFORMATIONS,
    ParsePolicy,
)

#: Transformations the calculator always applies. They are tokenizer basics,
#: not style choices: disabling them would make ordinary names or numbers
#: unparseable.
CORE_TRANSFORMATIONS = (
    "lambda_notation",
    "auto_symbol",
    "repeated_decimals",
    "auto_number",
)

#: Transformations the settings page may toggle, in ParsePolicy order.
EXPOSED_TRANSFORMATIONS = (
    "factorial_notation",
    "split_symbols",
    "implicit_multiplication",
    "convert_xor",
    "implicit_application",
    "function_exponentiation",
)

#: Defaults preserve the calculator's behaviour before the setting existed.
DEFAULT_OPTIONS: dict[str, bool] = {
    name: name in DEFAULT_TRANSFORMATIONS for name in EXPOSED_TRANSFORMATIONS
}


def default_options() -> dict[str, bool]:
    """A fresh copy of :data:`DEFAULT_OPTIONS`."""
    return dict(DEFAULT_OPTIONS)


def normalize_options(options: Mapping[str, object] | None = None) -> dict[str, bool]:
    """Read the exposed flags, falling back to defaults for missing/invalid ones."""
    source = options or {}
    return {
        name: bool(source.get(name, DEFAULT_OPTIONS[name]))
        for name in EXPOSED_TRANSFORMATIONS
    }


def policy_from_options(
    options: Mapping[str, object] | None = None,
    *,
    profile_id: str | None = None,
) -> ParsePolicy:
    """Build the ordered parser policy from the exposed switches.

    ``profile_id`` is ``"default"`` while the flags match the historical
    behavior and ``"custom"`` otherwise, so a result can be traced to the
    rules that produced it without putting a whole flag set on every DTO.
    """
    flags = normalize_options(options)
    transformations = tuple(
        name
        for name in KNOWN_TRANSFORMATIONS
        if name in CORE_TRANSFORMATIONS or flags.get(name, False)
    )
    if profile_id is None:
        profile_id = "default" if flags == DEFAULT_OPTIONS else "custom"
    return ParsePolicy(
        profile_id=profile_id,
        transformations=transformations,
        evaluate=True,
    )
