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

        Layout.preferredWidth: 190
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
