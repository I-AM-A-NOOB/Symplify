# coding: utf-8
"""Main entry point for the Symplify calculator application.

This module serves as the application entry point, initializing the Qt
application and displaying the main window.

Example:
    $ python main.py
"""

import sys

from PySide6.QtWidgets import QApplication

from app.common.config_manager import ConfigManager
from app.view import MainWindow


def main() -> int:
    """Run the Symplify calculator application.

    Returns:
        Application exit code.
    """
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Symplify")
    app.setApplicationVersion("1.0.0")

    # Load and apply all configurations
    ConfigManager.load()

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run application event loop
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
