import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 2.15
import QtQuick.Window 2.15
import RinUI
import "../components"

Item {
    id: page

    readonly property bool hasLatex: calcVM.latexSvgUrl !== ""

    Component.onCompleted: {
        calcVM.set_latex_color(Theme.currentTheme.colors.textColor)
        codeInput.forceActiveFocus()
    }

    // Re-tint the LaTeX when the app theme changes.
    Connections {
        target: Theme

        function onCurrentThemeChanged() {
            calcVM.set_latex_color(Theme.currentTheme.colors.textColor)
        }
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

    function insertToInput(text) {
        const target = findFocusedEditable(page) || fallbackTarget()
        if (target && target.insert)
            target.insert(target.cursorPosition, text)
    }

    function clearInput() {
        const target = findFocusedEditable(page) || fallbackTarget()
        if (target && target.clear)
            target.clear()
    }

    function undoInput() {
        const target = findFocusedEditable(page) || fallbackTarget()
        if (target && target.undo)
            target.undo()
    }

    function redoInput() {
        const target = findFocusedEditable(page) || fallbackTarget()
        if (target && target.redo)
            target.redo()
    }

    function switchToCode() {
        calcVM.inputMode = 0
        codeInput.forceActiveFocus()
    }

    function switchToAssign() {
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
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        anchors.bottomMargin: 16
        spacing: 14

        // ---- Command bar ----
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                typography: Typography.Title
                text: qsTr("Calculator")
            }

            ToolSeparator {}

            Button {
                text: qsTr("Calculate")
                icon.name: "ic_fluent_calculator_20_regular"
                highlighted: true
                onClicked: runCalculation()
            }

            ToolButton {
                icon.name: "ic_fluent_clear_formatting_20_regular"
                icon.color: Theme.currentTheme.colors.textColor
                ToolTip {
                    delay: 500
                    visible: parent.hovered
                    text: qsTr("Clear input")
                }
                onClicked: clearInput()
            }
            ToolButton {
                icon.name: "ic_fluent_arrow_undo_20_regular"
                icon.color: Theme.currentTheme.colors.textColor
                ToolTip {
                    delay: 500
                    visible: parent.hovered
                    text: qsTr("Undo")
                }
                onClicked: undoInput()
            }
            ToolButton {
                icon.name: "ic_fluent_arrow_redo_20_regular"
                icon.color: Theme.currentTheme.colors.textColor
                ToolTip {
                    delay: 500
                    visible: parent.hovered
                    text: qsTr("Redo")
                }
                onClicked: redoInput()
            }

            Item { Layout.fillWidth: true }

            DropDownButton {
                text: qsTr("Examples")

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
        }

        // ---- Split content: left input panel / right result panel ----
        SplitView {
            id: splitView

            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Horizontal

            handle: Rectangle {
                implicitWidth: 6
                implicitHeight: 6
                color: "transparent"
            }

            // Left panel: mode selector, input, keyboard
            Item {
                SplitView.preferredWidth: Math.max(360, splitView.width * 0.38)
                SplitView.minimumWidth: 360

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 12

                    // Input mode switch. calcVM.inputMode is the single
                    // source of truth (it survives page switches); the
                    // Segmented only syncs from it -- a fresh page must
                    // never write its default index back into the VM.
                    Segmented {
                        id: modeSwitch

                        Component.onCompleted: currentIndex = calcVM.inputMode

                        SegmentedItem {
                            text: qsTr("Code")
                            onClicked: calcVM.inputMode = 0
                        }
                        SegmentedItem {
                            text: qsTr("Assign")
                            onClicked: calcVM.inputMode = 1
                        }
                    }

                    Connections {
                        target: calcVM

                        function onInputModeChanged() {
                            modeSwitch.currentIndex = calcVM.inputMode
                            if (calcVM.inputMode === 0)
                                codeInput.forceActiveFocus()
                            else
                                assignNameField.forceActiveFocus()
                        }
                    }

                    // Input area: Code / Assign (plain Item with visibility
                    // toggling — a nested StackLayout here propagates its
                    // children's minimum sizes and defeats preferredHeight)
                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 110

                        ScrollView {
                            id: codeScroll

                            anchors.fill: parent
                            visible: calcVM.inputMode === 0

                            TextArea {
                                id: codeInput

                                width: codeScroll.availableWidth
                                text: calcVM.inputText
                                wrapMode: TextArea.Wrap
                                placeholderText: qsTr("Enter expression...")
                                font.pixelSize: 15

                                onTextChanged: calcVM.inputText = text

                                // Smart mode switch: '=' in an empty input -> Assign
                                Keys.onPressed: (event) => {
                                    if (event.key === Qt.Key_Equal
                                            && !event.modifiers
                                            && calcVM.inputText.trim().length === 0) {
                                        switchToAssign()
                                        event.accepted = true
                                    }
                                }
                            }
                        }

                        RowLayout {
                            anchors.fill: parent
                            visible: calcVM.inputMode === 1
                            spacing: 8

                            TextField {
                                id: assignNameField

                                Layout.preferredWidth: 130
                                Layout.alignment: Qt.AlignVCenter
                                text: calcVM.assignName
                                placeholderText: qsTr("name")

                                onTextChanged: calcVM.assignName = text

                                // Smart navigation: an operator typed at the end of
                                // the name sets the combo and jumps to the value;
                                // backspace at position 0 returns to Code mode.
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

                            TextField {
                                id: assignValueField

                                Layout.fillWidth: true
                                Layout.minimumWidth: 80
                                Layout.alignment: Qt.AlignVCenter
                                text: calcVM.assignValue
                                placeholderText: qsTr("expression")

                                onTextChanged: calcVM.assignValue = text

                                Keys.onPressed: (event) => {
                                    // Single line: Enter calculates, never inserts a newline.
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
                        Layout.preferredHeight: 240
                        Layout.minimumHeight: 200
                        onKeyPressed: (key) => page.insertToInput(key)
                    }

                    // Vertical spacer: keys keep their size regardless of window height.
                    Item { Layout.fillHeight: true }
                }
            }

            // Right panel: result text, LaTeX area, plot area
            Item {
                SplitView.fillWidth: true
                SplitView.minimumWidth: 400

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 12

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            Layout.fillWidth: true
                            typography: Typography.Body
                            wrapMode: Text.Wrap
                            color: calcVM.isError
                                ? Theme.currentTheme.colors.systemCriticalColor
                                : Theme.currentTheme.colors.textColor
                            text: calcVM.resultText
                        }

                        Button {
                            text: qsTr("Copy expr")
                            icon.name: "ic_fluent_copy_20_regular"
                            flat: true
                            enabled: calcVM.inputMode === 0 && calcVM.inputText !== ""
                            onClicked: vm.copyText(calcVM.inputText)
                        }
                        Button {
                            text: qsTr("Copy LaTeX")
                            icon.name: "ic_fluent_copy_20_regular"
                            flat: true
                            enabled: calcVM.resultLatex !== ""
                            onClicked: vm.copyText(calcVM.resultLatex)
                        }
                    }

                    // LaTeX result area: rendered at the SVG's natural size
                    // (crisp, not upscaled), left-aligned; horizontal scroll.
                    ScrollView {
                        id: latexScroll

                        Layout.fillWidth: true
                        Layout.preferredHeight: page.hasLatex
                            ? Math.max(80, latexImage.height + 24) : 120
                        ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AlwaysOff }

                        MouseArea {
                            anchors.fill: parent
                            acceptedButtons: Qt.NoButton
                            onWheel: (wheel) => {
                                const max = Math.max(0, latexScroll.contentWidth - latexScroll.width)
                                const cur = latexScroll.contentItem.contentX
                                latexScrollAnim.to = Math.max(0,
                                    Math.min(max, cur - wheel.angleDelta.y / 120 * 30))
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

                        // implicit sizes drive the ScrollView's content size,
                        // avoiding an explicit contentWidth binding loop.
                        Item {
                            id: latexContent

                            implicitWidth: page.hasLatex ? latexImage.width : 1
                            implicitHeight: page.hasLatex ? latexImage.height : 120
                            width: Math.max(latexScroll.availableWidth, implicitWidth)
                            height: implicitHeight

                            Image {
                                id: latexImage

                                objectName: "latexImage"
                                x: 0
                                y: 0
                                visible: page.hasLatex
                                smooth: true
                                fillMode: Image.PreserveAspectFit

                                // Item stays at the SVG's logical size while the
                                // render resolution (sourceSize) is scaled by the
                                // screen DPI, keeping it crisp on high-DPI displays.
                                width: calcVM.latexWidth
                                height: calcVM.latexHeight
                                sourceSize: Qt.size(
                                    calcVM.latexWidth * Screen.devicePixelRatio,
                                    calcVM.latexHeight * Screen.devicePixelRatio)
                                source: page.hasLatex ? calcVM.latexSvgUrl : ""
                            }

                            Text {
                                anchors.fill: parent
                                visible: !page.hasLatex
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                wrapMode: Text.WrapAnywhere
                                typography: calcVM.isError ? Typography.Body : Typography.Subtitle
                                color: calcVM.isError
                                    ? Theme.currentTheme.colors.systemCriticalColor
                                    : calcVM.resultText === ""
                                      ? Theme.currentTheme.colors.textSecondaryColor
                                      : Theme.currentTheme.colors.textColor
                                text: calcVM.isError
                                    ? calcVM.errorMessage
                                    : calcVM.resultText !== ""
                                      ? calcVM.resultText
                                      : qsTr("Enter an expression, then press Ctrl+Return to calculate.")
                            }
                        }
                    }

                    // Plot area (empty placeholder)
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        color: Theme.currentTheme.colors.cardColor
                        radius: Theme.currentTheme.appearance.buttonRadius
                        border.width: Theme.currentTheme.appearance.borderWidth
                        border.color: Theme.currentTheme.colors.cardBorderColor

                        Row {
                            anchors.centerIn: parent
                            spacing: 10

                            Icon {
                                name: "ic_fluent_math_formula_20_regular"
                                size: 20
                                color: Theme.currentTheme.colors.textSecondaryColor
                            }
                            Text {
                                typography: Typography.Body
                                color: Theme.currentTheme.colors.textSecondaryColor
                                text: qsTr("Plotting is on the roadmap.")
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                    }
                }
            }
        }
    }

    Shortcut {
        sequences: ["Ctrl+Return"]
        onActivated: runCalculation()
    }

    Dialog {
        id: warningDialog

        property string contentText: ""

        title: qsTr("Warning")
        standardButtons: Dialog.Ok
        Text {
            Layout.fillWidth: true
            width: 320
            wrapMode: Text.WordWrap
            typography: Typography.Body
            color: Theme.currentTheme.colors.textColor
            text: warningDialog.contentText
        }
    }

    Connections {
        target: calcVM

        function onWarningOccurred(title, content) {
            warningDialog.title = title
            warningDialog.contentText = content
            warningDialog.open()
        }
    }
}
