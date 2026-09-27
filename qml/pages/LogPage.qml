import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import RinUI as Rin
import "../components"

// The log is edge to edge and borderless: no card behind it, no rounded chrome of
// its own — the page *is* the text view. Four details shape the layout.
//
//   * A `Flickable` carries the content and declares its own `contentHeight`,
//     which is the Settings page's arrangement too. A `ScrollView` was tried
//     first and is the wrong tool here: it sizes its content to the viewport, and
//     a rich text `TextArea` inside one never settles (its width change re-wraps
//     the text, which changes its height, which asks for a scroll bar...). The
//     measured result was a few hundred pixels of scrollable range against ~6000
//     of text, so the tail was unreachable.
//   * The scroll bar is a page-level sibling *above* the header rather than the
//     flickable's attached bar. That is what lets the floating bar obey "margin
//     equals corner radius" without ever covering the bar: nothing inside the
//     flickable can be raised above a sibling.
//   * The title is content and scrolls away; the actions are not (see
//     `PageHeader`), so the row below only reserves their room.
Item {
    id: page

    // Follow the tail unless the reader has scrolled away. Entries arrive from
    // the app and from Qt, and a log that does not show its newest line is
    // useless — but yanking the view while someone reads older lines is worse.
    property bool followTail: true
    // Whether the view has been put at the tail yet. Until it has, contentY means
    // "not laid out", not "the reader scrolled up".
    property bool placed: false

    function scrollToTail() {
        const tail = logScroll.contentHeight - logScroll.height
        if (tail <= 0)          // nothing to scroll yet: try again when it grows
            return
        logScroll.contentY = tail
        page.placed = true
    }

    // Opening the page has to land on the newest entry, and the rich text lays
    // out over more than one frame — so this runs on completion and again as the
    // content height settles, rather than only when an entry arrives.
    Component.onCompleted: Qt.callLater(page.scrollToTail)

    Connections {
        target: logScroll

        function onContentYChanged() {
            if (!page.placed)
                return
            page.followTail = logScroll.contentY >= logScroll.contentHeight - logScroll.height - 8
        }

        function onContentHeightChanged() {
            if (!page.placed || page.followTail)
                Qt.callLater(page.scrollToTail)
        }
    }

    Connections {
        target: logVM

        function onRichLogsChanged() {
            if (page.followTail)
                Qt.callLater(page.scrollToTail)
        }
    }

    Flickable {
        id: logScroll

        anchors.fill: parent
        clip: true
        contentWidth: width
        // The content plus the same 24px again at the bottom, so the newest line
        // can be scrolled clear of the edge.
        contentHeight: content.height + frame.inset * 2

        // RinUI's own bar, attached to this flickable — the same bar RinUI's
        // ListView attaches for the History page.
        Rin.ScrollBar.vertical: Rin.ScrollBar {}



        Item {
            id: content

            x: frame.inset
            y: frame.inset
            width: logScroll.width - frame.inset * 2
            height: headerRow.height + logText.height

            PageHeaderRow {
                id: headerRow

                width: parent.width
                reservedWidth: frame.actionsWidth
                reservedHeight: frame.headerHeight
                //: Air between the reserve and the log itself.
                bottomGap: 12
                }

            Text {
                id: logText

                y: headerRow.height
                width: parent.width
                // The markup is ours (python/viewmodel/log_viewmodel.py), and the
                // message text inside it is escaped there — so the `<` and `&` of
                // an expression can never be read as markup.
                textFormat: Text.RichText
                wrapMode: Text.Wrap
                text: logVM.richLogs
                color: Theme.currentTheme.colors.textColor
                // Log lines are expressions and results, so they wear the code font.
                font: settingsVM.codeFont
            }
        }
    }

    // The frame: title, actions, floating bar, window-edge scroll bar. The body
    // above owns everything that scrolls.
    PageScaffold {
        id: frame

        title: qsTr("Log")
        flickable: logScroll
        inlineRow: headerRow

        // A `CommandBar`, not a hand-written row: the two actions must survive a
        // narrow window, and the bar folds whichever does not fit into its menu.
        CommandBar {
            // The plain rendering, for the clipboard: the page shows markup.
            Action {
                text: qsTr("Copy log")
                icon.name: "ic_fluent_copy_20_regular"
                enabled: logVM.formattedLogs !== ""
                onTriggered: vm.copyText(logVM.formattedLogs)
            }

            Action {
                text: qsTr("Clear log")
                icon.name: "ic_fluent_delete_20_regular"
                enabled: logVM.formattedLogs !== ""
                onTriggered: logVM.clear()
            }
        }
    }

    Text {
        anchors.centerIn: parent
        visible: logVM.formattedLogs === ""
        typography: Typography.Body
        color: Theme.currentTheme.colors.textSecondaryColor
        text: qsTr("Log is empty.")
    }
}
