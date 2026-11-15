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

#: Every child script's preamble. Qt's build tools sit beside the interpreter, and
#: `shutil.which` only finds them when `Scripts/` is on PATH — which `uv run`
#: arranges and a direct `.venv/Scripts/python.exe` invocation does not. Resolving
#: beside the interpreter first keeps the suite runnable either way. Concatenated
#: *after* the dedent on purpose: the scripts below are written indented.
TOOL_LOOKUP = '''\
import os
import shutil
import sys
from pathlib import Path

def lrelease() -> str:
    """pyside6-lrelease, beside this interpreter first, then on PATH."""
    beside = Path(sys.executable).with_name(
        "pyside6-lrelease" + (".exe" if os.name == "nt" else ""))
    if beside.is_file():
        return str(beside)
    return shutil.which("pyside6-lrelease") or "pyside6-lrelease"
'''


def run_script(source: str) -> list[Any]:
    """Run a small script in a fresh interpreter and return its JSON events."""
    path = Path(tempfile.mkdtemp(prefix="symplify_process_")) / "smoke.py"
    path.write_text(TOOL_LOOKUP + textwrap.dedent(source), encoding="utf-8")
    env = {**os.environ}
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [PYTHON, str(path)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
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
    assert events[:2] == [["result", "ResultView"], ["variants", 1]]


def test_importing_the_entry_point_is_worker_safe():
    """Spawn re-imports main.py in every worker; it must not pull Qt/SymPy in.

    The UI imports live inside `main()` now. Before that, a calculation worker
    paid for PySide6/qmlmathplot before its own target even started.
    """
    events = run_script(
        r"""
        import json
        import sys
        import main
        print(json.dumps({
            "pyside": any(name.startswith("PySide6") for name in sys.modules),
            "sympy": "sympy" in sys.modules,
            "qmlmathplot": any(name.startswith("qmlmathplot") for name in sys.modules),
        }))
        """
    )
    assert events == {"pyside": False, "sympy": False, "qmlmathplot": False}


def test_process_backend_attaches_plot_programs():
    """The worker builds qmlmathplot Programs; the UI never parses for the plot."""
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
                events.append([type(result).__name__, len(result.plot),
                               result.plot[0].label if result.plot else ""])
                app.quit()

            backend.finished.connect(finished)
            backend.failed.connect(lambda request_id, message: (
                events.append(["failed", message]), app.quit()))
            backend.submit(1, "evaluate", "x**2", {})
            QTimer.singleShot(15000, app.quit)
            app.exec()
            backend.shutdown()
            print(json.dumps(events))

        if __name__ == "__main__":
            main()
        """
    )
    assert events == [["ResultView", 1, "x**2"]]


def test_variable_writes_cross_a_real_worker():
    """The Variables page's writes use their own spawned worker.

    A successful add only reaches the model when the worker answers, and the
    row carries the canonical expression — the UI process never parsed it.
    """
    events = run_script(
        r"""
        import json
        from PySide6.QtCore import QCoreApplication, QTimer
        from python.store_worker import VariableStore
        from python.viewmodel.calculation_backend import ProcessBackend
        from python.viewmodel.variables_viewmodel import VariablesModel

        def main():
            app = QCoreApplication([])
            backend = ProcessBackend(timeout_seconds=30.0)
            model = VariablesModel(None, backend=backend, store=VariableStore())
            events = []

            def added(name, ok):
                events.append([name, ok, model.cellAt(0, 1),
                               model.cellAt(1, 1) if model.rowCount() > 1 else ""])
                if len(events) == 1:
                    model.add("b", "3")
                else:
                    app.quit()

            model.variableAdded.connect(added)
            model.add("a", "2")
            QTimer.singleShot(15000, app.quit)
            app.exec()
            backend.shutdown()
            print(json.dumps(events))

        if __name__ == "__main__":
            main()
        """
    )
    assert events == [["a", True, "2", ""], ["b", True, "2", "3"]]


def test_the_keyboard_target_uses_the_windows_active_focus_item():
    """The on-screen keyboard must find the focused editor without walking the tree.

    `InputPane.keyboardTarget()` used to recurse over every child (the 200+ keys
    included) on each virtual key press. It now takes `Window.activeFocusItem`
    and keeps the two rules the walk encoded: the input must belong to the pane,
    and it must be a text control. `T.TextArea`/`T.TextField` are the template
    bases, so RinUI's TextArea and the Basic-derived CodeField both match (the
    unqualified style names shadow each other and made a Basic field fall back to
    the wrong editor).

    The window has to be real for `activeFocusItem` to be populated; that is why
    this runs in a child interpreter with a QGuiApplication, like the process
    tests beside it.
    """
    events = run_script(
        r"""
        import json
        import os
        import tempfile
        from pathlib import Path

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

        from PySide6.QtCore import QObject, QTimer, QUrl, Slot
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlComponent, QQmlEngine
        from RinUI.core.config import RINUI_PATH

        from python.settings import SettingsStore
        from python.viewmodel.main_viewmodel import MainViewModel

        class Probe(QObject):
            def __init__(self):
                super().__init__()
                self.events = []

            @Slot(str, bool)
            def record(self, name, ok):
                self.events.append([name, ok])

            @Slot()
            def finish(self):
                print(json.dumps(self.events))
                QGuiApplication.instance().quit()

        def main():
            app = QGuiApplication([])
            store = SettingsStore(Path(tempfile.mkdtemp()) / "config.yaml")
            store.load()
            vm = MainViewModel(store)
            engine = QQmlEngine()
            engine.addImportPath(str(RINUI_PATH))
            ctx = engine.rootContext()
            for name, obj in {
                "vm": vm,
                "calcVM": vm.calculator,
                "varsVM": vm.variables,
                "variablesModel": vm.variables.model,
                "variablesFilter": vm.variablesFilter,
                "historyVM": vm.history,
                "historyFilter": vm.historyFilter,
                "historyWindow": vm.historyWindow,
                "logVM": vm.log,
                "settingsVM": vm.settings,
            }.items():
                ctx.setContextProperty(name, obj)
            probe = Probe()
            ctx.setContextProperty("probe", probe)
            component = QQmlComponent(engine)
            component.setData(b'''import QtQuick
        import QtQuick.Window 2.15
        import QtQuick.Controls
        import "components"

        Window {
            width: 900
            height: 600
            visible: true

            InputPane { id: pane; anchors.fill: parent }
            TextField { id: outsideField; objectName: "outsideField" }

            Timer {
                id: first
                interval: 120
                running: true
                onTriggered: {
                    probe.record("own input", pane.editableInPane(pane.codeInput) === pane.codeInput)
                    probe.record("outside field", pane.editableInPane(outsideField) === null)
                    probe.record("nothing", pane.editableInPane(null) === null)

                    calcVM.inputMode = 1
                    pane.focusAssignName()
                    second.start()
                }
            }
            Timer {
                id: second
                interval: 120
                onTriggered: {
                    probe.record("focused name", pane.keyboardTarget().placeholderText === "name")
                    outsideField.forceActiveFocus()
                    third.start()
                }
            }
            Timer {
                id: third
                interval: 120
                onTriggered: {
                    probe.record("mode fallback", pane.keyboardTarget().placeholderText === "expression")
                    probe.finish()
                }
            }
        }''', QUrl.fromLocalFile(str(Path("qml/harness.qml").resolve())))
            obj = component.create(ctx)
            assert obj is not None, component.errorString()
            obj.requestActivate()
            QTimer.singleShot(5000, app.quit)
            app.exec()

        if __name__ == "__main__":
            main()
        """
    )
    assert events == [
        ["own input", True],
        ["outside field", True],
        ["nothing", True],
        ["focused name", True],
        ["mode fallback", True],
    ]


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
    assert events[:2] == [["result", "ResultView"], ["variants", 0]]
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
        import subprocess
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
                [lrelease(),
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
                [lrelease(),
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


def test_a_render_past_its_deadline_fails_instead_of_hanging():
    """A render that never comes back must not leave the UI waiting forever.

    The renderer runs in a separate process, so a pathological layout (or a
    wedged ziamath) used to leave the token pending forever: the pipe stayed open,
    the poll timer kept running and the artwork never arrived. The service now
    treats a missed deadline as a dead renderer: every pending token fails and the
    child is retired, so the next request starts fresh. This exercises the expiry
    branch directly — a real 10 s wait is not a unit test.
    """
    import time

    from python.latex_render import LatexStyle
    from python.viewmodel.latex_service import LatexRenderService

    service = LatexRenderService()
    failures = []
    service.failed.connect(lambda token, message: failures.append((token, message)))
    service._pending["expired"] = (("x", LatexStyle()), 0)
    service._deadline = time.monotonic() - 1

    service._poll()

    assert failures and "exceeded" in failures[0][1]
    assert not service._pending


def test_the_store_worker_crosses_a_real_process():
    events = run_script(
        r"""
        import json
        from python.child_process import ChildProcess
        from python.store_worker import worker_main
        from python.worker_protocol import CommitRequest, StoreEntryCandidate

        def main():
            child = ChildProcess(worker_main)
            events = []
            try:
                pipe = child.ensure()
                pipe.send((1, "snapshot", None))
                request_id, kind, snapshot = pipe.recv()
                events.append([request_id, kind, snapshot.revision, len(snapshot.entries)])

                pipe.send((2, "commit", CommitRequest(
                    0,
                    StoreEntryCandidate(
                        name="x",
                        srepr="Symbol('x')",
                        display="x",
                        type_label="Symbol",
                        latex="x",
                    ),
                )))
                request_id, kind, reply = pipe.recv()
                events.append([request_id, kind, reply.ok, reply.revision,
                               reply.delta.base_revision, reply.delta.revision])

                pipe.send((3, "snapshot", None))
                request_id, kind, snapshot = pipe.recv()
                events.append([request_id, kind, snapshot.revision,
                               [entry.name for entry in snapshot.entries]])
            finally:
                child.stop()
            print(json.dumps(events))

        if __name__ == "__main__":
            main()
        """
    )
    assert events == [
        [1, "snapshot", 0, 0],
        [2, "reply", True, 1, 0, 1],
        [3, "snapshot", 1, ["x"]],
    ]


def test_the_compute_worker_caches_scope_revisions():
    events = run_script(
        r"""
        import json
        from python.backend_worker import worker_main
        from python.child_process import ChildProcess
        from python.worker_protocol import ScopeChange, ScopeDelta, ScopeSnapshot, StoreEntry

        def entry(name, revision, srepr):
            return StoreEntry(
                name=name,
                srepr=srepr,
                display=name,
                type_label="Integer",
                latex="",
                revision=revision,
                valid=True,
            )

        def main():
            child = ChildProcess(worker_main)
            events = []
            try:
                pipe = child.ensure()
                snapshot = ScopeSnapshot(1, (entry("x", 1, "Symbol('x')"),))
                pipe.send((1, "evaluate", "x + 1", snapshot))
                result = pipe.recv()
                events.append(["snapshot", type(result[2]).__name__, result[2].text])
                pipe.recv()  # optional variants

                delta = ScopeDelta(
                    1,
                    2,
                    (ScopeChange("x", 2, entry("x", 2, "Integer(5)")),),
                )
                pipe.send((2, "evaluate", "x + 1", delta))
                result = pipe.recv()
                events.append(["delta", type(result[2]).__name__, result[2].text])
                pipe.recv()  # optional variants
            finally:
                child.stop()
            print(json.dumps(events))

        if __name__ == "__main__":
            main()
        """
    )
    assert events == [
        ["snapshot", "ResultView", "x + 1"],
        ["delta", "ResultView", "6"],
    ]


def test_building_the_app_viewmodels_does_not_import_sympy():
    events = run_script(
        r"""
        import json
        import sys
        import tempfile
        from pathlib import Path

        from PySide6.QtCore import QCoreApplication

        from python.settings import SettingsStore
        from python.store_worker import VariableStore
        from python.viewmodel.calculation_backend import ProcessBackend
        from python.viewmodel.main_viewmodel import MainViewModel

        def main():
            app = QCoreApplication([])
            settings = SettingsStore(Path(tempfile.mkdtemp()) / "config.yaml")
            settings.load()
            store = VariableStore()
            calculator = ProcessBackend()
            variables = ProcessBackend()
            try:
                MainViewModel(
                    settings,
                    calculation_backend=calculator,
                    variables_backend=variables,
                    store_client=store,
                )
                print(json.dumps({
                    "sympy": "sympy" in sys.modules,
                    "model": "python.model" in sys.modules,
                }))
            finally:
                calculator.shutdown()
                variables.shutdown()

        if __name__ == "__main__":
            main()
        """
    )
    assert events == {"sympy": False, "model": False}


def test_the_store_client_persists_variables_between_runs():
    events = run_script(
        r"""
        import json
        import tempfile
        from pathlib import Path

        from python.store_client import StoreClient, plotting_seeds
        from python.worker_protocol import CommitRequest, StoreEntryCandidate

        def main():
            path = Path(tempfile.mkdtemp()) / "variables.json"
            first = StoreClient(path)
            try:
                first.bootstrap(plotting_seeds())
                assert first.commit(CommitRequest(
                    first.snapshot().revision,
                    StoreEntryCandidate(
                        name="a", srepr="Integer(5)", display="5",
                        type_label="Integer", latex="a = 5",
                    ),
                )).ok
            finally:
                first.close()

            second = StoreClient(path)
            try:
                snapshot = second.bootstrap(plotting_seeds())
            finally:
                second.close()

            data = json.loads(path.read_text(encoding="utf-8"))
            print(json.dumps({
                "names": [entry.name for entry in snapshot.entries],
                "sympy_version": data["sympy_version"],
            }))

        if __name__ == "__main__":
            main()
        """
    )
    assert events["names"] == ["x", "y", "a"]
    assert events["sympy_version"]


def test_the_store_client_bootstraps_and_commits_in_a_child():
    events = run_script(
        r"""
        import json
        from python.store_client import StoreClient, plotting_seeds
        from python.worker_protocol import CommitRequest, StoreEntryCandidate

        def main():
            client = StoreClient()
            try:
                snapshot = client.bootstrap(plotting_seeds())
                reply = client.commit(CommitRequest(
                    snapshot.revision,
                    StoreEntryCandidate(
                        name="a",
                        srepr="Integer(5)",
                        display="5",
                        type_label="Integer",
                        latex="a = 5",
                    ),
                ))
                final = client.snapshot()
                print(json.dumps({
                    "seed_revision": snapshot.revision,
                    "reply": [reply.ok, reply.revision],
                    "names": [entry.name for entry in final.entries],
                    "a": next(
                        entry.display for entry in final.entries if entry.name == "a"
                    ),
                }))
            finally:
                client.close()

        if __name__ == "__main__":
            main()
        """
    )
    assert events == {
        "seed_revision": 2,
        "reply": [True, 3],
        "names": ["x", "y", "a"],
        "a": "5",
    }


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
