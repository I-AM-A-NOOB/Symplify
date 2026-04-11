# coding: utf-8
"""Application-specific components for Symplify.

This package contains custom widgets that are specific to the Symplify
application, separate from the reusable qfluentplus component library.

Example:
    >>> from app.components import KeyboardPanel
    >>> keyboard = KeyboardPanel()
"""

from .keyboard_panel import KeyboardPanel

__all__ = ["KeyboardPanel"]
