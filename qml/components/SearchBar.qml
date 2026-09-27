import QtQuick
import QtQuick.Layouts 2.15
import RinUI

// Search box with a match-mode selector, shared by the Variables and History
// pages. The debounce lives here, in one place: typing re-queries only after a
// pause, while clearing the box (or pressing Esc) re-queries at once, so the
// full list comes back immediately.
RowLayout {
    id: root

    property var modeLabels: []

    signal searchRequested(string text, int mode)

    function apply() {
        debounce.stop()
        root.searchRequested(searchField.text, modeCombo.currentIndex)
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

    ComboBox {
        id: modeCombo

        Layout.preferredWidth: 118
        Layout.alignment: Qt.AlignVCenter
        model: root.modeLabels

        onActivated: root.apply()     // a mode switch applies immediately
    }

    Timer {
        id: debounce

        interval: 200
        onTriggered: root.apply()
    }
}
