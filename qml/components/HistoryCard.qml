import QtQuick
import QtQuick as QQ
import QtQuick.Layouts
import QtQuick.Controls.Basic 2.15 as QQC2
import RinUI

//: One history card — the delegate the History page's `Repeater` builds, one per
//: entry. It is a component of its own because that page is otherwise a 700-line file
//: whose bulk is this card: its two code lines, the formula strip, the hover, the
//: accent bar, the focus ring, its context menu and its keyboard handling.
//:
//: Two things come from the page (`host`) rather than from the model, both `required`
//: so a caller cannot forget them:
//: * `host` — the page. The card reads which card is current, how many are loaded and
//:   the page's inset, and it tells the page which card the reader picked
//:   (`host.currentIndex`, `host.keyboardNavigation`). Selection and keyboard focus are
//:   deliberately one thing on that page, so the card cannot own them:
//:   `onHighlightedChanged`/`onActiveFocusChanged` are the page's arrows, and the
//:   arrow keys move `host.currentIndex` and then call `host.reveal`.
//:   (`host.cardCount` is the page's `Repeater` count, for the arrow keys' bound.)
//: * `scroller` — the page's `PageBody`. `topInView` maps this card's `y` into the
//:   viewport, so it needs the body's content origin (`contentBox.y`) and `contentY`.
//:
//: The model roles arrive as `required` properties, exactly as they did inline.
QQC2.ItemDelegate {
    id: card
    //: The page that owns this card (see above).
    required property Item host
    //: The page's `PageBody`, for the viewport arithmetic (see above).
    required property Item scroller

    required property int index
    required property string mode
    required property string name
    required property string op
    required property string expression
    required property string result
    required property string error
    //: The LaTeX *source*, for the copy menu — cheap, so it stays a role.
    required property string latex
    //: These three are cheap to read now — `HistoryModel.data` no longer
    //: renders, it only looks the SVG up — so reading them at build time
    //: costs nothing. What renders is `historyVM.requestLatex`, called from
    //: `onLatexUrlChanged` below, i.e. only while this card is near the
    //: viewport (see `nearView`) and again if the cache was dropped.
    required property string latexUrl
    required property int naturalWidth
    required property int naturalHeight
    required property string time

    // An error card keeps its input plus the failure text instead
    // of a result, so the input can be sent back and fixed.
    readonly property bool isError: card.error !== ""
    readonly property color errorColor:
        Theme.currentTheme.colors.systemCriticalColor

    //: Where this card's top is in the viewport, and whether it is close
    //: enough to be worth rendering. Only the top edge is tested — testing
    //: the card's own height would make this depend on what it gates, and
    //: the two would chase each other. One screen of slack either way.
    readonly property real topInView: y + scroller.contentBox.y
                                    - scroller.contentY
    //: `visible` comes first: a card that is not loaded yet is skipped by the
    //: `Column`, so it has no position of its own and `y` reads 0 — which
    //: this test would otherwise take for "at the top of the viewport".
    readonly property bool nearView: visible
                                  && topInView < scroller.height * 2
                                  && topInView > -scroller.height

    //: Rendering is the view's to ask for (see `HistoryModel.requestLatex`).
    //: Both triggers end in a no-op once the entry has an SVG: `nearView`
    //: fires as the card approaches, and `latexUrl` changes back to empty
    //: when the cache is dropped under us by a theme or font change.
    function askForLatex() {
        if (nearView && latexUrl === "")
            historyVM.requestLatex(card.index)
    }
    onNearViewChanged: askForLatex()
    onLatexUrlChanged: askForLatex()
    Component.onCompleted: askForLatex()

    // Selection = the current item; drives the background tint
    // and the accent bar (mirrors ListViewDelegate.highlighted).
    highlighted: card.index === host.currentIndex

    // The current card holds keyboard focus so Enter/Space/
    // Shift+F10 open its menu; arrow keys navigate the list
    // (Keys.onUpPressed/onDownPressed). forceActiveFocus grants
    // real active focus (a plain `focus:` binding does not), so
    // the Keys handlers actually fire.
    activeFocusOnTab: true
    onHighlightedChanged: {
        if (highlighted) {
            forceActiveFocus()
        } else {
            //: A selection belongs to the card it was made on: when another
            //: card becomes the current one, this card's highlight goes with
            //: it. Without this a line stayed looking selected after the
            //: reader had moved on — clicking the padding, the timestamp or
            //: empty space moves no focus, so Qt has nothing to clear it on.
            inputLine.clearSelection()
            resultLine.clearSelection()
        }
    }

    // Keyboard focus *is* the selection (Fluent list semantics):
    // Tab/Backtab or a click makes the focused card current, so the
    // accent bar and the focus ring always sit on the same card.
    onActiveFocusChanged: {
        if (activeFocus)
            host.currentIndex = index
    }

    // Keyboard-navigation flag: set on arrow keys, cleared on any
    // click. Drives the FocusIndicator so it stays while selecting
    // with Up/Down (mirrors ListViewDelegate.keyboardNavigation).
    readonly property bool keyboardNavigation:
        host.keyboardNavigation && highlighted

    width: parent.width
    height: cardBody.implicitHeight + 20
    //: Not loaded yet? The `Column` skips it, so it costs nothing on screen
    //: and nothing in the scroll extent.
    visible: card.index < host.loaded

    // The card inset is the delegate's to apply, because the list is
    // full-bleed; then the content padding it always had, plus 8px so
    // the text keeps its distance from the card edge.
    leftPadding: host.cardInset + 18
    rightPadding: host.cardInset + 18
    bottomPadding: 18

    topPadding: 18

    //: Widths of the plain prefixes (`> `, `name op `, the aligned
    //: `= ` line) the two code lines hang in front of the highlighted
    //: text — the viewmodel elides that text to what remains. A
    //: no-break space has the same advance as a plain one, so the
    //: alignment padding measures with spaces.
    readonly property string inputPrefix:
        card.mode === "Assign" ? `${card.name} ${card.op} ` : "> "
    readonly property string resultPrefix:
        //: For an assignment the LaTeX is the whole definition (`x = …`),
        //: so the prefix the value-line aligns under would print the name a
        //: second time. Errors have no LaTeX — hence no prefix either.
        card.isError || card.mode === "Assign"
            ? "" : "&nbsp;".repeat(card.name.length + 1) + "= "
    readonly property string resultPrefixPlain:
        card.isError || card.mode === "Assign"
            ? "" : "\u00A0".repeat(card.name.length + 1) + "= "


    contentItem: ColumnLayout {
        id: cardBody
        spacing: 6

        // Input line + send-to-input button (pinned top-right).
        RowLayout {
            Layout.fillWidth: true
            spacing: 4

            // A read-only `TextEdit` for the same reason as the result
            // line below: what you typed is as much of a takeaway as
            // what came back, and it was the one line on the card that
            // could not be selected. Same dressing as the result line.
            //: One shared component for both pages' read-only text —
            //: selectable, never editable, and without RinUI's right-click
            //: menu (a read-only box offers neither Cut nor Paste). The
            //: `TapHandler` hands a plain click to the card and leaves a
            //: drag to the text: the box owns left presses for selecting,
            //: which is what stopped the card's own click from firing.
            CopyableLabel {
                id: inputLine
                objectName: "inputLine"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.alignment: Qt.AlignVCenter
                color: Theme.currentTheme.colors.textColor
                //: The whole expression, never a truncation of it: the
                //: box clips at the row's width, the selection spans all
                //: of it, and the copy is what was typed.
                text: card.inputPrefix
                    + (vm ? vm.highlighted(
                               card.expression, Theme.isDark()) : "")

                //: The same right click as the result line's, and the
                //: same as a click on the card: the menu belongs to the
                //: whole card, not to the padding around its text.
                //: `card.mapFromItem` and not a bare `mapFromItem`: this
                //: handler's scope is the *label*, so an unqualified call
                //: maps from the label to the label — measured, the menu
                //: then landed a label's offset away from the pointer.
                onRightClicked: (mx, my) => {
                    host.keyboardNavigation = false
                    host.currentIndex = card.index
                    openMenuAt(card.mapFromItem(inputLine, mx, my))
                }

                onClicked: {
                    host.keyboardNavigation = false
                    host.currentIndex = card.index
                    card.clearLines()
                }
            }

            // Always visible and enabled -- only the opacity
            // changes, so the layout (and card height) never
            // moves. Reaching it (hover or keyboard focus) is an
            // intent to interact, so it stays clickable.
            ToolButton {
                id: sendBtn
                objectName: "sendBtn"

                visible: true
                opacity: (cardHover.hovered || card.activeFocus
                          || sendBtn.activeFocus
                          || sendBtn.hovered) ? 1.0 : 0.0

                Behavior on opacity {
                    NumberAnimation { duration: 150 }
                }

                icon.name: "ic_fluent_calculator_arrow_clockwise_20_regular"
                icon.color: Theme.currentTheme.colors.textColor
                Tip {
                    text: qsTr("Send to input")
                }
                onClicked: {
                    if (card.mode === "Assign")
                        vm.sendToAssign(card.name, card.op,
                                        card.expression)
                    else
                        vm.sendToCode(card.expression)
                }
            }
        }

        // Result line: the '=' is aligned with the assignment
        // operator (leading spaces = name length + 1). A failed
        // entry shows its failure text here instead -- in the
        // critical color and wrapped, since eliding it would hide
        // the very thing the card is for. Everything else on an
        // error card (input line, background) stays normal.
        // A read-only `TextEdit`, so the result is selectable and
        // copyable: on a page of calculation cards the result is the
        // thing you take away, and only the calculator's outcome box
        // was. It draws no background of its own and sits at its
        // line height, so the card does not move.
        CopyableLabel {
            id: resultLine
            objectName: "resultLine"

            Layout.fillWidth: true
            Layout.minimumWidth: 0
            //: An error's prose wraps so none of the message is hidden;
            //: a result stays on one line and lets the box clip it.
            wrap: card.isError
            textFormat: card.isError ? TextEdit.PlainText : TextEdit.RichText
            color: card.isError
                ? card.errorColor
                : Theme.currentTheme.colors.textSecondaryColor
            text: card.isError
                ? card.error
                : card.resultPrefix
                  + (vm ? vm.highlighted(
                              card.result, Theme.isDark()) : "")

            onRightClicked: (mx, my) => {
                host.keyboardNavigation = false
                host.currentIndex = card.index
                openMenuAt(card.mapFromItem(resultLine, mx, my))
            }

            onClicked: {
                host.keyboardNavigation = false
                host.currentIndex = card.index
                card.clearLines()
            }
        }

        // Rendered result, horizontally scrollable (see `MathStrip`
        // for the geometry, including the room its overlay bar needs).
        // Hidden outright when the entry has no artwork — the card's
        // Result line is where a failure is reported.
        MathStrip {
            Layout.fillWidth: true

            visible: card.naturalHeight > 0
            naturalWidth: card.naturalWidth
            naturalHeight: card.naturalHeight
            source: card.latexUrl

            // The scroll strip is a Flickable, so it owns left
            // presses and the delegate's onClicked doesn't fire
            // here; forward simple clicks (no drag = no scroll).
            // Right clicks pass through to the card's own handler.
            TapHandler {
                acceptedButtons: Qt.LeftButton
                onTapped: {
                    host.keyboardNavigation = false
                    host.currentIndex = card.index
                }
            }
        }
        // Timestamp, bottom-right.
        QQ.Text {
            Layout.alignment: Qt.AlignRight
            // Below the card body as well as beside it: the strip's
            // overlay bar sits along the bottom edge, and the timestamp
            // used to share the last row with it.
            Layout.bottomMargin: 8
            font.pixelSize: 11
            color: Theme.currentTheme.colors.textTertialyColor
            text: card.time
        }
    }

    background: Rectangle {
        id: cardBg

        anchors.fill: parent
        anchors.topMargin: 2
        anchors.bottomMargin: 2
        anchors.leftMargin: host.cardInset + 2
        anchors.rightMargin: host.cardInset + 2
        radius: Theme.currentTheme.appearance.buttonRadius
        color: (card.highlighted || cardHover.hovered)
            ? Theme.currentTheme.colors.subtleSecondaryColor
            : "transparent"

        Behavior on color {
            ColorAnimation { duration: 120 }
        }

        // Fluent keyboard-focus ring. control is a Control
        // (ItemDelegate), so visualFocus/focusReason resolve; the
        // ring shows for keyboard navigation (arrow keys) and
        // Tab/Backtab focus, never on a mouse click.
        FocusIndicator {
            control: card
            keyboardFocus: card.keyboardNavigation
        }
    }

    // The card's hover, from an overlay that sits *above* the content.
    //
    // Not on the background, which is where this used to be: `background`
    // is a sibling of `contentItem`, so a pointer over anything the card
    // holds — its two text lines above all — walks a chain that never
    // includes the background, and its handler saw nothing. Measured with
    // the real cursor: over a line's text, `hovered` was false, while the
    // same pointer over the card's padding reported true. This item is
    // declared after the content, so it is the topmost thing over the card
    // and its handler is always in that chain. A plain `Item` accepts no
    // button, so clicks, drags and the text's own selection still reach
    // what is underneath.
    Item {
        anchors.fill: cardBg
        HoverHandler { id: cardHover }
    }

    // Selected-item accent bar. Cards are tall and variable
    // height, so it tracks the card with a fixed 20px inset. The
    // enter animation follows RinUI's Indicator (opacity + height
    // + y expansion).
    Rectangle {
        id: selectBar

        visible: card.highlighted
        x: host.cardInset + 2
        y: 20
        width: 3
        radius: 2
        color: Theme.currentTheme.colors.primaryColor
        height: card.height - 40 - card.topInset

        onVisibleChanged: {
            if (visible)
                enterAnimation.restart()
        }

        ParallelAnimation {
            id: enterAnimation

            PropertyAnimation {
                target: selectBar
                property: "opacity"
                from: 0.0
                to: 1.0
                duration: Utils.animationSpeed
                easing.type: Easing.OutQuad
            }
            ParallelAnimation {
                PropertyAnimation {
                    target: selectBar
                    property: "height"
                    from: 0
                    to: card.height - 40
                    duration: Utils.animationSpeedMiddle
                    easing.type: Easing.OutQuint
                }
                PropertyAnimation {
                    target: selectBar
                    property: "y"
                    from: card.height / 2
                    to: 20
                    duration: Utils.animationSpeedMiddle
                    easing.type: Easing.OutQuint
                }
            }
        }
    }

    //: Drop both lines' selections. Called whenever a click lands
    //: somewhere other than on those lines — see the page's `clearSelections`.
    function clearLines() {
        inputLine.clearSelection()
        resultLine.clearSelection()
    }

    //: Open the menu at a point in the *card's* own coordinates.
    //:
    //: A menu's position is relative to its parent item, and this menu's
    //: parent is the delegate — it is declared here so its items can read
    //: `card`. The pointer therefore has to arrive in this space: the
    //: scene point the first attempt passed puts the menu a card's height
    //: further down the page, and the lower the card, the further off.
    function openMenuAt(point) {
        openMenu(point.x, point.y)
    }

    //: …and RinUI's own place for the keyboard routes, which have no
    //: pointer: centred under the card, which is what its `Position.Bottom`
    //: computes from the parent.
    function openMenuDefault() {
        openMenu((width - entryMenu.width) / 2, height + 5)
    }

    //: One door for both routes, and the *second* gesture is why it is not a one-liner.
    //: RinUI's `Menu` drives its `x`/`y` from `posX`/`posY` through its `enter`
    //: transition, so setting the two on an *open* menu moves nothing: measured, a
    //: second right-click at a new point left the menu exactly where the first had put
    //: it, and a third one moved it to `x=864, y=-150` — off the window, which is the
    //: flash the page used to show. Every gesture therefore closes what is open and
    //: opens again, and the re-open waits for `onClosed`: a QQC2 `Popup` keeps
    //: `visible` true until its exit transition has finished, so calling `popup()`
    //: immediately after `close()` is silently swallowed (measured: the menu stayed
    //: closed). `pendingPoint` is that hand-off — non-null only for a re-open, so a
    //: close by clicking outside leaves it alone.
    property var pendingPoint: null

    function openMenu(x, y) {
        if (entryMenu.visible) {
            pendingPoint = Qt.point(x, y)
            entryMenu.close()
            return
        }
        entryMenu.posX = x
        entryMenu.posY = y
        entryMenu.popup()
    }

    // Left click (card body) selects the card — and ends any selection
    // the reader had made on one of its lines: they have moved on, and a
    // highlight that exists to be copied should go with them.
    onClicked: {
        host.keyboardNavigation = false
        host.currentIndex = index
        clearLines()
    }

    // Right click selects the card and opens its menu at the
    // pointer. No exclusion checks: right clicks over the send
    // button or the scroll strip pass through to this handler.
    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: (eventPoint) => {
            host.keyboardNavigation = false
            host.currentIndex = index
            openMenuAt(eventPoint.position)
        }
    }

    // Arrow keys move the selection; a `ListView` kept the item in view
    // for us, so with a `Column` that part is `host.reveal`.
    Keys.onUpPressed: {
        host.keyboardNavigation = true
        host.currentIndex = Math.max(0, host.currentIndex - 1)
        host.reveal(host.currentIndex)
    }
    Keys.onDownPressed: {
        host.keyboardNavigation = true
        host.currentIndex = Math.min(host.cardCount - 1, host.currentIndex + 1)
        host.reveal(host.currentIndex)
    }

    // Keyboard: menu at the default position (not the pointer).
    Keys.onReturnPressed: openMenuDefault()
    Keys.onEnterPressed: openMenuDefault()
    Keys.onSpacePressed: openMenuDefault()
    Keys.onPressed: (event) => {
        // Context-menu key / Shift+F10.
        if (event.key === Qt.Key_Menu
                || (event.key === Qt.Key_F10
                    && (event.modifiers & Qt.ShiftModifier))) {
            openMenuDefault()
            event.accepted = true
        }
    }

    Menu {
        id: entryMenu

        //: The re-open a second gesture asked for (see `openMenu`): a close has
        //: really finished here, which is the moment `popup()` starts working again.
        onClosed: {
            if (card.pendingPoint) {
                const p = card.pendingPoint
                card.pendingPoint = null
                card.openMenu(p.x, p.y)
            }
        }

        MenuItem {
            text: qsTr("Send to input")
            onTriggered: {
                if (card.mode === "Assign")
                    vm.sendToAssign(card.name, card.op,
                                    card.expression)
                else
                    vm.sendToCode(card.expression)
            }
        }

        MenuSeparator {}

        // A failed entry has no result and no LaTeX to copy, so the
        // copy items are disabled rather than silently copying "".
        MenuItem {
            text: card.mode === "Assign"
                ? qsTr("Copy value") : qsTr("Copy result")
            enabled: !card.isError
            onTriggered: vm.copyText(card.result)
        }
        MenuItem {
            text: qsTr("Copy LaTeX")
            enabled: !card.isError
            onTriggered: vm.copyText(card.latex)
        }
        MenuItem {
            text: qsTr("Copy expression")
            onTriggered: vm.copyText(card.expression)
        }
    }
}
