import QtQuick
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
    //: How many cards exist — the `Repeater`'s count. `HistoryCard`'s arrow keys
    //: clamp to it (the cards are the page's to count, not their own).
    readonly property int cardCount: cards.count
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
        const top = historyScroll.contentBox.y + card.y
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
    // an ordinary child of the content now, exactly as on the other three pages, so
    // all four wire `PageScaffold` the same way.
    PageBody {
        id: historyScroll

        frame: frame
        anchors.fill: parent

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

        Column {
            id: content

            width: parent.width
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

                delegate: HistoryCard {
                    host: page
                    scroller: historyScroll
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
            //: The bar's one flexible piece: when the window leaves the row short, the
            //: field gives way before the title has to disappear, and never past a
            //: usable width.
            Layout.alignment: Qt.AlignVCenter
            Layout.fillWidth: true
            Layout.maximumWidth: implicitWidth
            //: The box drives the proxy itself, and adopts whatever query the proxy
            //: still holds — see `SearchBar.filter`.
            filter: historyFilter
            modeLabels: [qsTr("Fuzzy"), qsTr("Expression"), qsTr("Result")]
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
