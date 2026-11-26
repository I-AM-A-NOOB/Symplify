import QtQuick
import QtQuick as QQ
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Templates as T
import QtQuick.Window 2.15
import RinUI
import RinUI as Rin

//: The Calculator's input half: the Code / Assign stage, both editors and the
//: on-screen keyboard, plus the focus and cursor helpers the keyboard drives.
//:
//: A component because it is one stateful little machine (mode slide, focus
//: target, selection-aware insertion) sitting beside the result and the plot;
//: the page owns the toolbar and the split and calls into this. The mode itself
//: stays `calcVM.inputMode` — this only renders it and keeps the editors in step.
Item {
    id: root

    objectName: "inputPane"

    clip: true
    visible: !vm.zenMode

    //: The shared code-input dressing: surface ink, placeholder and code font.
    CodeInputLook { id: look }

    //: The inner text item of the Code box; the helpers below address it.
    readonly property Item codeInput: codeArea.textArea

    //: True after a focus jump triggered by an operator/Backspace. The OS keeps
    //: delivering auto-repeated events to the *new* focus item; swallow those
    //: until a fresh (non-repeat) press so holding the key cannot keep editing
    //: or jumping in the destination field.
    property bool repeatGuard: false

    function consumeRepeat(event) {
        if (event.isAutoRepeat) {
            if (root.repeatGuard) {
                event.accepted = true
                return true
            }
        } else {
            root.repeatGuard = false
        }
        return false
    }

    Component.onCompleted: {
        // CodeScrollArea owns the highlighter, so Code and Variables expression
        // boxes cannot attach two highlighters to the same document.
        codeInput.forceActiveFocus()
    }

    //: The focused text input *inside this pane*, if any.
    //:
    //: `Window.activeFocusItem` is the item Qt already tracks. The recursive
    //: walk this replaces scanned every child — the 200+ on-screen keys
    //: included — on every virtual key press to answer the same question.
    //: `isAncestorOf` keeps the rule the walk encoded: a text input on another
    //: surface must not become this keyboard's target, so focus outside the pane
    //: falls back to the current mode's editor.
    //: Does `item` live under this pane? `isAncestorOf` is C++-only (not a QML
    //: method), so the check walks the parent chain instead — a handful of
    //: steps, versus the old full-tree recursion.
    function belongsToPane(item) {
        let node = item
        while (node && node !== root)
            node = node.parent
        return node === root
    }

    function editableInPane(focused) {
        if (!focused || !belongsToPane(focused))
            return null
        // The template bases, not the style types: RinUI's TextArea derives from
        // Controls.Basic, while CodeField/CodeArea use Basic directly. Checking
        // the shadowing `TextArea`/`TextField` names made a Basic field fail the
        // test and the keyboard fall back to the wrong editor.
        if (focused instanceof T.TextArea
                || focused instanceof T.TextField
                || focused instanceof QQ.TextInput)
            return focused
        return null
    }

    function fallbackTarget() {
        return calcVM.inputMode === 0 ? codeInput : assignValueField.textArea
    }

    function keyboardTarget() {
        return editableInPane(Window.activeFocusItem) || fallbackTarget()
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

    //: Empty one editor through an undoable text operation. `clear()` resets
    //: the document in one go and can drop the edit history; `remove()` is the
    //: same replacement expressed as an edit, so the expression just cleared
    //: remains the next Undo step.
    function clearEditor(editor) {
        if (!editor || editor.length === 0)
            return
        if (editor.remove)
            editor.remove(0, editor.length)
        else if (editor.clear)
            editor.clear()
        else
            editor.text = ""
    }

    function clearInput() {
        const target = keyboardTarget()
        // "Clear" resets the whole workspace, not just the field that happens
        // to have focus. Both modes' editors are emptied through their own
        // undoable operation, then the result/plot/variants are reset.
        clearEditor(codeInput)
        clearEditor(assignNameField)
        clearEditor(assignValueField.textArea)
        calcVM.assignOperator = "="
        calcVM.clear_result()
        if (target)
            target.forceActiveFocus()
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

    function beginModeTransition() {
        inputStage.beginModeTransition()
    }

    function focusCode() {
        codeInput.forceActiveFocus()
    }

    function focusAssignName() {
        assignNameField.forceActiveFocus()
    }

    function switchToCode() {
        beginModeTransition()
        calcVM.inputMode = 0
        focusCode()
    }

    function switchToAssign() {
        beginModeTransition()
        calcVM.inputMode = 1
        focusAssignName()
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
                assignValueField.textArea.forceActiveFocus()
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
        spacing: 10

        // Input area: Code / Assign. Both live in the same clipped stage and
        // exchange places when the mode changes: one nudges out while fading,
        // the other nudges in while fading (`Motion.slide`), the same motion
        // the Calculator's Result/Plot Segmented uses. The inactive one is
        // disabled, so the hidden input never takes focus or keystrokes.
        Item {
            id: inputStage

            objectName: "inputStage"
            clip: true
            //: The first binding of `x` must not animate: a page rebuilt while
            //: the VM is in Assign mode would otherwise slide both rows in from
            //: the left.
            property bool slideReady: false
            //: Both editors must be visible while the mode cross-fade runs.
            //: Once it ends, the hidden one disappears so a sidebar width
            //: animation cannot expose it: its `x` offset is not tied to the
            //: stage's width any more, but a hidden editor should not take
            //: clicks or stay in the tab chain either.
            property bool modeSwitching: false

            function beginModeTransition() {
                modeSwitching = true
                modeSwitchTimer.restart()
            }

            Component.onCompleted: slideReady = true

            Timer {
                id: modeSwitchTimer
                interval: Motion.fast
                onTriggered: inputStage.modeSwitching = false
            }

            Layout.fillWidth: true
            // The Code box keeps its 110px footprint; Assign grows only as far
            // as its wrapping value needs. The spacer after the keyboard takes
            // the sidebar's spare height, so the keys stay above it instead of
            // floating.
            //: Code and Assign share one fixed stage height. The mode slide
            //: must not resize the workspace (and move the keyboard/result)
            //: when it switches; the value field scrolls inside this box.
            Layout.minimumHeight: 110
            Layout.preferredHeight: 110

            CodeScrollArea {
                id: codeArea

                objectName: "codeInput"
                //: The stage's two panes overlap; the inactive one is faded
                //: out and then hidden. Only the nudge (`Motion.slide`) and the
                //: cross-fade move — the same pair of values the tabbed
                //: Result/Plot switch uses.
                width: parent.width
                height: parent.height
                x: calcVM.inputMode === 0 ? 0 : -Motion.slide
                opacity: calcVM.inputMode === 0 ? 1 : 0
                enabled: calcVM.inputMode === 0
                visible: calcVM.inputMode === 0 || inputStage.modeSwitching
                //: Code leaves to the left, Assign arrives from the right; going
                //: back reverses both. WinUI's control motion, not OutCubic:
                //: the same curve as every other Segmented content switch.
                Behavior on x {
                    enabled: inputStage.slideReady
                    NumberAnimation {
                        duration: Motion.fast
                        easing.type: Easing.BezierSpline
                        easing.bezierCurve: Motion.enter
                    }
                }
                Behavior on opacity {
                    enabled: inputStage.slideReady
                    NumberAnimation {
                        duration: Motion.fast
                        easing.type: Easing.BezierSpline
                        easing.bezierCurve: Motion.enter
                    }
                }
                text: calcVM.inputText
                placeholderText: qsTr("Enter expression...")
                wrapMode: TextEdit.Wrap
                onTextChanged: calcVM.inputText = text
                //: The inner area is the text item: it draws the glyphs and
                //: holds the keystrokes, so the '=' shortcut lives here. Code
                //: and Variables expression boxes share this whole component.
                textArea.Keys.onPressed: (event) => {
                    if (root.consumeRepeat(event))
                        return
                    if (event.key === Qt.Key_Equal
                            && !event.modifiers
                            && calcVM.inputText.trim().length === 0) {
                        event.accepted = true
                        if (!event.isAutoRepeat) {
                            root.repeatGuard = true
                            root.switchToAssign()
                        }
                    }
                }
            }

            ColumnLayout {
                id: assignRow

                objectName: "assignInput"
                //: Mirror of the Code pane: same nudge, same curve, opposite
                //: side, so the two formats exchange places instead of one
                //: handing over to a static page.
                width: parent.width
                height: parent.height
                x: calcVM.inputMode === 1 ? 0 : Motion.slide
                opacity: calcVM.inputMode === 1 ? 1 : 0
                enabled: calcVM.inputMode === 1
                visible: calcVM.inputMode === 1 || inputStage.modeSwitching
                Behavior on x {
                    enabled: inputStage.slideReady
                    NumberAnimation {
                        duration: Motion.fast
                        easing.type: Easing.BezierSpline
                        easing.bezierCurve: Motion.enter
                    }
                }
                Behavior on opacity {
                    enabled: inputStage.slideReady
                    NumberAnimation {
                        duration: Motion.fast
                        easing.type: Easing.BezierSpline
                        easing.bezierCurve: Motion.enter
                    }
                }
                spacing: 8

                //: Name and operator on the first line; the value gets the full
                //: width and the remaining height on the second. A single row
                //: made the value field the narrow leftover between two fixed
                //: controls.
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    // The shared code field (surface, ink, code font), the same
                    // one the Variables page renames with.
                    CodeField {
                        id: assignNameField

                        objectName: "assignNameInput"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 80
                        Layout.alignment: Qt.AlignVCenter
                        text: calcVM.assignName
                        placeholderText: qsTr("name")
                        onTextChanged: calcVM.assignName = text

                        // Smart navigation: an operator typed at the end of the
                        // name sets the combo and jumps to the value; backspace at
                        // position 0 returns to Code mode. Auto-repeat must not
                        // perform either jump: holding a key should type/repeat in
                        // one field, and the next press after release can move.
                        Keys.onPressed: (event) => {
                            if (root.consumeRepeat(event))
                                return
                            const opMap = { "=": 0, "+": 1, "-": 2,
                                            "*": 3, "/": 4, "%": 5 }
                            const opIndex = opMap[event.text]
                            const mods = event.modifiers & ~Qt.ShiftModifier
                            if (opIndex !== undefined && mods === 0
                                    && cursorPosition === length) {
                                if (event.isAutoRepeat) {
                                    event.accepted = true
                                    return
                                }
                                calcVM.assignOperator = operatorCombo.operators[opIndex]
                                root.repeatGuard = true
                                assignValueField.textArea.forceActiveFocus()
                                event.accepted = true
                            } else if (event.key === Qt.Key_Backspace
                                       && cursorPosition === 0
                                       && selectedText === "") {
                                if (event.isAutoRepeat) {
                                    event.accepted = true
                                    return
                                }
                                root.repeatGuard = true
                                root.switchToCode()
                                event.accepted = true
                            }
                        }
                    }

                    Rin.ComboBox {
                        id: operatorCombo

                        objectName: "assignOperatorCombo"
                        readonly property var operators:
                            ["=", "+=", "-=", "*=", "/=", "%="]
                        Layout.alignment: Qt.AlignVCenter
                        model: operators
                        currentIndex: {
                            const i = model.indexOf(calcVM.assignOperator)
                            return i >= 0 ? i : 0
                        }
                        onActivated: (index) => calcVM.assignOperator = model[index]
                    }
                }

                // The same scrollable construction as Code mode and the
                // Variables expression field: an inner TextArea keeps the text
                // top-aligned, and the shared code surface/highlighter applies.
                CodeScrollArea {
                    id: assignValueField

                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.minimumHeight: 44
                    Layout.fillHeight: true
                    text: calcVM.assignValue
                    placeholderText: qsTr("expression")
                    wrapMode: TextEdit.Wrap
                    onTextChanged: calcVM.assignValue = text

                    textArea.objectName: "assignValueInput"
                    submitOnEnter: true
                    emptyBackspaceJumps: true
                    autoRepeatBlocked: root.repeatGuard
                    onSubmitRequested: root.runCalculation()
                    onNonAutoRepeatPressed: root.repeatGuard = false
                    onEmptyBackspacePressed: (autoRepeat) => {
                        // Holding Backspace must not leave the field: consume the
                        // repeated event; release, then press again to jump.
                        if (autoRepeat)
                            return
                        root.repeatGuard = true
                        assignNameField.forceActiveFocus()
                    }
                }
            }
        }

        KeyboardPanel {
            id: keyboardPanel

            Layout.fillWidth: true
            //: The panel animates its own implicit height; the layout follows
            //: it frame by frame instead of toggling between the two constants.
            //: The minimum is the same value, so collapse and expand are one
            //: curve rather than one direction clamping the minimum.
            Layout.preferredHeight: keyboardPanel.implicitHeight
            Layout.minimumHeight: keyboardPanel.implicitHeight
            onKeyPressed: (key) => root.insertToInput(key)
            onBackspacePressed: root.backspaceInput()
            onCursorLeftPressed: root.moveInputCursor(-1)
            onCursorRightPressed: root.moveInputCursor(1)
            onUndoPressed: root.undoInput()
            onRedoPressed: root.redoInput()
        }

        //: The mock-up's spacer: the input and the keyboard keep their sizes,
        //: and the empty rest of the sidebar belongs below the keys rather than
        //: inside the editor.
        Item { Layout.fillHeight: true }
    }
}
