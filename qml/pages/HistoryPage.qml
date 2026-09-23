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
                   > historyScroll.contentHeight - 320) {
            loaded = Math.min(cards.count, loaded + batch)
            Qt.callLater(maybeLoadMore)
        }
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
        contentHeight: content.height + 48

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

            x: 24
            y: 24
            width: historyScroll.width - 48
            spacing: 10

            //: The title, and the row the actions ride until the bar takes over.
            PageHeaderRow {
                id: titleRow

                width: parent.width
                reservedWidth: frame.actionsWidth
                //: Air between the title row and the first card.
                bottomGap: 12
                title: qsTr("History")
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
                if (highlighted)
                    forceActiveFocus()
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
                card.isError ? "" : "&nbsp;".repeat(card.name.length + 1) + "= "
            readonly property string resultPrefixPlain:
                card.isError ? "" : "\u00A0".repeat(card.name.length + 1) + "= "
            TextMetrics {
                id: inputPrefixMetrics
                font: settingsVM.codeFont
                text: card.inputPrefix
            }
            TextMetrics {
                id: resultPrefixMetrics
                font: settingsVM.codeFont
                text: card.resultPrefixPlain
            }

            contentItem: ColumnLayout {
                id: cardBody
                spacing: 6

                // Input line + send-to-input button (pinned top-right).
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    QQ.Text {
                        Layout.fillWidth: true
                        // Rich text's implicit width is the full text, and a
                        // layout defaults an item's minimum to that — zero it
                        // so the row squeezes this line instead of overflowing.
                        Layout.minimumWidth: 0
                        Layout.alignment: Qt.AlignVCenter
                        font: settingsVM.codeFont
                        color: Theme.currentTheme.colors.textColor
                        // `Text.elide` is ignored for rich text, so the
                        // expression is elided by the viewmodel, on the plain
                        // string, to what remains of the line beside the prefix.
                        textFormat: QQ.Text.RichText
                        text: card.inputPrefix
                            + vm.highlightedElided(card.expression,
                                                   width - inputPrefixMetrics.width,
                                                   Theme.isDark())
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
                QQ.Text {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    // Code text: the aligned `= result` line. The name-length
                    // padding aligns it under the assignment operator, so it
                    // has to stay monospace for the alignment to hold. The
                    // result is elided by the viewmodel to what remains beside
                    // the padding: `Text.elide` is ignored for rich text.
                    font: settingsVM.codeFont
                    color: card.isError
                        ? card.errorColor
                        : Theme.currentTheme.colors.textSecondaryColor
                    wrapMode: card.isError ? QQ.Text.WordWrap : QQ.Text.NoWrap
                    // Rich text collapses runs of spaces, so the padding that
                    // holds `=` under the assignment operator has to be
                    // non-breaking. A failure is prose, so it stays plain.
                    textFormat: card.isError ? QQ.Text.PlainText : QQ.Text.RichText
                    text: card.isError
                        ? card.error
                        : card.resultPrefix
                          + vm.highlightedElided(card.result,
                                                 width - resultPrefixMetrics.width,
                                                 Theme.isDark())
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

                // On the card, not on the delegate: the delegate is full-bleed, so
                // a handler there would light the card up from the page gutter.
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

            // Left click (card body) selects the card.
            onClicked: {
                page.keyboardNavigation = false
                page.currentIndex = index
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
                    entryMenu.popup(eventPoint.position)
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
            Keys.onReturnPressed: entryMenu.popup()
            Keys.onEnterPressed: entryMenu.popup()
            Keys.onSpacePressed: entryMenu.popup()
            Keys.onPressed: (event) => {
                // Context-menu key / Shift+F10.
                if (event.key === Qt.Key_Menu
                        || (event.key === Qt.Key_F10
                            && (event.modifiers & Qt.ShiftModifier))) {
                    entryMenu.popup()
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
            modeLabels: [qsTr("Fuzzy"), qsTr("Expression"), qsTr("Result")]
            onSearchRequested: (text, mode) => {
                historyFilter.searchText = text
                historyFilter.searchMode = mode
            }
        }

        ToolButton {
            icon.name: "ic_fluent_delete_20_regular"
            icon.color: enabled
                ? Theme.currentTheme.colors.textColor
                : Theme.currentTheme.colors.textDisabledColor
            flat: true
            // The source count on purpose: an active search must not disable
            // clearing the history.
            enabled: historyVM.count > 0
            ToolTip {
                delay: 500
                visible: parent.hovered
                text: qsTr("Clear history")
            }
            onClicked: historyVM.clear()
        }
    }
}
