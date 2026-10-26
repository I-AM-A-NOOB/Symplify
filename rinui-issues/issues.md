# RinUI issues we patch

Target: **RinUI 0.4.4.1** (PyPI, 2026-08-30).

This list is deliberately filtered: it contains only places where the behavior is
clearly RinUI's responsibility — a bug, a broken contract, or a WinUI imitation
that behaves differently from WinUI. Generic Qt traps, app-specific layout
decisions, and test-harness-only behavior are not included unless RinUI is the
direct cause.

No file inside `RinUI` is edited. "Patch" below means a runtime monkeypatch, a
project-local QML shadow type, or a call-site workaround in this repository.

**Excluded on purpose:** Qt's text-field context menu (anchored to the caret by
Qt's style), startup resize/maximize DWM desync (Windows/Qt window lifecycle),
NavigationView's default page recreation (the same as WinUI's default; missing
cache is a feature request), and test-harness-only page rendering.

## Runtime patches

### 1. Import writes a config file into the current working directory

**Upstream**
`RinUI/core/config.py` computes `BASE_DIR = Path.cwd().resolve()` and creates
`<cwd>/RinUI/config/rin_ui.json` while the package is being imported. There is no
supported environment variable or argument to redirect or disable this write.
Importing a UI library must not create a directory in the caller's working
directory; this also affects build tools that merely import RinUI to analyze it.

**Local patch**
- `python/rinui_bootstrap.py` changes the working directory to a temporary
  directory for the duration of `import RinUI`, then removes it.
- It injects our appearance values into `RinConfig.config` and replaces
  `RinConfig.save_config` with a no-op, so later theme changes cannot write a
  second source of truth.
- It migrates a legacy `<app>/RinUI/config/rin_ui.json` into our settings file
  once, then removes the empty RinUI directory.
- `scripts/build_windows.py` repeats the cleanup after Nuitka's own import.

**Upstream fix**
Make import side-effect free. Accept an explicit config path, or defer the
directory/file creation until `RinConfig` is actually saved.

**Files**: `python/rinui_bootstrap.py`, `scripts/build_windows.py`

### 2. Title-bar drag moves the window twice

**Upstream**
RinUI's title bar starts a native move on press, but its
`onPositionChanged` also does `window.setX(window.x + delta.x)`. The guard meant
to suppress the manual move tests `Qt.platform.os !== "windows"`, which is true
everywhere *except* Windows; its other disjuncts (`window.isMaximized`,
`window.isFullScreen`) are not defined by RinUI at all. When the first drag
un-maximizes the window, the title bar's local coordinates shift and the manual
move teleports the window to the screen corner.

**Local patch**
- `python/window_drag.py` subclasses `WinEventManager` and replaces its
  `drag_window_event` with a real caption press:
  `WM_NCLBUTTONDOWN` + `HTCAPTION`.
- It also exposes `dragInProgress` for the whole gesture, including queued mouse
  events.
- `qml/MainWindow.qml` folds that flag into `isMaximized`, which is what RinUI's
  guard reads.

**Upstream fix**
Use the caption-press message, or remove the manual `setX` move entirely. Define
`isMaximized`/`isFullScreen`, and fix the platform condition.

**Files**: `python/window_drag.py`, `python/rinui_bootstrap.py`,
`qml/MainWindow.qml`

### 3. Taskbar icon is lost after RinUI changes window flags

**Upstream**
`FluentWindowBase.Component.onCompleted` clears `FramelessWindowHint` after the
window has already been shown. Changing window flags makes Qt recreate the
native window, and the Windows taskbar snapshots the button icon when that
window appears. `QApplication.setWindowIcon` only sets the application/class
fallback, so the button can keep `IDI_APPLICATION` while Alt+Tab shows the right
icon.

**Local patch**
- `main.py` calls `window.root_window.setIcon(icon)` again after
  `window.load()`, which makes the taskbar re-read it.
- `python/window_icon.apply_to_window_class()` also sets `GCLP_HICON` and
  `GCLP_HICONSM` on the window class, so the fallback icon is ours before the
  shell first snapshots it.

**Upstream fix**
Do not clear `FramelessWindowHint` after the window is shown, or expose a
post-show hook and re-apply the window icon after any flag change that recreates
the native window.

**Files**: `main.py`, `python/window_icon.py`

### 4. Expander's `z: 999` blocker eats every text cursor

**Upstream**
`RinUI/components/Layout/Expander.qml` places a full-size `MouseArea` at
`z: 999` with `preventStealing: true`. It declares no `cursorShape`. Qt takes the
cursor from the topmost item under the pointer, so the blocker's arrow beats the
I-beam of every `TextField`, `TextArea`, `SpinBox`, and combo box inside the
expander. The blocker's own `enabled` is only meant to cover the disabled
expander, but its `visible` is always true.

**Local patch**
- `qml/components/ExpanderPanel.qml` (plain `Expander`)
- `qml/components/ExpanderRow.qml` (`SettingExpander`)

Both find the blocker after creation and bind
`blocker.visible = blocker.enabled`, preserving click blocking only while the
expander is disabled.

**Upstream fix**
Make the blocker visible only when the expander is disabled, or give it
`cursorShape: Qt.ArrowCursor` without covering child controls' cursor logic.

**Files**: `qml/components/ExpanderPanel.qml`, `qml/components/ExpanderRow.qml`

### 5. `ScrollableTextArea` cannot size or scroll correctly

**Upstream**
`RinUI/components/Text/ScrollableTextArea.qml` binds
`implicitHeight: defaultHeight`, but `defaultHeight` is not defined; every
instance logs `ReferenceError: defaultHeight is not defined`. The wrapper also
does not scroll its content when the text overflows: with 80 log lines the view
stayed on the oldest entries, clipped by the card, with no visible bar.

**Local patch**
There is no complete local replacement. The components are used only where the
content is bounded, and the Log page keeps its own tail-follow behavior. The
warning is tolerated as upstream noise.

**Upstream fix**
Define a real default height (or remove the binding), give the inner
`TextArea` an explicit height, and make the `ScrollView` actually scroll the
text document.

**Files**: `qml/pages/LogPage.qml`, `qml/pages/CalculatorPage.qml`
(consumers), `python/log_viewmodel.py`

### 6. `TableView` disables its own mouse/edit handling

**Upstream**
`RinUI/components/ListAndCollections/TableView.qml` sets
`acceptedButtons: Qt.NoButton` to stop its selection logic being overwritten.
That also removes standard mouse handling and the built-in edit triggers.
`TableViewDelegate.qml` paints the view's `currentRow` as selected in addition to
the actual selection, and this build has no `selectRow()`. Its inline editor is a
bare `TextField`, which has no `textDocument`, so it cannot accept a code
highlighter.

**Local patch**
- `qml/pages/VariablesPage.qml` restores `acceptedButtons: Qt.LeftButton`,
  selects through `selectionModel.setCurrentIndex(...)`, and uses a custom
  `TableView.editDelegate`.
- `qml/components/VariableCellEditor.qml` provides `TextArea`-based editors
  with a `textDocument`, a delegate-owned commit path, and explicit
  `visible: !cell.editing` handling.
- The table's inert horizontal/vertical bars are declared away with
  `ScrollBar.horizontal: null` / `ScrollBar.vertical: null`.

**Upstream fix**
Do not disable mouse handling globally to fix selection. Provide a supported
`selectRow`, let the edit trigger be configurable, and make the default editor
capable of hosting a highlighter (`TextArea`/`TextEdit`).

**Files**: `qml/pages/VariablesPage.qml`,
`qml/components/VariableCellEditor.qml`

### 7. `Button` / `ToolButton` semantics are inconsistent with their API

**Upstream**
- `RinUI/components/BasicInput/Button.qml` resolves
  `backgroundColor` as `flat ? subtleSecondaryColor : highlighted ? primaryColor : controlColor`.
  A flat `highlighted` button is therefore not an accent button.
- `Button.qml` exposes `textColor` but its labels do not consistently honor it;
  icon color handling is separate again.
- `RinUI/components/BasicInput/ToolButton.qml` always draws `text` beside the
  icon. `display: AbstractButton.IconOnly` has no effect, so an action with a
  label becomes a full sentence-wide button.
**Local patch**
- `qml/components/CommandBar.qml` drives one `Action` into either a
  `ToolButton` or a `MenuItem`, binds the icon explicitly, puts labels in the
  tooltip, and keeps accent actions as separate `Button`s outside the bar.
**Upstream fix**
Honor `display`, `textColor`, and `icon.color`; define a clear precedence for
`flat` vs `highlighted`.

**Files**: `qml/components/CommandBar.qml`

### 8. `Menu` popup position and reopen behavior

**Upstream**
`RinUI/components/MenusAndToolbars/Menu.qml` animates `x`/`y` towards
`posX`/`posY` in its `enter` transition. A point passed to `popup(x, y)` is
overwritten by the animation, so delegate context menus open under the wrong
item. The same `Menu` has an exit transition; `popup()` immediately after
`close()` is swallowed while the popup is still exiting, and a second gesture
fades the old menu out at the old point before opening at the new one.

**Local patch**
- `qml/components/CodeContextMenu.qml` declares the menu inside its own
  `MouseArea`, sets `posX`/`posY` before `popup()`, and sets `exit: null` so a
  re-open is synchronous.
- `qml/components/HistoryCard.qml` uses the `open → close → onClosed → open`
  hand-off for its delegate menu, where `posX`/`posY` cannot be changed on an
  open menu.
- `qml/components/CopyableLabel.qml` forwards right clicks in the label's own
  coordinates, so the card can open the menu at the pointer.

**Upstream fix**
Provide a stable `popupAt(x, y)` that is authoritative over `enter`, and make
re-opening an already-open menu atomic. If the exit animation stays, document
that `popup()` immediately after `close()` cannot work.

**Files**: `qml/components/CodeContextMenu.qml`,
`qml/components/HistoryCard.qml`, `qml/components/CopyableLabel.qml`

## QML shadow/replacement components

### 9. `SelectorBarItem` and `SegmentedItem` have no keyboard-focus visual

**Upstream**
Both components render a selected `Indicator` but no `FocusIndicator`. A fully
keyboard-driven tab row therefore has no visible focus, unlike WinUI's
`SelectorBar` / segmented controls.

**Local patch**
- `qml/components/SelectorBarItem.qml` and
  `qml/components/SegmentedItem.qml` inherit the RinUI types and add the app's
  `ProjectFocusIndicator`.
- `qml/components/ProjectFocusIndicator.qml` centralizes the ring radius and
  probe `objectName`.

**Upstream fix**
Include focus visuals in the component, or document the intended way to add them
without shadowing the type.

**Files**: `qml/components/SelectorBarItem.qml`,
`qml/components/SegmentedItem.qml`, `qml/components/ProjectFocusIndicator.qml`

### 10. `RinUI.AdvancedComponents` is not importable; `Indicator` geometry is fixed

**Upstream**
`RinUI/components/qmldir` declares `module RinUI.AdvancedComponents`, but that
URI is not importable in this build (module URIs resolve by directory name).
`Indicator` sizes itself from a hardcoded ~38px row (`currentItemHeight - 23`),
which does not fit the History page's taller, variable-height cards.

**Local patch**
- The History card draws its own accent bar with the tuned `height - 40` inset
  instead of instantiating `Indicator`.
- `FocusIndicator` remains the root-module import used for focus rings.

**Upstream fix**
Register/export the module correctly (or expose `Indicator` from the root
module) and make its geometry item-relative rather than row-height-relative.

**Files**: `qml/components/HistoryCard.qml`

### 11. `SettingItem` / `SettingCard` / `SettingExpander` API is too rigid

**Upstream**
The installed components do not match the published documentation:
- `SettingCard.icon` is effectively read-only (`icon.name:` is the writable part).
- A `SettingCard`'s bare children land in its right-hand slot; a
  `SettingExpander`'s bare children are collapsible content; `SettingItem` has no
  `content` property.
- `SettingItem` caps its label column at 60% and splits the remaining width by
  content width, so a field cannot take the row width and a radio cannot lead its
  own label.
**Local patch**
- `qml/components/SettingRowBase.qml` collapses `SettingItem`'s label column
  with pinned empty `title`/`description` and renders the app's own label.
- `SettingFieldRow.qml` gives a text field the full row width;
  `RadioSettingRow.qml` puts the radio before its label;
  `RadioSettingGroup.qml` supplies the group surface and exclusivity via the
  caller's setting.

**Upstream fix**
Publish an API matching the installed version, make the left label column
optional, expose a general content slot, and provide/document a group/radio
pattern for exclusive rows.

**Files**: `qml/components/SettingRowBase.qml`,
`qml/components/SettingFieldRow.qml`,
`qml/components/RadioSettingRow.qml`,
`qml/components/RadioSettingGroup.qml`

### 12. ScrollView/ScrollBar integration leaks Qt style bars

**Upstream**
RinUI ships a `ScrollView.qml` but does not register it as the type users get
from `QtQuick.Controls`; that style creates its own bars and the page cannot name
them. Assigning `verticalScrollBar` / `horizontalScrollBar` on several views is
silently ignored because the bars bind their own `policy`; only
`ScrollBar.horizontal: null` / `ScrollBar.vertical: null` removes them. Inert
bars can still render as a full-width strip when the content fits. RinUI's
overlay bar also occupies the bottom edge of horizontal strips, where its arrow
buttons overlap formulas.

**Local patch**
- `qml/components/PageBody.qml` attaches `Rin.ScrollBar.vertical` once and owns
  the Flickable geometry.
- `qml/pages/VariablesPage.qml` explicitly nulls both table bars.
- `qml/components/HScrollView.qml` and `MathStrip.qml` reserve `barRoom` for
  the overlay arrow row.

**Upstream fix**
Register a usable `ScrollView`, expose bar slots that can be replaced, avoid
drawing bars that cannot scroll, and document the overlay bar's occupied height.

**Files**: `qml/components/PageBody.qml`, `qml/pages/VariablesPage.qml`,
`qml/components/HScrollView.qml`, `qml/components/MathStrip.qml`

## Window / navigation design issues

### 13. Top/Bottom navigation sections are capped at 20% of the window

**Upstream**
RinUI caps `Position.Top` and `Position.Bottom` navigation items at 20% of the
window height. WinUI does not impose that layout rule; it makes a small
top/bottom group scroll or split unexpectedly.

**Local patch**
Main items are left unpositioned (middle); only Log/Settings are pinned to
`Position.Bottom`.

**Upstream fix**
Remove the 20% cap or make it configurable; let the navigation view scroll only
when its own content overflows.

**Files**: `qml/MainWindow.qml`

## Known RinUI errors not patched

These are clearly upstream but currently only tolerated:

- `RinUI.Dialog` logs `TypeError: Cannot read property 'width'/'height' of null`
  from its own `Dialog.qml` while binding before it is shown; `Slider` produces
  similar construction warnings.
- `ScrollableTextArea` logs `ReferenceError: defaultHeight is not defined` on
  every instance.

They are not page bugs; do not chase them in app code.
