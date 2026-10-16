import QtQuick
import QtQuick.Controls 2.15
import QtQuick.Layouts 2.15
import RinUI
import RinUI as Rin
import "../components"

Item {
    id: page

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

                Tip {
                    text: parent.text
                }

                onClicked: runCalculation()
            }

            ToolSeparator {}

            //: The bar's own row of editing actions, each an icon with its
            //: tooltip. The bar folds whatever does not fit behind its own "more"
            //: button, so adding an action to it costs the row nothing.
            CommandBar {
                //: The buttons continue the title rather than close the row, so
                //: they hug the left edge this bar was given.
                contentAlignment: Qt.AlignLeft
                //: And the bar must not span the row: the examples button follows
                //: it, and a bar that filled the width would push that button out
                //: to the far edge (measured: the bar at 486 px of empty space and
                //: Examples at x=751 before this line). Folding still works — a row
                //: layout shrinks the bar to its share, which is what the fold
                //: count reads.
                Layout.fillWidth: false

                Action {
                    text: qsTr("Clear input")
                    icon.name: "ic_fluent_clear_formatting_20_regular"
                    onTriggered: clearInput()
                }
                Action {
                    text: qsTr("Undo")
                    icon.name: "ic_fluent_arrow_undo_20_regular"
                    onTriggered: undoInput()
                }
                Action {
                    text: qsTr("Redo")
                    icon.name: "ic_fluent_arrow_redo_20_regular"
                    onTriggered: redoInput()
                }
            }

            ToolSeparator {}

            //: The examples, as a dropdown of their own rather than a member of the
            //: bar: they write into the input instead of acting on it, which makes
            //: them a different kind of thing from the row of actions — and the
            //: bar's own folding would fold them away as though they were one more
            //: action. Subtle-styled: the accent on Calculate is the page's one
            //: shout, and this is the other side of it.
            DropDownButton {
                flat: true
                text: qsTr("Examples")
                icon.name: "ic_fluent_math_formula_20_regular"
                icon.color: enabled
                    ? Theme.currentTheme.colors.textColor
                    : Theme.currentTheme.colors.textDisabledColor
                Tip {
                    text: parent.text
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

                        //: The app's context menu for the Code box (see
                        //: `CodeContextMenu`): a sibling of the box rather than a
                        //: child, because the box is RinUI's `ScrollableTextArea`
                        //: and this has to sit *over* it — ahead of the menu its
                        //: own inner `TextArea` opens from a vendored `MouseArea`.
                        //: It covers what the box covers, and shows when the box
                        //: does.
                        CodeContextMenu {
                            editor: codeArea.textArea
                            anchors.fill: parent
                            visible: calcVM.inputMode === 0
                        }

                        RowLayout {
                            id: assignRow

                            anchors.fill: parent
                            visible: calcVM.inputMode === 1
                            spacing: 8

                            // The shared code field (surface, ink, code font), the
                            // same one the Variables page renames with.
                            CodeField {
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

                            // The shared highlighted code area — it wraps, so a
                            // long expression stays readable, and it keeps the
                            // field's manners: Enter still calculates (below).
                            CodeArea {
                                id: assignValueField

                                Layout.fillWidth: true
                                Layout.minimumWidth: 80
                                Layout.alignment: Qt.AlignVCenter
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

                    //: The copy buttons stand alone now that the outcome box lives
                    //: in the scroll area below: they read as the panel's actions
                    //: rather than as part of the result line.
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Item { Layout.fillWidth: true }

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
                                Layout.preferredHeight: Math.round(settingsVM.codeSize * 4.2)
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
                                        : qsTr("result ∈ LaTeX"))
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

                                naturalWidth: calcVM.latexWidth
                                naturalHeight: calcVM.latexHeight
                                source: calcVM.latexSvgUrl
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

    //: The calculator's own refusals — a SymPy built-in name, which is stored but
    //: worth saying out loud. The dialog and its wiring are the shared pair.
    WarningDialog {
        source: calcVM
    }
}
