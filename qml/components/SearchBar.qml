import QtQuick
import QtQuick.Layouts 2.15
import RinUI

// Search box with a match-mode selector, shared by the Variables and History
// pages. The debounce lives here, in one place: typing re-queries only after a
// pause, while clearing the box (or pressing Esc) re-queries at once, so the
// full list comes back immediately.
//
// The *query* is the filter's, not the box's (see `filter`): the proxy outlives
// the page, so a freshly built box has to show what it is still filtering by.
//
// The mode is chosen from a menu behind a flat icon button rather than from a
// combo box. The labels are long ("Fuzzy", "Expression", "Result"), the choice is
// made about once a session, and a combo box spent a fifth of the toolbar on
// showing it — the toolbar is where the room is scarce (see `CommandBar`).
RowLayout {
    id: root

    //: The match-mode labels, in the order `python/viewmodel/search.py`'s enums hold
    //: them: the menu hands its index straight through, so this list and the enum are
    //: one contract (see "The Variables and History pages bind to search-filtered
    //: proxies" in the guide).
    property var modeLabels: []
    //: The chosen match mode, as an index into `modeLabels`.
    property int mode: 0
    //: The proxy this box drives — `variablesFilter` or `historyFilter`. The query
    //: belongs to the proxy, which survives a page switch (RinUI rebuilds a page on
    //: every navigation), so the box owns the whole round trip: it adopts what the
    //: filter still holds when it is built and writes every query back. A page hands
    //: it this and its labels, and nothing else.
    property var filter: null

    //: True while `adoptFilter` writes the field. Without it that write reads as
    //: typing, and starts a query for what the filter is already showing.
    property bool adopting: false

    //: Show the query the filter still holds. Run on completion, and deliberately
    //: not a binding: a call in a binding creates no dependency of its own, and a
    //: one-way write on every change would fight the caret of whoever is typing
    //: (which is why the box is the one that writes the filter, and not both).
    function adoptFilter() {
        if (!root.filter)
            return
        root.adopting = true
        root.mode = root.filter.searchMode
        searchField.text = root.filter.searchText
        root.adopting = false
    }

    Component.onCompleted: adoptFilter()

    function apply() {
        debounce.stop()
        if (!root.filter)
            return
        root.filter.searchMode = root.mode
        root.filter.searchText = searchField.text
    }

    //: Empty the box, and the query with it — one path, through the empty-text
    //: handler below, so "clear the query" has one spelling.
    function clear() {
        searchField.text = ""
    }

    TextField {
        id: searchField

        //: RinUI's own `TextField` brings a context menu of its own, opened from a
        //: vendored `MouseArea`, and Basic's inherited attached menu sits under it
        //: as well. Both are switched off by the component below, which is the
        //: app's menu (see `CodeContextMenu`), at the pointer.
        CodeContextMenu { editor: searchField }

        //: Named for a harness that has to read what the box shows (the pages'
        //: other probe hooks exist for the same reason).
        objectName: "searchField"
        //: The field is what gives way when the bar runs short — not the whole box:
        //: squeezing this component below what its two children need pushes the mode
        //: selector out over the toolbar's next button. `fillWidth` plus a floor here
        //: is what turns "too narrow" into a slightly smaller field, and the mode
        //: selector keeps the width its labels need. The component's own implicit
        //: minimum (this floor + the selector + the spacing) is its real limit, so a
        //: page must not impose a smaller one of its own.
        Layout.fillWidth: true
        Layout.preferredWidth: 190
        Layout.minimumWidth: 90
        Layout.alignment: Qt.AlignVCenter
        placeholderText: qsTr("Search...")

        onTextChanged: {
            if (root.adopting)
                return                // the filter's own text, not a query
            if (text === "")
                root.apply()          // clearing restores everything at once
            else
                debounce.restart()
        }
        onAccepted: root.apply()

        Keys.onEscapePressed: root.clear()
    }

    ToolButton {
        id: modeButton

        Layout.alignment: Qt.AlignVCenter
        //: No `display`: RinUI's `ToolButton` is a `Button` that draws whatever
        //: `text` it has and never consults that property, and this button has none
        //: — the icon is all there is. (Setting it here only earned a ReferenceError:
        //: `AbstractButton` lives in `QtQuick.Controls`, which this file does not
        //: import, and `RinUI` does not re-export.)
        flat: true
        icon.name: "ic_fluent_filter_20_regular"
        icon.color: Theme.currentTheme.colors.textColor

        //: The button says which mode is in use without spending the room a combo
        //: box needs to say it.
        Tip {
            text: root.modeLabels.length > root.mode
                ? root.modeLabels[root.mode] : ""
        }
        onClicked: modeMenu.popup(modeButton, modeButton.width / 2, modeButton.height)
    }

    Menu {
        id: modeMenu

        Repeater {
            model: root.modeLabels

            delegate: MenuItem {
                //: Both are required: without them the delegate's `modelData` is not
                //: defined at all (a ReferenceError per item, at runtime only).
                required property int index
                required property var modelData

                text: modelData
                checkable: true
                checked: index === root.mode
                onTriggered: {
                    root.mode = index
                    root.apply()          // a mode switch applies immediately
                }
            }
        }
    }

    Timer {
        id: debounce

        interval: 200
        onTriggered: root.apply()
    }
}
