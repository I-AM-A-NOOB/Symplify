"""Process-boundary tests.

The model tests intentionally use an in-process backend. These tests exercise
the real spawn/pipe code in a child interpreter so a QCoreApplication created
for one test cannot change the in-process tests' rendering path.

Run from the repository root:

    uv run python -m tests.test_process
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def run_script(source: str) -> list[Any]:
    """Run a small script in a fresh interpreter and return its JSON events."""
    path = Path(tempfile.mkdtemp(prefix="symplify_process_")) / "smoke.py"
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    env = {**os.environ}
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [PYTHON, str(path)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_process_backend_sends_result_before_variants():
    events = run_script(
        r"""
        import json
        from PySide6.QtCore import QCoreApplication, QTimer
        from python.viewmodel.calculation_backend import ProcessBackend

        def main():
            app = QCoreApplication([])
            backend = ProcessBackend(timeout_seconds=30.0)
            events = []

            def finished(request_id, result):
                events.append(["result", type(result).__name__])

            def variants(request_id, rows):
                events.append(["variants", len(rows)])
                app.quit()

            backend.finished.connect(finished)
            backend.variantsReady.connect(variants)
            backend.failed.connect(lambda request_id, message: (
                events.append(["failed", message]), app.quit()))
            backend.submit(1, "evaluate", "sqrt(2)", {})
            QTimer.singleShot(15000, app.quit)
            app.exec()
            backend.shutdown()
            print(json.dumps(events))

        if __name__ == "__main__":
            main()
        """
    )
    assert events[:2] == [["result", "Success"], ["variants", 1]]


def test_variant_timeout_does_not_fail_the_result():
    events = run_script(
        r"""
        import json
        from PySide6.QtCore import QCoreApplication, QTimer
        from python.viewmodel.calculation_backend import ProcessBackend

        def main():
            app = QCoreApplication([])
            backend = ProcessBackend(timeout_seconds=30.0)
            backend.VARIANTS_TIMEOUT_SECONDS = 0.05
            events = []

            def finished(request_id, result):
                events.append(["result", type(result).__name__])

            def variants(request_id, rows):
                events.append(["variants", len(rows)])
                app.quit()

            backend.finished.connect(finished)
            backend.variantsReady.connect(variants)
            backend.failed.connect(lambda request_id, message: (
                events.append(["failed", message]), app.quit()))
            backend.submit(1, "evaluate", "Integral(sin(x**2), x)", {})
            QTimer.singleShot(15000, app.quit)
            app.exec()
            backend.shutdown()
            print(json.dumps(events))

        if __name__ == "__main__":
            main()
        """
    )
    assert events[:2] == [["result", "Success"], ["variants", 0]]
    assert not any(event[0] == "failed" for event in events)


def test_latex_renderer_process_returns_svg():
    events = run_script(
        r"""
        import json
        from PySide6.QtCore import QCoreApplication, QTimer
        from python.latex_render import LatexStyle
        from python.viewmodel.latex_service import LatexRenderService

        def main():
            app = QCoreApplication([])
            service = LatexRenderService(app)
            events = []

            def rendered(token, url, width, height):
                events.append(["rendered", token,
                               url.startswith("data:image/svg+xml"),
                               width > 0, height > 0])
                app.quit()

            service.rendered.connect(rendered)
            service.failed.connect(lambda token, message: (
                events.append(["failed", message]), app.quit()))
            service.request("r", r"\sqrt{2}", LatexStyle())
            QTimer.singleShot(15000, app.quit)
            app.exec()
            service.shutdown()
            print(json.dumps(events))

        if __name__ == "__main__":
            main()
        """
    )
    assert events == [["rendered", "r", True, True, True]]


def test_stale_renderer_jobs_are_skipped():
    events = run_script(
        r"""
        import json
        from PySide6.QtCore import QCoreApplication, QTimer
        from python.latex_render import LatexStyle
        from python.viewmodel.latex_service import LatexRenderService

        def main():
            app = QCoreApplication([])
            service = LatexRenderService(app)
            events = []

            def rendered(token, url, width, height):
                events.append(token)
                if token == "second":
                    app.quit()

            service.rendered.connect(rendered)
            service.failed.connect(lambda token, message: (
                events.append("failed"), app.quit()))
            style = LatexStyle()
            service.request("first", r"\sqrt{2}", style)
            service.begin_generation("calculator")
            service.request("second", r"\sqrt{3}", style)
            QTimer.singleShot(15000, app.quit)
            app.exec()
            service.shutdown()
            print(json.dumps(events))

        if __name__ == "__main__":
            main()
        """
    )
    assert events == ["second"]


def test_language_catalogue_loads_and_switches():
    events = run_script(
        r"""
        import json
        import shutil
        import subprocess
        import sys
        import tempfile
        from pathlib import Path

        from PySide6.QtCore import QCoreApplication

        from python.settings import SettingsStore
        from python.viewmodel.settings_viewmodel import SettingsViewModel

        def main():
            root = Path(tempfile.mkdtemp())
            (root / "symplify_zh_CN.ts").write_text(
                '<?xml version="1.0" encoding="utf-8"?>'
                '<TS version="2.1" language="zh_CN">'
                '<context><name>SettingsLanguageSection</name><message>'
                '<source>Display language</source><translation>显示语言</translation>'
                '</message></context></TS>',
                encoding="utf-8",
            )
            subprocess.run(
                [shutil.which("pyside6-lrelease"),
                 str(root / "symplify_zh_CN.ts"),
                 "-qm", str(root / "symplify_zh_CN.qm")],
                check=True, capture_output=True,
            )
            app = QCoreApplication([])
            store = SettingsStore(Path(tempfile.mkdtemp()) / "config.yaml")
            store.load()
            store.set("appearance.language", "zh_CN")
            vm = SettingsViewModel(store, translation_dir=root)
            events = [QCoreApplication.translate(
                "SettingsLanguageSection", "Display language")]
            vm.language = "en"
            events.append(QCoreApplication.translate(
                "SettingsLanguageSection", "Display language"))
            events.append([entry["code"] for entry in vm.languages])
            print(json.dumps(events))

        if __name__ == "__main__":
            main()
        """
    )
    assert events == ["显示语言", "Display language", ["en", "zh_CN"]]


def test_english_catalogue_can_override_source_copy():
    events = run_script(
        r"""
        import json
        import shutil
        import subprocess
        import tempfile
        from pathlib import Path

        from PySide6.QtCore import QCoreApplication

        from python.settings import SettingsStore
        from python.viewmodel.settings_viewmodel import SettingsViewModel

        def main():
            root = Path(tempfile.mkdtemp())
            (root / "symplify_en.ts").write_text(
                '<?xml version="1.0" encoding="utf-8"?>'
                '<TS version="2.1" language="en">'
                '<context><name>SettingsLanguageSection</name><message>'
                '<source>Display language</source>'
                '<translation>Interface language</translation>'
                '</message></context></TS>',
                encoding="utf-8",
            )
            subprocess.run(
                [shutil.which("pyside6-lrelease"),
                 str(root / "symplify_en.ts"),
                 "-qm", str(root / "symplify_en.qm")],
                check=True, capture_output=True,
            )
            app = QCoreApplication([])
            store = SettingsStore(Path(tempfile.mkdtemp()) / "config.yaml")
            store.load()
            store.set("appearance.language", "en")
            vm = SettingsViewModel(store, translation_dir=root)
            print(json.dumps([QCoreApplication.translate(
                "SettingsLanguageSection", "Display language")]))

        if __name__ == "__main__":
            main()
        """
    )
    assert events == ["Interface language"]


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
