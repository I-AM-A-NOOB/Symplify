"""Run every test module: ``uv run python -m tests``.

Each module is also runnable on its own (``python -m tests.test_model``); this
just saves remembering them.
"""


from . import test_model, test_process, test_settings

MODULES = (test_model, test_settings, test_process)


def main() -> int:
    """Run each test module and report a combined exit code."""
    failed = 0
    for module in MODULES:
        print(f"\n=== {module.__name__} ===")
        failed += module.main()
    # Each module's `main` answers 1 when *it* failed, so `failed` counts modules,
    # not tests — the per-module summary above already prints the test ratio.
    print(
        f"\nFAILED: {failed}/{len(MODULES)} module(s)" if failed
        else f"\nOK: {len(MODULES)} module(s)"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
