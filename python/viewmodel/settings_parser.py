"""Parser switches: the subset of SymPy transformations the UI exposes.

Methods only. The ``Property`` declarations and signals live on
``SettingsViewModel``, which mixes this in; every setter persists through the
one SettingsStore and announces the parser domain plus the catch-all change.
"""

from __future__ import annotations

from ..parse_options import EXPOSED_TRANSFORMATIONS, policy_from_options
from ..worker_protocol import ParsePolicy


class ParserSettings:
    """Reads and writes the user-visible parser transformations."""

    def _get_parse_option(self, name: str) -> bool:
        return bool(self._store.get(f"parser.{name}"))

    def _set_parse_option(self, name: str, value: object) -> None:
        self._store.set(f"parser.{name}", bool(value))
        self.parseSettingsChanged.emit()
        self.changed.emit()

    def parse_policy(self) -> ParsePolicy:
        """The current policy, built in the protocol's canonical order."""
        return policy_from_options(
            {name: self._get_parse_option(name) for name in EXPOSED_TRANSFORMATIONS}
        )

    def _get_factorial_notation(self) -> bool:
        return self._get_parse_option("factorial_notation")

    def _set_factorial_notation(self, value: object) -> None:
        self._set_parse_option("factorial_notation", value)

    def _get_implicit_multiplication(self) -> bool:
        return self._get_parse_option("implicit_multiplication")

    def _set_implicit_multiplication(self, value: object) -> None:
        self._set_parse_option("implicit_multiplication", value)

    def _get_convert_xor(self) -> bool:
        return self._get_parse_option("convert_xor")

    def _set_convert_xor(self, value: object) -> None:
        self._set_parse_option("convert_xor", value)

    def _get_implicit_application(self) -> bool:
        return self._get_parse_option("implicit_application")

    def _set_implicit_application(self, value: object) -> None:
        self._set_parse_option("implicit_application", value)

    def _get_function_exponentiation(self) -> bool:
        return self._get_parse_option("function_exponentiation")

    def _set_function_exponentiation(self, value: object) -> None:
        self._set_parse_option("function_exponentiation", value)

    def _get_split_symbols(self) -> bool:
        return self._get_parse_option("split_symbols")

    def _set_split_symbols(self, value: object) -> None:
        self._set_parse_option("split_symbols", value)
