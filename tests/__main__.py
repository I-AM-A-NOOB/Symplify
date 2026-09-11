# coding: utf-8
"""Run every test module: ``uv run python -m tests``.

Each module is also runnable on its own (``python -m tests.test_model``); this
just saves remembering them.
"""

import sys

from . import test_model, test_settings

MODULES = (test_model, test_settings)


def main() -> int:
    """Run each test module and report a combined exit code."""
    failed = 0
    for module in MODULES:
        print(f"\n=== {module.__name__} ===")
        failed += module.main()
    print(f"\n{'FAILED' if failed else 'OK'}: {len(MODULES)} module(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
