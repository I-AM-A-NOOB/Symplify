import QtQuick
import QtQuick.Controls 2.15
import QtQuick.Layouts 2.15
import QtQuick.Window 2.15
import RinUI
import RinUI as Rin
import QmlMathPlot 1.0
import Qt5Compat.GraphicalEffects
import "../components"

Item {
    id: page

    // The input is RinUI's scrollable text area; the helpers below (focus,
    // insert, selectAll, fallbackTarget) address the text item, so this points
    // them at the wrapper's inner area.
    readonly property Item codeInput: codeArea.textArea

    //: The calculation backend's state, shown beside the result's copy actions.
    //: "busy" rather than "calculating…" keeps the row short enough for the
    //: split view's minimum width.
    readonly property string backendStatusText:
        calcVM.backendStatus === "calculating" ? qsTr("Backend: busy")
        : calcVM.backendStatus === "timedout" ? qsTr("Backend: timed out")
        : calcVM.backendStatus === "failed" ? qsTr("Backend: failed")
        : qsTr("Backend: ready")

    readonly property color backendStatusColor:
        calcVM.backendStatus === "timedout" || calcVM.backendStatus === "failed"
            ? Theme.currentTheme.colors.systemCriticalColor
            : calcVM.backendStatus === "calculating"
                ? Theme.currentTheme.colors.primaryColor
                : Theme.currentTheme.colors.textSecondaryColor

    //: The result pane has a minimum that still fits the backend status and the
    //: compact copy buttons, plus a readable width where the copy labels fit.
    //: The plot takes a fixed share when it sits beside the result and the spare
    //: height when it sits below it.
    readonly property int inputPanelWidth: 320
    readonly property int resultPaneMinWidth: 270
    readonly property int resultPaneReadableWidth: 340
    readonly property int resultPaneMinHeight: 140
    readonly property int plotPaneMinWidth: 240
    readonly property int plotPanePreferredWidth: 340
    readonly property int plotPaneMinHeight: 180
    //: WinUI3 ContentSizer measurements are physical pixels: a 20px hover band
    //: and a 36x8 pill. Qt Quick sizes are logical, so divide by the *page's*
    //: current screen DPR. `Utils.dpiScale` is a singleton and can stay on the
    //: primary screen when the window moves; `Screen` attached here follows the
    //: window's screen.
    readonly property real screenDpi: Screen.devicePixelRatio > 0
        ? Screen.devicePixelRatio : 1
    readonly property real paneHandleWidth: 16
    readonly property real splitterPillThickness: 4
    readonly property real splitterPillLength: 24

    //: WinUI3 ContentSizer tones: the rest state is the page surface, the hover
    //: band is the closest neutral fill, and the pill is the opaque system
    //: neutral (not a text colour, so it does not vary with state or alpha).
    readonly property color splitterHoverFill: Theme.currentTheme.isDark
        ? Theme.currentTheme.colors.controlTertiaryColor
        : Theme.currentTheme.colors.subtleSecondaryColor
    readonly property color splitterPillColor:
        Theme.currentTheme.colors.systemNeutralColor

    //: One ratio for both orientations. Dragging the result/plot divider writes
    //: it; rotating the layout reads it back, so the panes keep their relative
    //: share instead of snapping to a default.
    property real resultShare: 0.5

    //: The toolbar labels fit at this content width; below it the two copy
    //: actions become icon-only buttons with their words in tooltips.
    readonly property bool wideHeader: page.width >= 900

    //: Wide layouts put the plot beside the result. The width test is the real
    //: constraint; the ratio keeps a tall, narrow window from looking like a
    //: three-column desktop layout. The plot pane is hidden when there is
    //: nothing to draw, so this is also false then.
    readonly property bool plotBesideResult:
        calcVM.hasPlot
        && resultArea.width >= resultPaneReadableWidth + plotPanePreferredWidth
                                + paneHandleWidth
        && page.width / Math.max(1, page.height) >= 1.2

    //: Which side the previous layout put the plot on. The geometry binds to
    //: this while the flip runs, so the animation starts from a normalized
    //: layout of the *current* container rather than stale pixel sizes.
    property bool layoutFromHorizontal: false
    property bool wasPlotBesideResult: false

    onPlotBesideResultChanged: {
        layoutFromHorizontal = wasPlotBesideResult
        wasPlotBesideResult = plotBesideResult
        splitArea.beginLayoutTransition()
    }

    // The code theme's surface — `background` and `ink` for the ACTIVE theme,
    // since a family has a dark and a light member. An empty value means the
    // family has no opinion (High Contrast Light states neither) and the UI
    // theme's own colours stand in.
    readonly property var codeSurface: settingsVM.codeSurface(Theme.isDark())

    Component.onCompleted: {
        // Code colouring on the input. The item hands over its document, and the
        // palette follows the ACTIVE theme — RinUI resolves Auto against the OS,
        // so ask it rather than the setting.
        vm.attachCodeHighlighting(codeArea.textArea.textDocument, Theme.isDark())
        codeInput.forceActiveFocus()
    }

    function findFocusedEditable(item) {
        if (!item)
            return null
        if (item.activeFocus
                && (item instanceof TextArea
                    || item instanceof TextField
                    || item instanceof TextInput))
            return item
        for (let i = 0; i < item.children.length; i++) {
            const found = findFocusedEditable(item.children[i])
            if (found)
                return found
        }
        return null
    }

    function fallbackTarget() {
        return calcVM.inputMode === 0 ? codeInput : assignValueField
    }

    function keyboardTarget() {
        return findFocusedEditable(page) || fallbackTarget()
    }

    //: Typing over a selection replaces it, like a physical keyboard. QML's
    //: `insert` only inserts at the cursor, so the selection has to go first.
    function removeSelection(target) {
        if (!target || !target.selectedText)
            return false
        const start = Math.min(target.selectionStart, target.selectionEnd)
        const end = Math.max(target.selectionStart, target.selectionEnd)
        target.remove(start, end)
        target.cursorPosition = start
        return true
    }

    function insertToInput(text) {
        const target = keyboardTarget()
        if (!target || !target.insert)
            return
        removeSelection(target)
        target.insert(target.cursorPosition, text)
    }

    function backspaceInput() {
        const target = keyboardTarget()
        if (!target)
            return
        if (removeSelection(target))
            return
        if (target.cursorPosition > 0)
            target.remove(target.cursorPosition - 1, target.cursorPosition)
    }

    function moveInputCursor(delta) {
        const target = keyboardTarget()
        if (!target)
            return
        target.forceActiveFocus()
        let position = target.cursorPosition
        if (target.selectedText) {
            position = delta < 0
                ? Math.min(target.selectionStart, target.selectionEnd)
                : Math.max(target.selectionStart, target.selectionEnd)
            if (target.deselect)
                target.deselect()
        } else {
            position = Math.max(0, Math.min(target.length, position + delta))
        }
        target.cursorPosition = position
    }

    function clearInput() {
        const target = keyboardTarget()
        if (target && target.clear)
            target.clear()
    }

    function undoInput() {
        const target = keyboardTarget()
        if (target && target.undo)
            target.undo()
    }

    function redoInput() {
        const target = keyboardTarget()
        if (target && target.redo)
            target.redo()
    }

    function switchToCode() {
        inputStage.beginModeTransition()
        calcVM.inputMode = 0
        codeInput.forceActiveFocus()
    }

    function switchToAssign() {
        inputStage.beginModeTransition()
        calcVM.inputMode = 1
        assignNameField.forceActiveFocus()
    }

    function runCalculation() {
        if (calcVM.inputMode === 0) {
            const expr = calcVM.inputText.trim()
            if (expr) {
                calcVM.calculate(expr)
                codeInput.selectAll()
                codeInput.forceActiveFocus()
            }
        } else {
            const name = calcVM.assignName.trim()
            const value = calcVM.assignValue.trim()
            if (name && value) {
                calcVM.calculateAssign(name, calcVM.assignOperator, value)
                assignValueField.forceActiveFocus()
            }
        }
    }

    function setExample(expression) {
        switchToCode()
        calcVM.inputText = expression
        runCalculation()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: vm.zenMode ? 16 : 24
        anchors.bottomMargin: 16
        spacing: vm.zenMode ? 0 : 14

        // ---- Page toolbar ----
        //: One row above both panes. The title is the page's, not the input
        //: pane's: it stays put when the input is collapsed and reads as the
        //: heading of the whole workspace. The mode switch and the loud action
        //: live here for the same reason — they act on the page's input, not on
        //: a panel's furniture.
        RowLayout {
            objectName: "calculatorToolbar"
            Layout.fillWidth: true
            spacing: page.wideHeader ? 8 : 6
            visible: !vm.zenMode

            Text {
                //: Windows Calculator's page heading, not another toolbar label.
                //: The 28px face yields to the 20px one before the toolbar
                //: starts dropping controls at the minimum window width.
                typography: page.wideHeader ? Typography.Title : Typography.Subtitle
                text: qsTr("Calculator")
                Layout.alignment: Qt.AlignVCenter
            }

            //: `calcVM.inputMode` is the single source of truth (it survives page
            //: switches); the Segmented only syncs from it, so a rebuilt page
            //: never writes its default index back into the VM.
            Segmented {
                id: modeSwitch

                Layout.alignment: Qt.AlignVCenter
                Component.onCompleted: currentIndex = calcVM.inputMode

                SegmentedItem {
                    text: qsTr("Code")
                    onClicked: page.switchToCode()
                }
                SegmentedItem {
                    text: qsTr("Assign")
                    onClicked: page.switchToAssign()
                }
            }

            Connections {
                target: calcVM

                function onInputModeChanged() {
                    modeSwitch.currentIndex = calcVM.inputMode
                    inputStage.beginModeTransition()
                    if (calcVM.inputMode === 0)
                        codeInput.forceActiveFocus()
                    else
                        assignNameField.forceActiveFocus()
                }
            }

            //: The page's one loud action, outside the bar: it is what this page is
            //: *for*, and it is the only thing here that acts on the input as a
            //: whole. Accent-styled, which RinUI's `Button` draws as its primary
            //: fill — `highlighted`, never `flat`, since `flat` outranks
            //: `highlighted` in the colour choice.
            Button {
                highlighted: true
                text: qsTr("Calculate")
                //: The accent name from the icon font RinUI ships.
                icon.name: "ic_fluent_calculator_20_regular"
                icon.color: enabled
                    ? Theme.currentTheme.colors.textAccentColor
                    : Theme.currentTheme.colors.textDisabledColor
                Layout.alignment: Qt.AlignVCenter

                Tip {
                    text: parent.text
                }

                onClicked: runCalculation()
            }

            //: The examples write into the input instead of acting on it, so
            //: they are a dropdown of their own rather than one more action.
            //: Icon-only here: the bar has to keep the title, the mode and the
            //: loud action in one line at the minimum window width.
            DropDownButton {
                flat: true
                text: ""
                icon.name: "ic_fluent_math_formula_sparkle_20_regular"
                icon.color: enabled
                    ? Theme.currentTheme.colors.textColor
                    : Theme.currentTheme.colors.textDisabledColor
                Layout.alignment: Qt.AlignVCenter
                Accessible.name: qsTr("Examples")

                Tip {
                    text: qsTr("Examples")
                }

                MenuItem {
                    text: "diff(x**2, x)"
                    onTriggered: setExample("diff(x**2, x)")
                }
                MenuItem {
                    text: "integrate(x**2, x)"
                    onTriggered: setExample("integrate(x**2, x)")
                }
                MenuItem {
                    text: "limit(sin(x)/x, x, 0)"
                    onTriggered: setExample("limit(sin(x)/x, x, 0)")
                }
                MenuItem {
                    text: "solve(x**2 - 4, x)"
                    onTriggered: setExample("solve(x**2 - 4, x)")
                }
                MenuItem {
                    text: "Matrix([[1, 2], [3, 4]])"
                    onTriggered: setExample("Matrix([[1, 2], [3, 4]])")
                }
            }

            //: Clear stays a normal, icon-only toolbar button. Undo and Redo do
            //: not live here: they belong with the cursor keys they edit beside
            //: (see `KeyboardPanel`), which is also where the mock-up puts them.
            ToolButton {
                objectName: "clearInputButton"

                flat: true
                icon.name: "ic_fluent_clear_formatting_20_regular"
                icon.color: enabled
                    ? Theme.currentTheme.colors.textColor
                    : Theme.currentTheme.colors.textDisabledColor
                Layout.alignment: Qt.AlignVCenter
                Accessible.name: qsTr("Clear input")

                Tip { text: qsTr("Clear input") }
                onClicked: clearInput()
            }


        }

        // ---- Workspace: input / result and plot ----
        SplitView {
            id: workspace

            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Horizontal

            handle: Rectangle {
                implicitWidth: page.paneHandleWidth
                implicitHeight: page.paneHandleWidth
                color: inputSplitHover.hovered
                    ? page.splitterHoverFill : "transparent"
                visible: inputPane.visible

                Behavior on color {
                    ColorAnimation {
                        duration: 120
                        easing.type: Easing.OutCubic
                    }
                }

                HoverHandler { id: inputSplitHover }

                //: WinUI3's ContentSizer: a 20px neutral hover band and a fixed
                //: 8x36 pill. The pill's size and opaque neutral colour do not
                //: change on hover; only the band appears.
                Rectangle {
                    anchors.centerIn: parent
                    width: page.splitterPillThickness
                    height: page.splitterPillLength
                    radius: page.splitterPillThickness / 2
                    color: page.splitterPillColor
                }
            }

            // The input is a resizable pane, not a details sidebar. Zen hides it
            // entirely; the SplitView then gives the result/plot area the width.
            Item {
                id: inputPane
                objectName: "inputPane"

                SplitView.preferredWidth: page.inputPanelWidth
                SplitView.minimumWidth: 280
                visible: !vm.zenMode
                clip: true

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 10

                    // Input area: Code / Assign. Both live side by side in a
                    // clipped stage and slide in opposite directions when the
                    // mode changes; the off-screen one is disabled, so the
                    // hidden input never takes focus or keystrokes.
                    Item {
                        id: inputStage

                        objectName: "inputStage"
                        clip: true
                        //: The first binding of `x` must not animate: a page
                        //: rebuilt while the VM is in Assign mode would
                        //: otherwise slide both rows in from the left.
                        property bool slideReady: false
                        //: Both editors must be visible while the mode slide
                        //: runs. Once it ends, the hidden one disappears so a
                        //: sidebar width animation cannot expose it: its `x`
                        //: offset shrinks with the stage otherwise.
                        property bool modeSwitching: false

                        function beginModeTransition() {
                            modeSwitching = true
                            modeSwitchTimer.restart()
                        }

                        Component.onCompleted: slideReady = true

                        Timer {
                            id: modeSwitchTimer
                            interval: 180
                            onTriggered: inputStage.modeSwitching = false
                        }

                        Layout.fillWidth: true
                        // The Code box keeps its 110px footprint; Assign grows
                        // only as far as its wrapping value needs. The spacer
                        // after the keyboard takes the sidebar's spare height,
                        // so the keys stay above it instead of floating.
                        Layout.minimumHeight: 110
                        Layout.preferredHeight: calcVM.inputMode === 0
                                ? 110
                                : Math.min(240, Math.max(110, assignRow.implicitHeight + 8))

                        ScrollableTextArea {
                            id: codeArea

                            objectName: "codeInput"
                            // The stage's two panes are siblings of its width;
                            // the inactive one sits fully outside the clip.
                            width: parent.width
                            height: parent.height
                            x: calcVM.inputMode === 0 ? 0 : -width
                            enabled: calcVM.inputMode === 0
                            visible: calcVM.inputMode === 0
                                || inputStage.modeSwitching
                            //: Code leaves to the left, Assign arrives from the
                            //: right; going back reverses both. Eased, not a
                            //: paginated SwipeView: the two panes cross the
                            //: stage together.
                            Behavior on x {
                                enabled: inputStage.slideReady
                                NumberAnimation {
                                    duration: 180
                                    easing.type: Easing.OutCubic
                                }
                            }
                            text: calcVM.inputText
                            placeholderText: qsTr("Enter expression...")
                            wrapMode: TextEdit.Wrap
                            onTextChanged: calcVM.inputText = text
                            // The box takes the code theme's own surface, and the
                            // inner area's background has to go or it would cover
                            // it. Text the palette leaves unpainted (a free
                            // symbol) then reads in the theme's ink rather than
                            // the UI's, which is what keeps it legible there.
                            background: CodeSurface {
                                focused: codeArea.textArea.activeFocus
                            }
                            textArea.background: null
                            textArea.color: page.codeSurface.ink
                                || Theme.currentTheme.colors.textColor
                            // The theme's own placeholder colour, which the family
                            // states or VSCode derives from its foreground. "" keeps
                            // RinUI's, for a family with no surface of its own.
                            textArea.placeholderTextColor: page.codeSurface.placeholder
                                || Theme.currentTheme.colors.textSecondaryColor
                            // The inner area is the text item: it draws the
                            // glyphs, so the code font has to reach it, and it
                            // holds the keystrokes, so the '=' shortcut does too.
                            textArea.font: settingsVM.codeFont
                            textArea.Keys.onPressed: (event) => {
                                if (event.key === Qt.Key_Equal
                                        && !event.modifiers
                                        && calcVM.inputText.trim().length === 0) {
                                    switchToAssign()
                                    event.accepted = true
                                }
                            }
                        }

                        //: The app's context menu for the Code box (see
                        //: `CodeContextMenu`): a sibling of the box rather than a
                        //: child, because the box is RinUI's `ScrollableTextArea`
                        //: and this has to sit *over* it — ahead of the menu its
                        //: own inner `TextArea` opens from a vendored `MouseArea`.
                        //: It covers what the box covers, and shows when the box
                        //: does.
                        CodeContextMenu {
                            editor: codeArea.textArea
                            anchors.fill: codeArea
                            visible: calcVM.inputMode === 0
                        }

                        ColumnLayout {
                            id: assignRow

                            objectName: "assignInput"
                            width: parent.width
                            height: parent.height
                            x: calcVM.inputMode === 1 ? 0 : width
                            enabled: calcVM.inputMode === 1
                            visible: calcVM.inputMode === 1
                                || inputStage.modeSwitching
                            Behavior on x {
                                enabled: inputStage.slideReady
                                NumberAnimation {
                                    duration: 180
                                    easing.type: Easing.OutCubic
                                }
                            }
                            spacing: 8

                            //: Name and operator on the first line; the value gets
                            //: the full width and the remaining height on the
                            //: second. A single row made the value field the
                            //: narrow leftover between two fixed controls.
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                // The shared code field (surface, ink, code font),
                                // the same one the Variables page renames with.
                                CodeField {
                                    id: assignNameField

                                    Layout.preferredWidth: 130
                                    Layout.alignment: Qt.AlignVCenter
                                    text: calcVM.assignName
                                    placeholderText: qsTr("name")
                                    onTextChanged: calcVM.assignName = text

                                    // Smart navigation: an operator typed at the end
                                    // of the name sets the combo and jumps to the
                                    // value; backspace at position 0 returns to Code
                                    // mode.
                                    Keys.onPressed: (event) => {
                                        const opMap = { "=": 0, "+": 1, "-": 2,
                                                        "*": 3, "/": 4, "%": 5 }
                                        const opIndex = opMap[event.text]
                                        const mods = event.modifiers & ~Qt.ShiftModifier
                                        if (opIndex !== undefined && mods === 0
                                                && cursorPosition === length) {
                                            calcVM.assignOperator = operatorCombo.model[opIndex]
                                            assignValueField.forceActiveFocus()
                                            event.accepted = true
                                        } else if (event.key === Qt.Key_Backspace
                                                   && cursorPosition === 0
                                                   && selectedText === "") {
                                            switchToCode()
                                            event.accepted = true
                                        }
                                    }
                                }

                                ComboBox {
                                    id: operatorCombo

                                    Layout.preferredWidth: 96
                                    Layout.alignment: Qt.AlignVCenter
                                    model: ["=", "+=", "-=", "*=", "/=", "%="]
                                    currentIndex: {
                                        const i = model.indexOf(calcVM.assignOperator)
                                        return i >= 0 ? i : 0
                                    }
                                    onActivated: (index) => calcVM.assignOperator = model[index]
                                }

                                Item { Layout.fillWidth: true }
                            }

                            // The shared highlighted code area — full width on the
                            // second line; it fills the Assign stage's spare height.
                            CodeArea {
                                id: assignValueField

                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                Layout.minimumHeight: 44
                                Layout.fillHeight: true
                                text: calcVM.assignValue
                                placeholderText: qsTr("expression")
                                wrapMode: TextEdit.Wrap
                                onTextChanged: calcVM.assignValue = text

                                Keys.onPressed: (event) => {
                                    // Enter calculates, never inserts a newline.
                                    if (event.key === Qt.Key_Return
                                            || event.key === Qt.Key_Enter) {
                                        runCalculation()
                                        event.accepted = true
                                    } else if (event.key === Qt.Key_Backspace
                                               && cursorPosition === 0
                                               && length === 0) {
                                        // Backspace in an empty value -> focus the name
                                        assignNameField.forceActiveFocus()
                                        event.accepted = true
                                    }
                                }
                            }
                        }

                    }
                    KeyboardPanel {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 282
                        Layout.minimumHeight: 242
                        onKeyPressed: (key) => page.insertToInput(key)
                        onBackspacePressed: page.backspaceInput()
                        onCursorLeftPressed: page.moveInputCursor(-1)
                        onCursorRightPressed: page.moveInputCursor(1)
                        onUndoPressed: page.undoInput()
                        onRedoPressed: page.redoInput()
                    }

                    //: The mock-up's spacer: the input and the keyboard keep
                    //: their sizes, and the empty rest of the sidebar belongs
                    //: below the keys rather than inside the editor.
                    Item { Layout.fillHeight: true }
                }
            }

            // Right area: result and plot. The result/plot divider is one
            // ratio, not two layout states: dragging it writes `resultShare`,
            // and the horizontal and vertical bindings both read it back.
            Item {
                id: resultArea

                SplitView.fillWidth: true
                SplitView.minimumWidth: page.resultPaneMinWidth
                clip: true

                Item {
                    id: splitArea
                    objectName: "splitArea"

                    anchors.fill: parent

                    readonly property real horizontalLength:
                        Math.max(0, width - page.paneHandleWidth)
                    readonly property real verticalLength:
                        Math.max(0, height - page.paneHandleWidth)
                    //: While the 16ms decision timer runs, keep the *old*
                    //: orientation visible. Otherwise the bindings would already
                    //: show the new layout, then jump back to animate from it.
                    property bool layoutPending: false
                    readonly property bool targetHorizontal:
                        layoutPending ? page.layoutFromHorizontal
                                      : page.plotBesideResult
                    readonly property real splitLength:
                        targetHorizontal ? horizontalLength : verticalLength
                    readonly property real minShare: splitLength <= 0 ? 0
                        : targetHorizontal
                            ? page.resultPaneMinWidth / splitLength
                            : page.resultPaneMinHeight / splitLength
                    readonly property real maxShare: splitLength <= 0 ? 1
                        : targetHorizontal
                            ? 1 - page.plotPaneMinWidth / splitLength
                            : 1 - page.plotPaneMinHeight / splitLength
                    readonly property real effectiveShare:
                        Math.max(minShare, Math.min(maxShare, page.resultShare))
                    //: During a flip, interpolate the raw share so the pending
                    //: old layout and the p=0 frame match. Minimums clamp only
                    //: the settled, interactive layout (and the drag itself).
                    readonly property real geometryShare:
                        (layoutPending || layoutProgress < 1)
                            ? page.resultShare : effectiveShare

                    //: 0 at the old orientation, 1 at the new one. The panes'
                    //: geometry is interpolated from normalized dimensions of
                    //: the *current* split area, not from stale pixel sizes, so
                    //: a window resize cannot push the plot height negative.
                    property real layoutProgress: 1

                    function beginLayoutTransition() {
                        layoutAnimation.stop()
                        layoutProgress = 1
                        layoutPending = true
                        layoutDecisionTimer.restart()
                    }

                    function applyLayoutTransition() {
                        //: Let the window resize settle before touching the
                        //: plot. qmlmathplot hangs if its canvas is resized in
                        //: the same event cycle as a small window resize.
                        if (Window.height < 620) {
                            layoutProgress = 1
                            layoutPending = false
                            return
                        }
                        layoutProgress = 0
                        layoutPending = false
                        layoutAnimation.restart()
                    }

                    Timer {
                        id: layoutDecisionTimer
                        interval: 16
                        onTriggered: splitArea.applyLayoutTransition()
                    }

                    NumberAnimation {
                        id: layoutAnimation
                        target: splitArea
                        property: "layoutProgress"
                        from: 0
                        to: 1
                        duration: Utils.animationSpeed
                        easing.type: Easing.OutCubic
                    }

                    readonly property real resultWidth: {
                        if (!calcVM.hasPlot)
                            return width
                        if (layoutPending)
                            return targetHorizontal
                                ? horizontalLength * geometryShare : width
                        const end = targetHorizontal
                            ? horizontalLength * geometryShare : width
                        const start = page.layoutFromHorizontal
                            ? horizontalLength * geometryShare : width
                        return start + (end - start) * layoutProgress
                    }
                    readonly property real resultHeight: {
                        if (!calcVM.hasPlot)
                            return height
                        if (layoutPending)
                            return targetHorizontal
                                ? height : verticalLength * geometryShare
                        const end = targetHorizontal
                            ? height : verticalLength * geometryShare
                        const start = page.layoutFromHorizontal
                            ? height : verticalLength * geometryShare
                        return start + (end - start) * layoutProgress
                    }

                    Item {
                        id: resultPane
                        objectName: "resultPane"

                        x: 0
                        y: 0
                        width: splitArea.resultWidth
                        height: splitArea.resultHeight

                        //: The empty state's monogram: the app's Σ tinted
                        //: into the theme's neutral, or one item of a
                        //: user-configured pool rendered in the result's own
                        //: style. It is a sibling of (and behind) the scroller,
                        //: so it cannot steal a click, and it lives only where
                        //: there is nothing to read.
                        Item {
                            id: watermark
                            objectName: "resultWatermark"

                            //: The same emptiness the outcome line uses: a value or
                            //: a failure means there is something to read, and the
                            //: mark steps aside. (`resultText` is the plain outcome;
                            //: a failure leaves it empty and sets `isError`.)
                            readonly property bool empty:
                                calcVM.resultText === "" && !calcVM.isError
                            readonly property bool random:
                                settingsVM.resultWatermark === "random"
                            //: The random render arrives at the watermark's own
                            //: fixed size; it is never blown up to the pane.
                            //: Only a pool item bigger than the pane shrinks,
                            //: and it keeps its aspect while doing so.
                            readonly property real randomScale:
                                !random
                                    || calcVM.watermarkWidth <= 0
                                    || calcVM.watermarkHeight <= 0
                                ? 1
                                : Math.min(1,
                                           width / calcVM.watermarkWidth,
                                           height / calcVM.watermarkHeight)

                            anchors.fill: parent
                            anchors.topMargin: resultHeaderRow.height + 12
                            anchors.leftMargin: 24
                            anchors.rightMargin: 24
                            anchors.bottomMargin: 32
                            visible: empty
                            //: Both kinds are drawn in the same ink (the theme's
                            //: text colour), so one fade here weights them alike.
                            opacity: empty ? 0.2 : 0

                            Behavior on opacity {
                                NumberAnimation { duration: 150; easing.type: Easing.OutQuad }
                            }

                            Image {
                                id: art

                                //: Both kinds are the viewmodel's artwork: the
                                //: monogram tinted to the formula ink, or the
                                //: rolled pool item rendered at a fixed size.
                                anchors.centerIn: parent
                                width: parent.random
                                    ? Math.round(calcVM.watermarkWidth
                                                 * watermark.randomScale)
                                    : Math.min(Math.round(parent.width),
                                               Math.round(parent.height * 0.6),
                                               140)
                                height: parent.random
                                    ? Math.round(calcVM.watermarkHeight
                                                 * watermark.randomScale)
                                    : width
                                fillMode: Image.PreserveAspectFit
                                smooth: true
                                sourceSize: Qt.size(
                                    Math.round(width * Screen.devicePixelRatio),
                                    Math.round(height * Screen.devicePixelRatio))
                                source: calcVM.watermarkSvgUrl
                            }
                        }

                        ColumnLayout {
                            anchors.fill: parent
                            spacing: 8

                            //: The backend state belongs to the result it
                            //: governs, so it sits above the result rather than
                            //: in the page toolbar. The toolbar is the actions;
                            //: this is the surface's own state.
                            RowLayout {
                                id: resultHeaderRow
                                Layout.fillWidth: true
                                Layout.rightMargin: 8
                                spacing: 6

                                ProgressRing {
                                    visible: calcVM.backendBusy
                                    size: 14
                                    strokeWidth: 2
                                    indeterminate: true
                                }

                                Text {
                                    text: page.backendStatusText
                                    typography: Typography.Caption
                                    color: page.backendStatusColor
                                }

                                Item { Layout.fillWidth: true }

                                ToolButton {
                                    objectName: "resultCopyButton"
                                    flat: true
                                    icon.name: "ic_fluent_copy_20_regular"
                                    icon.color: enabled
                                        ? Theme.currentTheme.colors.textColor
                                        : Theme.currentTheme.colors.textDisabledColor
                                    enabled: calcVM.resultText !== ""
                                    Accessible.name: qsTr("Copy result")
                                    Tip { text: qsTr("Copy result") }
                                    onClicked: vm.copyText(calcVM.resultText)
                                }
                                ToolButton {
                                    objectName: "resultCopyLatexButton"
                                    flat: true
                                    icon.name: "ic_fluent_clipboard_math_formula_20_regular"
                                    icon.color: enabled
                                        ? Theme.currentTheme.colors.textColor
                                        : Theme.currentTheme.colors.textDisabledColor
                                    enabled: calcVM.resultLatex !== ""
                                    Accessible.name: qsTr("Copy LaTeX")
                                    Tip { text: qsTr("Copy LaTeX") }
                                    onClicked: vm.copyText(calcVM.resultLatex)
                                }
                            }

                            //: The result scroller now contains only what there
                            //: is to read: the outcome, the formula and the
                            //: alternative forms. The plot is a sibling pane, so
                            //: scrolling a long answer cannot drag it away and
                            //: the wheel over the plot is the plot's.
                            Flickable {
                                id: resultScroll

                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                clip: true
                                contentHeight: resultColumn.implicitHeight

                                ScrollBar.vertical: ScrollBar { }

                                ColumnLayout {
                                    id: resultColumn

                                    width: resultScroll.width
                                    spacing: 12
                            //: What there is to *read*, and the only place that says
                            //: it: the value as markup in the code colours, a failure's
                            //: prose, or the placeholder while nothing has been calculated.
                            //: The formula below is the LaTeX's alone. Selectable — a result is
                            //: something to copy out — but never editable, and borderless: a
                            //: bare `TextEdit` draws no background. It wraps instead of eliding
                            //: (rich text ignores `elide`), which is why the viewmodel's
                            //: unelided `highlighted` is the right call here.
                            //:
                            //: Living inside the scroll area rather than beside the copy
                            //: buttons is what makes a long outcome scroll with the formula
                            //: instead of pushing it out of the window.
                            //: The same component the history cards use (see
                            //: `CopyableLabel`): read-only, borderless, selectable,
                            //: no right-click menu. The calculator's outcome and a
                            //: history result line are the same kind of text.
                            CopyableLabel {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                //: Height follows the text: the fixed 4.2-line box
                                //: left a band of empty space between the outcome
                                //: and its formula, which read as the LaTeX block's
                                //: own top margin. The column is inside the scroll
                                //: area, so a long result grows it and scrolls.
                                wrap: true
                                textFormat: isProse ? TextEdit.PlainText
                                    : TextEdit.RichText
                                readonly property bool isProse: calcVM.isError
                                readonly property bool hasResult: calcVM.resultText !== ""
                                color: isProse
                                    ? Theme.currentTheme.colors.systemCriticalColor
                                    : (hasResult
                                        ? Theme.currentTheme.colors.textColor
                                        : Theme.currentTheme.colors.textSecondaryColor)
                                text: isProse
                                    ? calcVM.errorMessage
                                    : (hasResult
                                        ? (vm ? vm.highlighted(calcVM.resultText, Theme.isDark()) : "")
                                        : qsTr("Press Ctrl+Return to calculate"))
                            }

                            // LaTeX result area: the natural-height rendering,
                            // horizontally scrollable when it is wider than the
                            // panel (see `MathStrip` for the geometry, including
                            // the room its overlay bar needs). The strip is only
                            // as tall as the artwork, so with nothing to render
                            // it takes no space at all — the outcome it would
                            // have reported is on the result line above instead.
                            MathStrip {
                                Layout.fillWidth: true
                                //: The outcome line above is the gap; no second one.
                                paddingTop: 0

                                naturalWidth: calcVM.latexWidth
                                naturalHeight: calcVM.latexHeight
                                source: calcVM.latexSvgUrl
                            }

                            //: The alternative forms of the answer (N, expanded,
                            //: factored, …), in the History card's own row
                            //: anatomy. Empty and invisible when there is no
                            //: different form worth showing.
                            VariantsCard {
                                Layout.fillWidth: true
                                variants: calcVM.variants
                            }

                        } // resultColumn
                    } // Flickable
                } // result ColumnLayout
            } // resultPane

            //: The divider writes the one result share both orientations read.
            //: It is a plain MouseArea rather than a SplitView handle so the
            //: ratio survives an orientation change by construction.
            Rectangle {
                id: plotHandle

                visible: calcVM.hasPlot
                color: plotSplitHover.containsMouse
                    ? page.splitterHoverFill : "transparent"
                x: splitArea.targetHorizontal ? resultPane.width : 0
                y: splitArea.targetHorizontal ? 0 : resultPane.height
                width: splitArea.targetHorizontal
                    ? page.paneHandleWidth : splitArea.width
                height: splitArea.targetHorizontal
                    ? splitArea.height : page.paneHandleWidth

                Behavior on color {
                    ColorAnimation {
                        duration: 120
                        easing.type: Easing.OutCubic
                    }
                }

                MouseArea {
                    id: plotSplitHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: splitArea.targetHorizontal
                        ? Qt.SplitHCursor : Qt.SplitVCursor

                    onPositionChanged: (mouse) => {
                        if (!pressed || splitArea.splitLength <= 0)
                            return
                        const point = mapToItem(splitArea, mouse.x, mouse.y)
                        if (splitArea.targetHorizontal) {
                            page.resultShare = Math.max(0, Math.min(1,
                                (point.x - page.paneHandleWidth / 2)
                                    / splitArea.splitLength))
                        } else {
                            page.resultShare = Math.max(0, Math.min(1,
                                (point.y - page.paneHandleWidth / 2)
                                    / splitArea.splitLength))
                        }
                    }
                }

                //: The same opaque ContentSizer pill, rotated with the
                //: result/plot layout. It is hidden during the flip so it cannot
                //: float across the content.
                Rectangle {
                    anchors.centerIn: parent
                    visible: !splitArea.layoutPending
                        && splitArea.layoutProgress >= 1
                    width: splitArea.targetHorizontal
                        ? page.splitterPillThickness : page.splitterPillLength
                    height: splitArea.targetHorizontal
                        ? page.splitterPillLength : page.splitterPillThickness
                    radius: page.splitterPillThickness / 2
                    color: page.splitterPillColor
                }
            }

            // The plot is a sibling of the result pane, never a child of its
            // scroller. That is what keeps a long formula from dragging the
            // plot away and lets the wheel over the plot stay with the plot.
            // The plot itself lives in the viewmodel (RinUI rebuilds a page on
            // every navigation), so this is a view of it and owns no state.
            Item {
                id: plotPane
                objectName: "plotPane"

                x: splitArea.targetHorizontal
                    ? resultPane.width + page.paneHandleWidth : 0
                y: splitArea.targetHorizontal
                    ? 0 : resultPane.height + page.paneHandleWidth
                width: splitArea.targetHorizontal
                    ? Math.max(0, splitArea.width - resultPane.width
                        - page.paneHandleWidth)
                    : splitArea.width
                height: splitArea.targetHorizontal
                    ? splitArea.height
                    : Math.max(0, splitArea.height - resultPane.height
                        - page.paneHandleWidth)
                visible: calcVM.hasPlot

                //: Plot actions live in the pane header, outside the drawing
                //: surface. Overlaying them on the canvas hid the plot's own
                //: furniture (axis labels, cursor read-outs) and made the
                //: toolbar collide with the graph instead of framing it.
                RowLayout {
                    id: plotToolbar
                    objectName: "plotToolbar"

                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.margins: 3
                    height: 32
                    spacing: 4

                    Text {
                        text: qsTr("Plot")
                        typography: Typography.Caption
                        color: Theme.currentTheme.colors.textSecondaryColor
                        Layout.leftMargin: 4
                    }

                    Item { Layout.fillWidth: true }

                    ToolButton {
                        objectName: "plotResetButton"
                        flat: true
                        icon.name: "ic_fluent_arrow_reset_20_regular"
                        icon.color: enabled
                            ? Theme.currentTheme.colors.textColor
                            : Theme.currentTheme.colors.textDisabledColor
                        enabled: calcVM.hasPlot
                        Accessible.name: qsTr("Reset plot view")
                        Tip { text: qsTr("Reset plot view") }
                        onClicked: plotView.camera.reset()
                    }
                    ToolButton {
                        objectName: "plotZoomOutButton"
                        flat: true
                        icon.name: "ic_fluent_zoom_out_20_regular"
                        icon.color: enabled
                            ? Theme.currentTheme.colors.textColor
                            : Theme.currentTheme.colors.textDisabledColor
                        enabled: calcVM.hasPlot && plotView.camera.zoomEnabled
                        Accessible.name: qsTr("Zoom out")
                        Tip { text: qsTr("Zoom out") }
                        onClicked: plotView.camera.animate_zoom(
                            -120, 0.5, 0.5, plotView.width, plotView.height, 160)
                    }
                    ToolButton {
                        objectName: "plotZoomInButton"
                        flat: true
                        icon.name: "ic_fluent_zoom_in_20_regular"
                        icon.color: enabled
                            ? Theme.currentTheme.colors.textColor
                            : Theme.currentTheme.colors.textDisabledColor
                        enabled: calcVM.hasPlot && plotView.camera.zoomEnabled
                        Accessible.name: qsTr("Zoom in")
                        Tip { text: qsTr("Zoom in") }
                        onClicked: plotView.camera.animate_zoom(
                            120, 0.5, 0.5, plotView.width, plotView.height, 160)
                    }
                }

                //: The focus ring draws two pixels outside its control, so
                //: three pixels of gutter keep it whole in the split pane.
                Control {
                    id: plotFrame
                    objectName: "plotFrame"

                    visible: calcVM.hasPlot
                    anchors.top: plotToolbar.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 3
                    anchors.topMargin: 0

                    //: The same focus arrangement the Segmented items use:
                    //: a Control is the Tab stop, so the shared ring can read
                    //: `visualFocus`/`focusReason` and appears for Tab/Backtab
                    //: only. A click lands on the plot itself (PlotInput focuses
                    //: it), which leaves this control unfocused and the ring
                    //: hidden — exactly what a click does to a button. Keys are
                    //: forwarded so both routes drive it.
                    focus: true
                    activeFocusOnTab: true
                    //: Qt Quick Controls took the tab chain over from
                    //: `activeFocusOnTab` (6.5): a Control's own `focusPolicy`
                    //: decides, and NoFocus is its default.
                    focusPolicy: Qt.StrongFocus
                    Keys.forwardTo: [plotView]

                    onActiveFocusChanged: {
                        if (activeFocus)
                            return
                        //: The plot never loses focus itself (the keys are
                        //: forwarded), so a held arrow key would keep panning.
                        //: qmlmathplot drops held keys when the camera stops
                        //: accepting them; these two toggles are that, through
                        //: public API.
                        const camera = plotView.camera
                        const pan = camera.panEnabled
                        const zoom = camera.zoomEnabled
                        camera.panEnabled = false
                        camera.panEnabled = pan
                        camera.zoomEnabled = false
                        camera.zoomEnabled = zoom
                    }

                    Rectangle {
                        anchors.fill: parent
                        //: The graph is the surface, not a card inside a card.
                        color: "transparent"
                        radius: 0
                        border.width: 0

                        //: Qt's `clip` is rectangular, so `clip: true` would let
                        //: the plot's square canvas paint over this card's rounded
                        //: corners. The contents are rendered into a layer and
                        //: masked with a rounded rectangle instead.
                        Item {
                            anchors.fill: parent
                            layer.enabled: true
                            layer.effect: OpacityMask {
                                maskSource: plotMask
                            }

                            //: The plot handles the mouse and the forwarded keys;
                            //: the control above owns the Tab stop.
                            PlotView {
                                id: plotView
                                objectName: "plotView"
                                anchors.fill: parent
                                plot: calcVM.plot
                                //: Not the Tab stop: the control above is, so
                                //: the ring has one owner. A click still focuses
                                //: the plot (PlotInput forces it), which is the
                                //: mouse path the ring ignores.
                                focus: false
                                activeFocusOnTab: false
                            }
                        }

                        //: A shader bake can refuse an expression (an unsupported
                        //: function, a level set too hard for the per-pixel
                        //: model). The plot must say so where the plot is, not
                        //: only in the log.
                        Text {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.margins: 10
                            visible: calcVM.plotError !== ""
                            text: calcVM.plotError
                            elide: Text.ElideRight
                            color: Theme.currentTheme.colors.systemCriticalColor
                            typography: Typography.Caption
                        }
                    }

                    //: The mask is outside the masked item (an effect may not
                    //: include itself) and never shown: the effect renders it
                    //: offscreen and reads its alpha.
                    Rectangle {
                        id: plotMask
                        objectName: "plotMask"
                        anchors.fill: parent
                        radius: Theme.currentTheme.appearance.buttonRadius
                        visible: false
                    }

                    //: The ring every other control raises, with the same rule:
                    //: `visualFocus` and a Tab/Backtab focus reason (see
                    //: `FocusIndicator`).
                    ProjectFocusIndicator {
                        objectName: "plotFocusIndicator"
                        control: plotFrame
                    }
                }

                        }
                    }
                }
            }
        }

    Connections {
        target: vm

        function onZenModeChanged() {
            Qt.callLater(function() {
                if (vm.zenMode)
                    resultScroll.forceActiveFocus()
                else
                    page.fallbackTarget().forceActiveFocus()
            })
        }
    }

    Shortcut {
        sequences: ["Ctrl+Return"]
        onActivated: runCalculation()
    }

    //: The calculator's own refusals — a SymPy built-in name, which is stored but
    //: worth saying out loud. The dialog and its wiring are the shared pair.
    WarningDialog {
        source: calcVM
    }
}
