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


def localize_warning(name: str, warning: str) -> str:
    """Translate a known reserved-name warning; leave every other string alone."""
    if warning == _BUILTIN.replace("%1", name):
        return QCoreApplication.translate("WarningDialog", _BUILTIN).replace("%1", name)
    if warning == _PLOTTING.replace("%1", name):
        return QCoreApplication.translate("WarningDialog", _PLOTTING).replace("%1", name)
    return warning


__all__ = ["localize_warning"]
