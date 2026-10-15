import QtQuick
import QtQuick as QQ
import QtQuick.Layouts 2.15
import QtQuick.Controls.Basic 2.15 as QQC2
import RinUI
import RinUI as Rin
import "../components"

Item {
    id: page

    //: Which card is selected. A `ListView` owned this (`currentIndex`,
    //: `isCurrentItem`, `incrementCurrentIndex`); with a `Column` of delegates the
    //: page owns it, and the cards read it back.
    property int currentIndex: 0
    //: Set by the arrow keys, cleared by any click, so the focus ring stays put
    //: while selecting by keyboard.
    property bool keyboardNavigation: false

    //: First layout may already satisfy the load condition (a tall window with
    //: a short first batch); `maybeLoadMore` fills until it does not.
    Component.onCompleted: maybeLoadMore()

    //: Cards revealed so far, and how many more each time the reader reaches the
    //: bottom. A `Column` skips invisible children, so the content only ever spans
    //: what is loaded: the page starts on the newest `batch` entries and grows as
    //: it is scrolled, one batch at a time.
    property int loaded: 12
    readonly property int batch: 12
    //: How close to the bottom the reader gets before the next batch loads. Not
    //: the panel width, which happens to be the same number on its own page.
    readonly property int prefetchMargin: 320

    //: How far the cards sit from the page edge: the content is already inset
    //: 24px, and the cards add this much on each side, clear of the scroll bar.
    readonly property int cardInset: 4
    //: Load one more batch when the reader is already near the bottom of what
    //: is loaded. Deliberately a single step, never a loop: a batch's cards
    //: only join `contentHeight` after the next layout pass, so a loop reads a
    //: stale height and would pour in everything at once. After loading, the
    //: check re-queues itself for after that layout (`Qt.callLater`) — a
    //: `contentHeightChanged` handler would do the same job, but Qt swallows
    //: the re-entrant emission when the height changes inside a handler's own
    //: cycle, which stalls the chain one batch after a resize. The chain stops
    //: as soon as the condition is false. This is also what keeps a window too
    //: tall for one batch loading anyway: there is nothing to scroll, so
    //: `contentY` alone would never fire.
    function maybeLoadMore() {
        if (loaded < cards.count
                && historyScroll.contentY + historyScroll.height
                   > historyScroll.contentHeight - page.prefetchMargin) {
            loaded = Math.min(cards.count, loaded + batch)
            Qt.callLater(maybeLoadMore)
        }
    }

    //: End the selection on the current card's lines.
    //:
    //: Nothing else can: a line never holds focus here — the card takes it back
    //: the moment it becomes current (`forceActiveFocus`, for its own key
    //: handlers), so neither `persistentSelection` nor a focus-out hook has
    //: anything to work with (measured: `activeFocus` on a line is false before
    //: and after a drag across its text). So every click that is *not* on a line
    //: says so explicitly: this one for clicks anywhere else on the page, the
    //: card's own `onClicked` for its body, and each line's `clicked` for its
    //: sibling.
    function clearSelections() {
        const card = cards.itemAt(page.currentIndex)
        if (card)
            card.clearLines()
    }

    //: Everything the page does not otherwise consume — the title, the gutter,
    //: the frame around the list. A `TapHandler` and not a `MouseArea`: it claims
    //: only a tap (the default `DragThreshold`), so flicking the list is
    //: untouched.
    TapHandler {
        acceptedButtons: Qt.LeftButton
        onTapped: page.clearSelections()
    }

    //: Bring a card into view, which `ListView.positionViewAtIndex` did for us.
    function reveal(index) {
        if (index >= loaded)                  // not loaded yet: load up to it
            loaded = Math.min(cards.count, index + 1)
        const card = cards.itemAt(index)
        if (!card)
            return
        const top = content.y + card.y
        const bottom = top + card.height
        if (top < historyScroll.contentY)
            historyScroll.contentY = top
        else if (bottom > historyScroll.contentY + historyScroll.height)
            historyScroll.contentY = bottom - historyScroll.height
    }

    // LatexImage rendering follows the app theme color.
    // A `Flickable` + `Column` + `Repeater`, not a `ListView`. The list's `header`
    // slot cost three traps — it is a `Component`, so ids in it are invisible and
    // the row has to be fetched back through `headerItem`; the view does not size
    // it; and this view parks it above the viewport whatever `headerPositioning`
    // says — and what that bought was keeping delegates unbuilt until they scrolled
    // into view, which measures at ~0.5-1.5ms per entry of cached SVG. The title is
    // an ordinary child of the content now, exactly as on Log and Settings, so all
    // three pages wire `PageScaffold` the same way.
    Flickable {
        id: historyScroll

        anchors.fill: parent
        clip: true
        contentWidth: width
        // The content plus the page's bottom inset, so the last card can be
        // scrolled clear of the edge.
        contentHeight: content.height + frame.inset * 2

        //: The scroll area's own presses — the empty space below the last card.
        //: The page's handler cannot cover it: a press that lands on the
        //: `Flickable` is consumed there and never reaches the page above it
        //: (measured: clicking below the cards left the selection standing).
        //: Declared inside the Flickable, so it is handed the presses that land on
        //: the Flickable itself; a press on a card is the card's, and the cards
        //: clear their own lines.
        TapHandler {
            acceptedButtons: Qt.LeftButton
            onTapped: page.clearSelections()
        }

        //: One batch more as the reader nears the bottom of what is loaded.
        //: These two plus the page's completion cover every state where the
        //: load condition can newly hold; the `Qt.callLater` chain inside
        //: `maybeLoadMore` carries it through the following layouts.
        onContentYChanged: page.maybeLoadMore()
        onHeightChanged: page.maybeLoadMore()

        //: RinUI's own bar, attached to this flickable — the same bar the other
        //: two pages attach.
        Rin.ScrollBar.vertical: Rin.ScrollBar {}

        Column {
            id: content

            x: frame.inset
            y: frame.inset
            width: historyScroll.width - frame.inset * 2
            spacing: 10

            //: The title, and the row the actions ride until the bar takes over.
            PageHeaderRow {
                id: titleRow

                width: parent.width
                reservedWidth: frame.actionsWidth
                reservedHeight: frame.headerHeight
                //: Air between the title row and the first card.
                bottomGap: 12
                }

            Repeater {
                id: cards

                model: historyFilter

        delegate: QQC2.ItemDelegate {
            id: card

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
            readonly property real topInView: y + content.y - historyScroll.contentY
            //: `visible` comes first: a card that is not loaded yet is skipped by the
            //: `Column`, so it has no position of its own and `y` reads 0 — which
            //: this test would otherwise take for "at the top of the viewport".
            readonly property bool nearView: visible
                                          && topInView < historyScroll.height * 2
                                          && topInView > -historyScroll.height

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
            highlighted: card.index === page.currentIndex

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
                    page.currentIndex = index
            }

            // Keyboard-navigation flag: set on arrow keys, cleared on any
            // click. Drives the FocusIndicator so it stays while selecting
            // with Up/Down (mirrors ListViewDelegate.keyboardNavigation).
            readonly property bool keyboardNavigation:
                page.keyboardNavigation && highlighted

            width: content.width
            height: cardBody.implicitHeight + 20
            //: Not loaded yet? The `Column` skips it, so it costs nothing on screen
            //: and nothing in the scroll extent.
            visible: card.index < page.loaded

            // The card inset is the delegate's to apply, because the list is
            // full-bleed; then the content padding it always had, plus 8px so
            // the text keeps its distance from the card edge.
            leftPadding: page.cardInset + 18
            rightPadding: page.cardInset + 18
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
                            page.keyboardNavigation = false
                            page.currentIndex = card.index
                            openMenuAt(card.mapFromItem(inputLine, mx, my))
                        }

                        onClicked: {
                            page.keyboardNavigation = false
                            page.currentIndex = card.index
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
                        ToolTip {
                            delay: 500
                            visible: parent.hovered
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
                        page.keyboardNavigation = false
                        page.currentIndex = card.index
                        openMenuAt(card.mapFromItem(resultLine, mx, my))
                    }

                    onClicked: {
                        page.keyboardNavigation = false
                        page.currentIndex = card.index
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
                            page.keyboardNavigation = false
                            page.currentIndex = card.index
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
                anchors.leftMargin: page.cardInset + 2
                anchors.rightMargin: page.cardInset + 2
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
                id: hoverOverlay

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
                x: page.cardInset + 2
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
            //: somewhere other than on those lines — see `page.clearSelections`.
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
            //: `posX`/`posY` and not `popup(x, y)` because RinUI's `Menu` animates
            //: *towards* those two, so setting them is what both places the menu
            //: and plays the unfold.
            function openMenuAt(point) {
                entryMenu.posX = point.x
                entryMenu.posY = point.y
                entryMenu.popup()
            }

            //: …and RinUI's own place for the keyboard routes, which have no
            //: pointer: centred under the card, which is what its `Position.Bottom`
            //: computes from the parent.
            function openMenuDefault() {
                entryMenu.posX = (width - entryMenu.width) / 2
                entryMenu.posY = height + 5
                entryMenu.popup()
            }

            // Left click (card body) selects the card — and ends any selection
            // the reader had made on one of its lines: they have moved on, and a
            // highlight that exists to be copied should go with them.
            onClicked: {
                page.keyboardNavigation = false
                page.currentIndex = index
                clearLines()
            }

            // Right click selects the card and opens its menu at the
            // pointer. No exclusion checks: right clicks over the send
            // button or the scroll strip pass through to this handler.
            TapHandler {
                id: cardTap

                acceptedButtons: Qt.RightButton
                onTapped: (eventPoint) => {
                    page.keyboardNavigation = false
                    page.currentIndex = index
                    openMenuAt(eventPoint.position)
                }
            }

            // Arrow keys move the selection; a `ListView` kept the item in view
            // for us, so with a `Column` that part is `page.reveal`.
            Keys.onUpPressed: {
                page.keyboardNavigation = true
                page.currentIndex = Math.max(0, page.currentIndex - 1)
                page.reveal(page.currentIndex)
            }
            Keys.onDownPressed: {
                page.keyboardNavigation = true
                page.currentIndex = Math.min(cards.count - 1, page.currentIndex + 1)
                page.reveal(page.currentIndex)
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

            }
        }

    }

    // The empty state centres on the *viewport*, so it sits beside the body
    // rather than inside it: a `Flickable`'s children are parented to its content
    // item, whose height is the content's — with nothing loaded that is the title
    // row alone, so the text used to land on the title instead of in the middle
    // of the page, exactly as it does on Log.
    Text {
        anchors.centerIn: parent
        visible: cards.count === 0
        typography: Typography.Body
        color: Theme.currentTheme.colors.textSecondaryColor
        text: historyFilter.searchText !== "" && historyVM.count > 0
            ? qsTr("No calculations match this search.")
            : qsTr("No calculations yet. Results will appear here.")
    }

    // The frame: title, actions, floating bar, window-edge scroll bar. The
    // Flickable above owns everything that scrolls, including the title row.
    PageScaffold {
        id: frame

        title: qsTr("History")
        flickable: historyScroll
        inlineRow: titleRow

        SearchBar {
            id: searchBar

            Layout.alignment: Qt.AlignVCenter
            //: The bar's one flexible piece: when the window — or the details panel —
            //: leaves the row short, the field gives way before the title has to
            //: disappear, and never past a usable width.
            Layout.fillWidth: true
            Layout.maximumWidth: implicitWidth
            modeLabels: [qsTr("Fuzzy"), qsTr("Expression"), qsTr("Result")]
            onSearchRequested: (text, mode) => {
                historyFilter.searchText = text
                historyFilter.searchMode = mode
            }
        }

        // The page's actions, in one `CommandBar`: it draws the ones the row has
        // room for and folds the rest into its overflow menu, so a narrow window
        // costs a click instead of a button.
        CommandBar {
            // Qualified on purpose: the unqualified Controls types are not
            // imported here, and adding them would put second copies of
            // `ToolButton`, `Menu` and `ToolTip` beside RinUI's, which this page
            // already uses.
            QQC2.Action {
                text: qsTr("Clear history")
                icon.name: "ic_fluent_delete_20_regular"
                // The source count on purpose: an active search must not disable
                // clearing the history.
                enabled: historyVM.count > 0
                onTriggered: historyVM.clear()
            }
        }
    }
}
