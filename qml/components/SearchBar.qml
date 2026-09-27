import QtQuick
import QtQuick.Layouts 2.15
import RinUI

// Search box with a match-mode selector, shared by the Variables and History
// pages. The debounce lives here, in one place: typing re-queries only after a
// pause, while clearing the box (or pressing Esc) re-queries at once, so the
// full list comes back immediately.
//
// The mode is chosen from a menu behind a flat icon button rather than from a
// combo box. The labels are long ("Fuzzy", "Expression", "Result"), the choice is
// made about once a session, and a combo box spent a fifth of the toolbar on
// showing it — the toolbar is where the room is scarce (see `CommandBar`).
RowLayout {
    id: root

    property var modeLabels: []
    //: The chosen match mode, as an index into `modeLabels`.
    property int mode: 0

    signal searchRequested(string text, int mode)

    function apply() {
        debounce.stop()
        root.searchRequested(searchField.text, root.mode)
    }

    function clear() {
        searchField.text = ""
        apply()
    }

    TextField {
        id: searchField

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
        ToolTip {
            delay: 500
            visible: parent.hovered
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
