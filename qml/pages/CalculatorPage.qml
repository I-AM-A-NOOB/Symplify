import QtQuick
import QtQuick.Controls
import QtQuick.Controls.FluentWinUI3
import QtQuick.Controls.FluentWinUI3.impl as FluentImpl
import QtQuick.Layouts
import QtQuick.Window
import "../components"

Page {
    id: root

    property string currentMode: "code" // "code" | "assign"

    property bool hasLatexSvg: calcVM && calcVM.latexSvgUrl.length > 0

    // Focus the code input when the app starts.
    Component.onCompleted: codeInput.forceActiveFocus()

    function switchToCode() {
        root.currentMode = "code"
        codeModeButton.checked = true
        codeInput.forceActiveFocus()
    }

    function switchToAssign() {
        root.currentMode = "assign"
        assignModeButton.checked = true
        assignName.forceActiveFocus()
    }

    function setExample(expr) {
        root.switchToCode()
        codeInput.text = expr
    }

    // Find the editable text field that currently holds active focus.
    // Window.activeFocusItem is unreliable here, so walk the item tree using
    // the per-item `activeFocus` flag instead.
    function findFocusedEditable(item) {
        if (!item)
            return null
        if (item.activeFocus && typeof item.insert === "function"
                && typeof item.cursorPosition === "number"
                && item.readOnly !== true)
            return item
        var children = item.children
        for (var i = 0; i < children.length; i++) {
            var found = root.findFocusedEditable(children[i])
            if (found)
                return found
        }
        return null
    }

    // The editable text field that currently holds active focus, or null.
    function focusedEditable() {
        var target = root.Window.activeFocusItem
        if (!target || typeof target.insert !== "function" || target.readOnly === true)
            return root.findFocusedEditable(root.Window.contentItem)
        return target
    }

    // Insert keyboard input into the focused editable field (keys never grab
    // focus). Falls back to the active mode's input when none is focused.
    function insertToInput(text) {
        var target = root.focusedEditable()
        if (target) {
            target.insert(target.cursorPosition, text)
            return
        }
        if (root.currentMode === "assign")
            assignValue.insert(assignValue.cursorPosition, text)
        else
            codeInput.insert(codeInput.cursorPosition, text)
    }

    // The Clear / Undo / Redo buttons act on the focused editable field too.
    function clearInput() {
        var target = root.focusedEditable()
        if (target && typeof target.clear === "function") {
            target.clear()
            return
        }
        if (root.currentMode === "assign")
            assignValue.clear()
        else
            codeInput.clear()
    }

    function undoInput() {
        var target = root.focusedEditable()
        if (target && typeof target.undo === "function") {
            target.undo()
            return
        }
        if (root.currentMode === "assign")
            assignValue.undo()
        else
            codeInput.undo()
    }

    function redoInput() {
        var target = root.focusedEditable()
        if (target && typeof target.redo === "function") {
            target.redo()
            return
        }
        if (root.currentMode === "assign")
            assignValue.redo()
        else
            codeInput.redo()
    }

    function runCalculation() {
        if (root.currentMode === "code") {
            var expr = codeInput.text.trim()
            if (expr) {
                calcVM.calculate(expr)
                codeInput.selectAll()
                codeInput.forceActiveFocus()
            }
        } else {
            var name = assignName.text.trim()
            var value = assignValue.text.trim()
            if (name && value) {
                calcVM.calculateAssign(name, operatorCombo.currentText, value)
                assignValue.forceActiveFocus()
            }
        }
    }

    Shortcut {
        sequence: "Ctrl+Return"
        onActivated: root.runCalculation()
    }

    Connections {
        target: calcVM
        function onWarningOccurred(title, content) {
            warningDialog.title = title
            warningContent.text = content
            warningDialog.open()
        }
    }

    Dialog {
        id: warningDialog
        modal: true
        standardButtons: Dialog.Ok
        contentItem: Label {
            id: warningContent
            width: 300
            wrapMode: Text.Wrap
        }
    }

    // Measures the value field's text so it can overflow horizontally.
    TextMetrics {
        id: textMetrics
        font: assignValue.font
        text: assignValue.text
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 8

        // ---- Command bar ----
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Button {
                id: calcButton
                text: qsTr("Calculate")
                highlighted: true
                onClicked: root.runCalculation()
            }

            ToolSeparator {}

            ToolButton {
                text: "\uF1B1" // FluentSystemIcons: backspace_20
                font.family: "FluentSystemIcons-Regular"
                font.pixelSize: 16
                ToolTip.visible: hovered
                ToolTip.text: qsTr("Clear input")
                onClicked: root.clearInput()
            }

            ToolButton {
                text: "\uF199" // FluentSystemIcons: arrow_undo_20
                font.family: "FluentSystemIcons-Regular"
                font.pixelSize: 16
                ToolTip.visible: hovered
                ToolTip.text: qsTr("Undo")
                onClicked: root.undoInput()
            }

            ToolButton {
                text: "\uF16E" // FluentSystemIcons: arrow_redo_20
                font.family: "FluentSystemIcons-Regular"
                font.pixelSize: 16
                ToolTip.visible: hovered
                ToolTip.text: qsTr("Redo")
                onClicked: root.redoInput()
            }

            ToolSeparator {}

            Button {
                text: qsTr("Examples")
                onClicked: examplesMenu.popup()
                Menu {
                    id: examplesMenu
                    MenuItem { text: qsTr("Derivative: diff(x**2, x)"); onTriggered: root.setExample("diff(x**2, x)") }
                    MenuItem { text: qsTr("Integral: integrate(x**2, x)"); onTriggered: root.setExample("integrate(x**2, x)") }
                    MenuItem { text: qsTr("Limit: limit(sin(x)/x, x, 0)"); onTriggered: root.setExample("limit(sin(x)/x, x, 0)") }
                    MenuItem { text: qsTr("Solve: solve(x**2 - 4, x)"); onTriggered: root.setExample("solve(x**2 - 4, x)") }
                    MenuItem { text: qsTr("Matrix: Matrix([[1, 2], [3, 4]])"); onTriggered: root.setExample("Matrix([[1, 2], [3, 4]])") }
                }
            }

            Item { Layout.fillWidth: true }
        }

        // ---- Split content: left input panel / right result panel ----
        SplitView {
            id: splitView
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Horizontal

            // Invisible splitter handle (still draggable, respects min widths).
            handle: Rectangle {
                implicitWidth: 6
                implicitHeight: 6
                color: "transparent"
            }

            // Left panel: mode selector, input, keyboard
            Frame {
                // Grows proportionally (a bit) on resize; never below the minimum.
                SplitView.preferredWidth: Math.max(360, splitView.width * 0.3)
                SplitView.minimumWidth: 360

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8

                    // Mode selector (replaces SegmentedWidget)
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Label { text: qsTr("Mode:") }
                        ButtonGroup {
                            id: modeGroup
                            buttons: [codeModeButton, assignModeButton]
                        }
                        Button {
                            id: codeModeButton
                            text: qsTr("Code")
                            checkable: true
                            checked: true
                            onClicked: root.switchToCode()
                        }
                        Button {
                            id: assignModeButton
                            text: qsTr("Assign")
                            checkable: true
                            onClicked: root.switchToAssign()
                        }
                        Item { Layout.fillWidth: true }
                    }

                    // Input area: Code / Assign slide horizontally when switching.
                    Item {
                        id: inputArea
                        Layout.fillWidth: true
                        Layout.preferredHeight: 110
                        clip: true
                        state: root.currentMode === "code" ? "code" : "assign"

                        // Input: CODE mode (multi-line editor with vertical scrollbar)
                        ScrollView {
                            id: codeScroll
                            width: inputArea.width
                            height: inputArea.height
                            enabled: root.currentMode === "code"
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                            TextArea {
                                id: codeInput
                                width: codeScroll.availableWidth
                                placeholderText: qsTr("Enter expression...")
                                wrapMode: Text.Wrap
                                selectByMouse: true

                                // Smart mode switch: '=' in an empty input -> Assign mode
                                Keys.onPressed: (event) => {
                                    if (event.key === Qt.Key_Equal && !event.modifiers
                                            && codeInput.text.trim().length === 0) {
                                        root.switchToAssign()
                                        event.accepted = true
                                    }
                                }
                            }
                        }

                        // Input: ASSIGN mode (name + operator + value)
                        RowLayout {
                            id: assignRow
                            width: inputArea.width
                            height: inputArea.height
                            spacing: 6
                            enabled: root.currentMode === "assign"

                            TextField {
                                id: assignName
                                Layout.preferredWidth: 140
                                Layout.alignment: Qt.AlignVCenter
                                placeholderText: qsTr("Variable name")

                                // Smart navigation, mirroring the widgets AssignInputWidget:
                                // typing an operator at the end sets the combo and
                                // jumps focus to the value field.
                                Keys.onPressed: (event) => {
                                    var opMap = { "=": "=", "+": "+=", "-": "-=",
                                                  "*": "*=", "/": "/=", "%": "%=" }
                                    var op = opMap[event.text]
                                    var mods = event.modifiers & ~Qt.ShiftModifier
                                    if (op !== undefined && mods === 0
                                            && assignName.cursorPosition === assignName.text.length) {
                                        operatorCombo.currentIndex = operatorCombo.model.indexOf(op)
                                        assignValue.forceActiveFocus()
                                        event.accepted = true
                                        return
                                    }
                                    if (event.key === Qt.Key_Backspace && assignName.cursorPosition === 0) {
                                        root.switchToCode()
                                        event.accepted = true
                                    }
                                }
                            }

                            ComboBox {
                                id: operatorCombo
                                model: ["=", "+=", "-=", "*=", "/=", "%="]
                                Layout.preferredWidth: 90
                                Layout.alignment: Qt.AlignVCenter
                            }

                            // Value field: a Fluent text-field decoration drawn
                            // directly from the theme, with a transparent scrolling
                            // TextArea stacked on top for the text.
                            Item {
                                id: valueField
                                Layout.fillWidth: true
                                Layout.minimumWidth: 80
                                Layout.alignment: Qt.AlignVCenter
                                Layout.preferredHeight: assignName.implicitHeight

                                // Fluent text-field background (theme-drawn, no fake control).
                                FluentImpl.StyleImage {
                                    anchors.fill: parent
                                    imageConfig: assignValue.activeFocus
                                        ? Config.controls.textfield.focused.background
                                        : valueHover.hovered
                                            ? Config.controls.textfield.hovered.background
                                            : Config.controls.textfield.normal.background
                                }

                                // Fluent focused-state accent stroke.
                                Item {
                                    objectName: "valueFocusStroke"
                                    visible: assignValue.activeFocus
                                    width: valueField.width
                                    height: 2
                                    y: valueField.height - height
                                    FluentImpl.FocusStroke {
                                        width: parent.width
                                        height: parent.height
                                        radius: 4
                                        color: palette.accent
                                    }
                                }

                                HoverHandler { id: valueHover }

                                ScrollView {
                                    id: valueScroll
                                    anchors.fill: parent
                                    clip: true
                                    ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AlwaysOff }
                                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AlwaysOff }
                                    contentWidth: Math.max(valueScroll.width, textMetrics.advanceWidth + 24)
                                    contentHeight: valueScroll.height

                                    WheelHandler {
                                        onWheel: (event) => {
                                            var max = Math.max(0, valueScroll.contentWidth - valueScroll.width)
                                            var cur = valueScroll.contentItem.contentX
                                            valueScrollAnim.to = Math.max(0,
                                                Math.min(max, cur - event.angleDelta.y / 120 * 30))
                                            valueScrollAnim.restart()
                                        }
                                    }
                                    NumberAnimation {
                                        id: valueScrollAnim
                                        target: valueScroll.contentItem
                                        property: "contentX"
                                        duration: 120
                                        easing.type: Easing.OutCubic
                                    }

                                    TextArea {
                                        id: assignValue
                                        width: valueScroll.contentWidth
                                        height: valueScroll.height
                                        background: null
                                        placeholderText: qsTr("Enter value...")
                                        wrapMode: Text.NoWrap
                                        selectByMouse: true

                                        Keys.onPressed: (event) => {
                                            // Single line: Enter calculates, never inserts a newline.
                                            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                                                event.accepted = true
                                                root.runCalculation()
                                                return
                                            }
                                            // Backspace at start of an empty value -> focus the name field
                                            if (event.key === Qt.Key_Backspace
                                                    && assignValue.cursorPosition === 0
                                                    && assignValue.text.length === 0) {
                                                assignName.forceActiveFocus()
                                                event.accepted = true
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        states: [
                            State {
                                name: "code"
                                PropertyChanges { target: codeScroll; x: 0 }
                                PropertyChanges { target: assignRow; x: inputArea.width }
                            },
                            State {
                                name: "assign"
                                PropertyChanges { target: codeScroll; x: -inputArea.width }
                                PropertyChanges { target: assignRow; x: 0 }
                            }
                        ]
                        transitions: Transition {
                            NumberAnimation {
                                properties: "x"
                                duration: 220
                                easing.type: Easing.OutCubic
                            }
                        }
                    }

                    // Keyboard panel (stable height; the spacer below absorbs the rest)
                    KeyboardPanel {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 240
                        Layout.minimumHeight: 200
                        Layout.topMargin: 4
                        onKeyPressed: (key) => root.insertToInput(key)
                    }

                    // Vertical spacer: keys keep their size regardless of which
                    // input area is in focus or how tall the window is.
                    Item { Layout.fillHeight: true }
                }
            }

            // Right panel: expression, LaTeX area, plot area
            Frame {
                // Absorbs most of the extra space on resize.
                SplitView.fillWidth: true
                SplitView.preferredWidth: 560
                SplitView.minimumWidth: 400

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8

                    // Result label + copy buttons
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Label {
                            Layout.fillWidth: true
                            text: calcVM ? calcVM.resultText : ""
                            wrapMode: Text.Wrap
                            font.pixelSize: 16
                        }
                        Button {
                            text: qsTr("Copy expr")
                            onClicked: {
                                if (root.currentMode === "code")
                                    vm.copyText(codeInput.text)
                            }
                        }
                        Button {
                            text: qsTr("Copy LaTeX")
                            onClicked: vm.copyText(calcVM.resultLatex)
                        }
                    }

                    // LaTeX result area: rendered at the SVG's natural size
                    // (crisp, not upscaled), left-aligned. Its height matches
                    // the LaTeX; a horizontal scrollbar appears when too wide.
                    ScrollView {
                        id: latexScroll
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.hasLatexSvg ? latexImage.height + 6 : 120
                        ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AlwaysOff }
                        contentWidth: Math.max(latexScroll.width, latexImage.width)
                        contentHeight: root.hasLatexSvg ? latexImage.height : 120

                        WheelHandler {
                            onWheel: (event) => {
                                var max = Math.max(0, latexScroll.contentWidth - latexScroll.width)
                                var cur = latexScroll.contentItem.contentX
                                latexScrollAnim.to = Math.max(0,
                                    Math.min(max, cur - event.angleDelta.y / 120 * 30))
                                latexScrollAnim.restart()
                            }
                        }
                        NumberAnimation {
                            id: latexScrollAnim
                            target: latexScroll.contentItem
                            property: "contentX"
                            duration: 120
                            easing.type: Easing.OutCubic
                        }

                        Item {
                            id: latexContent
                            width: Math.max(latexScroll.availableWidth, latexImage.width)
                            height: root.hasLatexSvg ? latexImage.height : 120

                            Image {
                                id: latexImage
                                x: 0
                                y: 0
                                visible: root.hasLatexSvg
                                smooth: true
                                fillMode: Image.PreserveAspectFit

                                // Item stays at the SVG's logical size while the
                                // render resolution (sourceSize) is scaled by the
                                // screen DPI, keeping it crisp on high-DPI displays.
                                width: calcVM ? calcVM.latexWidth : 0
                                height: calcVM ? calcVM.latexHeight : 0
                                sourceSize: Qt.size(
                                    (calcVM ? calcVM.latexWidth : 0) * Screen.devicePixelRatio,
                                    (calcVM ? calcVM.latexHeight : 0) * Screen.devicePixelRatio)
                                source: root.hasLatexSvg ? calcVM.latexSvgUrl : ""
                            }

                            EmptyArea {
                                anchors.fill: parent
                                visible: !root.hasLatexSvg
                                placeholderText: calcVM
                                    ? (calcVM.displayText.length > 0
                                        ? calcVM.displayText
                                        : qsTr("LaTeX result area"))
                                    : qsTr("LaTeX result area")
                            }
                        }
                    }

                    // Plot area (empty placeholder)
                    EmptyArea {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        placeholderText: qsTr("Plot area")
                    }
                }
            }
        }
    }
}
