"""Translate the model's display-ready warnings at the Qt boundary.

``python/model`` is zero Qt and the Store persists its warnings as strings, so
the two reserved-name sentences arrive here in English. The QML catalogues
already carry their source strings (``WarningDialog``), which is why the
translation is looked up with that context rather than through ``self.tr`` in
two viewmodels.
"""

from PySide6.QtCore import QCoreApplication

_BUILTIN = "%1 is a SymPy built-in. You asked for it."
_PLOTTING = "%1 is a plotting variable. You asked for it."


def reserved_warning(name: str, kind: str) -> str:
    """The translated warning for a reserved-name ``kind`` (``""`` if unknown).

    This is the primary path: the warning is a function of the *name*, so a
    changed source string or an old persisted sentence cannot orphan it.
    """
    template = _BUILTIN if kind == "builtin" else (
        _PLOTTING if kind == "plotting" else ""
    )
    if not template:
        return ""
    return QCoreApplication.translate("WarningDialog", template).replace("%1", name)


def localize_warning(name: str, warning: str) -> str:
    """Legacy fallback for a persisted warning whose name is no longer reserved.

    Kept for old Store entries whose ``warning`` text came from an earlier
    catalogue; new code asks :func:`reserved_warning` with the name's kind.
    """
    if warning == _BUILTIN.replace("%1", name):
        return QCoreApplication.translate("WarningDialog", _BUILTIN).replace("%1", name)
    if warning == _PLOTTING.replace("%1", name):
        return QCoreApplication.translate("WarningDialog", _PLOTTING).replace("%1", name)
    return warning


__all__ = ["localize_warning", "reserved_warning"]
