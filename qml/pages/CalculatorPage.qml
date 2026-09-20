import QtQuick
import QtQuick.Controls 2.15
import QtQuick.Layouts 2.15
import RinUI
import "../components"

Item {
    id: page

    readonly property bool hasLatex: calcVM.latexSvgUrl !== ""

    // The input is RinUI's scrollable text area; the helpers below (focus,
    // insert, selectAll, fallbackTarget) address the text item, so this points
    // them at the wrapper's inner area.
    readonly property Item codeInput: codeArea.textArea

    // The code theme's surface — `background` and `ink` for the ACTIVE theme,
    // since a family has a dark and a light member. An empty value means the
    // family has no opinion (High Contrast Light states neither) and the UI
    // theme's own colours stand in.
    readonly property var codeSurface: settingsVM.codeSurface(Theme.isDark())

    Component.onCompleted: {
        calcVM.set_latex_color(Theme.currentTheme.colors.textColor)
        // Code colouring on the input. The item hands over its document, and the
        // palette follows the ACTIVE theme — RinUI resolves Auto against the OS,
        // so ask it rather than the setting.
        vm.attachCodeHighlighting(codeArea.textArea.textDocument, Theme.isDark())
        // The Assign value is the other place an expression gets typed.
        vm.attachCodeHighlighting(assignValueField.textDocument, Theme.isDark())
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
        runCalculation()
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
                typography: Typography.Subtitle
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
                        // The Code box wants the full 110px. Assign is a row of
                        // controls that only needs one line — but it has to grow
                        // when the value wraps: the value is a TextArea now (a
                        // TextField has no `textDocument`, so it cannot take the
                        // highlighter) and a TextArea wraps rather than scrolling
                        // sideways.
                        Layout.preferredHeight: calcVM.inputMode === 0
                                ? 110
                                : Math.min(240, Math.max(110, assignRow.implicitHeight + 8))

                        ScrollableTextArea {
                            id: codeArea

                            anchors.fill: parent
                            visible: calcVM.inputMode === 0
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

                        RowLayout {
                            id: assignRow

                            anchors.fill: parent
                            visible: calcVM.inputMode === 1
                            spacing: 8

                            TextField {
                                id: assignNameField

                                Layout.preferredWidth: 130
                                Layout.alignment: Qt.AlignVCenter
                                text: calcVM.assignName
                                placeholderText: qsTr("name")
                                font: settingsVM.codeFont
                                // Same surface as the two expression boxes — this is
                                // part of the Assign row the code theme dresses — and
                                // the same ink on it. Nothing highlights a name, so this
                                // is plain text colour; an empty family answer leaves the
                                // UI theme's colour in place, as it does for them.
                                background: CodeSurface {
                                    focused: assignNameField.activeFocus
                                }
                                color: page.codeSurface.ink
                                    || Theme.currentTheme.colors.textColor
                                placeholderTextColor: page.codeSurface.placeholder
                                    || Theme.currentTheme.colors.textSecondaryColor
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

                            // A TextArea, not a TextField: only TextArea/TextEdit
                            // expose `textDocument`, which is what the code
                            // highlighter attaches to. It keeps the field's
                            // manners — Enter still calculates (see below) — and
                            // wraps, so a long expression stays readable.
                            TextArea {
                                id: assignValueField

                                Layout.fillWidth: true
                                Layout.minimumWidth: 80
                                Layout.alignment: Qt.AlignVCenter
                                text: calcVM.assignValue
                                placeholderText: qsTr("expression")
                                wrapMode: TextEdit.Wrap
                                // Plain text: expressions hold < and &, which
                                // the rich text auto-detection would swallow.
                                textFormat: TextEdit.PlainText
                                font: settingsVM.codeFont
                                // Same surface as the Code box: an expression is
                                // typed here too, and it is coloured by the same
                                // highlighter.
                                background: CodeSurface {
                                    focused: assignValueField.activeFocus
                                }
                                color: page.codeSurface.ink
                                    || Theme.currentTheme.colors.textColor
                                placeholderTextColor: page.codeSurface.placeholder
                                    || Theme.currentTheme.colors.textSecondaryColor
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
                            // Code text: this is the expression's value, coloured by
                            // the same span list the input above is — through the
                            // markup renderer, so label and editor agree.
                            font: settingsVM.codeFont
                            textFormat: Text.RichText
                            wrapMode: Text.NoWrap
                            elide: Text.ElideRight
                            color: calcVM.isError
                                ? Theme.currentTheme.colors.systemCriticalColor
                                : Theme.currentTheme.colors.textColor
                            text: vm.highlighted(calcVM.resultText, Theme.isDark())
                        }

                        Button {
                            text: calcVM.inputMode === 1
                                ? qsTr("Copy value") : qsTr("Copy result")
                            icon.name: "ic_fluent_copy_20_regular"
                            flat: true
                            enabled: calcVM.resultText !== ""
                            onClicked: vm.copyText(calcVM.resultText)
                        }
                        Button {
                            text: qsTr("Copy LaTeX")
                            icon.name: "ic_fluent_copy_20_regular"
                            flat: true
                            enabled: calcVM.resultLatex !== ""
                            onClicked: vm.copyText(calcVM.resultLatex)
                        }
                    }

                    // Result region: the LaTeX area (natural height) and the
                    // fixed-4:3 plot area scroll vertically when the window
                    // is too short to show them all.
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

                            // LaTeX result area: rendered at the SVG's natural
                            // height (crisp, not upscaled), left-aligned; the
                            // vertical wheel pans horizontally and a scrollbar
                            // appears when needed.
                            HScrollView {
                                id: latexScroll

                                Layout.fillWidth: true
                                Layout.preferredHeight: page.hasLatex
                                    ? Math.max(60, latexImage.height + 16) : 120
                                contentWidth: Math.max(latexScroll.width, latexImage.width)

                                // implicit sizes drive the content size,
                                // avoiding an explicit contentWidth binding loop.
                                Item {
                                    id: latexContent

                                    implicitWidth: page.hasLatex ? latexImage.width : 1
                                    implicitHeight: page.hasLatex ? latexImage.height : 120
                                    width: Math.max(latexScroll.width, implicitWidth)
                                    height: implicitHeight

                                    LatexImage {
                                        id: latexImage

                                        objectName: "latexImage"
                                        visible: page.hasLatex
                                        x: 0
                                        y: (parent.height - height) / 2
                                        naturalWidth: calcVM.latexWidth
                                        naturalHeight: calcVM.latexHeight
                                        source: page.hasLatex ? calcVM.latexSvgUrl : ""
                                    }

                                    // Shown instead of the rendered LaTeX
                                    // (error text, or the plain result when
                                    // there is no LaTeX for it) — an output, so
                                    // it typesets in the code font too.
                                    Text {
                                        anchors.fill: parent
                                        visible: !page.hasLatex
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                        wrapMode: Text.WrapAnywhere
                                        font: settingsVM.codeFont
                                        // The value is coloured like the input it
                                        // came from; the hint and a failure are
                                        // prose, so they stay plain (and raw — a
                                        // translation is not markup).
                                        textFormat: calcVM.isError || calcVM.resultText === ""
                                            ? Text.PlainText : Text.RichText
                                        color: calcVM.isError
                                            ? Theme.currentTheme.colors.systemCriticalColor
                                            : calcVM.resultText === ""
                                              ? Theme.currentTheme.colors.textSecondaryColor
                                              : Theme.currentTheme.colors.textColor
                                        text: calcVM.isError
                                            ? calcVM.errorMessage
                                            : calcVM.resultText !== ""
                                              ? vm.highlighted(calcVM.resultText, Theme.isDark())
                                              : qsTr("Enter an expression, then press Ctrl+Return to calculate.")
                                    }
                                }
                            }

                            // Function/plot area with a fixed 4:3 aspect ratio.
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: width * 0.75
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
