import QtQuick
import QtQuick.Layouts
import RinUI

//: The Variables page's details panel — the selected variable as one LaTeX line (or,
//: when there is nothing to typeset, the raw entry), the two fields that make it, and
//: the row's own actions. Fixed rather than scrolled: the table narrows beside it, so
//: both stay where the reader left them.
//:
//: It is the page's (`host`) because everything it shows is the page's state: which
//: row is selected, the definition read through `dataRevision`, the two fields'
//: read-back and write-through, and the two row actions. `host` is `required` so a
//: caller cannot forget it.
//:
//: Its width *is* the toggle (`host.sidebarOpen`), and it animates — which is why it
//: calls `host.refreshTableLayout()` when the animation stops (see that function).
Rectangle {
    id: details

    //: The page that owns this panel (see above).
    required property Item host

    //: Load the panel's fields from the selected row. Assignments, not bindings:
    //: the user types in them, and a binding would fight the typing. The page calls
    //: this whenever the selection or the model changes (`host.dataRevision`).
    function syncDetails() {
        if (host.selectedRow < 0) {
            nameField.text = ""
            valueField.text = ""
            return
        }
        nameField.text = variablesFilter.cellAt(host.selectedRow, 0)
        valueField.text = variablesFilter.cellAt(host.selectedRow, 1)
    }

    //: Write both fields back, through the same door the table's cell editors use —
    //: the proxy forwards to the source, which renames (column 0) or re-parses
    //: (column 1) — and only what changed, so an untouched field is not re-parsed.
    function applyDetails() {
        if (host.selectedRow < 0)
            return
        const row = host.selectedRow
        if (nameField.text !== variablesFilter.cellAt(row, 0))
            variablesFilter.setData(variablesFilter.modelIndex(row, 0), nameField.text, 0)
        if (valueField.text !== variablesFilter.cellAt(row, 1))
            variablesFilter.setData(variablesFilter.modelIndex(row, 1), valueField.text, 0)
    }

    anchors.top: parent.top
    anchors.bottom: parent.bottom
    anchors.right: parent.right
    //: The width *is* the toggle, and `visible` follows it — a collapsed panel
    //: that stayed visible would still take its clicks.
    width: host.sidebarOpen ? host.panelWidth : 0
    visible: width > 0
    color: Theme.currentTheme.colors.cardColor

    Behavior on width {
        NumberAnimation {
            duration: Utils.animationSpeed
            easing.type: Easing.OutQuint

            //: The table's columns are computed from its own width, and the
            //: provider runs whenever that changes — which, during this animation,
            //: is every frame. The frame that happens to run last is not
            //: necessarily the one at the final width, so the columns could end up
            //: sized for an intermediate one: `contentWidth` a hair over `width`,
            //: and a horizontal scroll bar over content that all fits (measured
            //: intermittently, same widths, open/close/open). One relayout when the
            //: animation stops fixes it at the only moment that matters.
            onRunningChanged: if (!running) host.refreshTableLayout()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        Item { Layout.fillHeight: true }

        //: `MathStrip`, not a bare `LatexImage`: it is the one place a rendered
        //: formula is laid out (padding, the room the overlay bar needs, the
        //: image at its natural size), and a long definition can be scrolled
        //: sideways in the panel instead of being clipped by it. Hand-rolling the
        //: image here is how the panel's artwork drifted in size from every other
        //: surface — same LaTeX, different frame.
        MathStrip {
            id: definitionImage

            Layout.fillWidth: true
            visible: host.selectedRow >= 0 && host.definition.url !== ""
            source: host.definition.url
            naturalWidth: host.definition.width
            naturalHeight: host.definition.height
        }
        Text {
            Layout.fillWidth: true
            visible: !definitionImage.visible
            text: host.definitionText
            wrapMode: Text.WordWrap
            font: settingsVM.codeFont
            color: host.selectedRow < 0
                ? Theme.currentTheme.colors.textSecondaryColor
                : Theme.currentTheme.colors.systemCriticalColor
        }

        CodeField {
            id: nameField

            Layout.fillWidth: true
            enabled: host.selectedRow >= 0
            placeholderText: qsTr("name")
            onAccepted: applyDetails()
        }
        //: Shaped exactly like the Calculator's Assign value box — the shared
        //: `CodeArea`, wrapping, its own height — rather than a forced 40px: a
        //: fixed height fights the content as soon as the expression wraps, and the
        //: panel is narrower than any calculator row.
        CodeArea {
            id: valueField

            Layout.fillWidth: true
            Layout.minimumWidth: 80
            Layout.alignment: Qt.AlignVCenter
            enabled: host.selectedRow >= 0
            wrapMode: TextEdit.Wrap
            placeholderText: qsTr("expression")
            // Enter applies and never inserts a newline, as everywhere else.
            Keys.onPressed: (event) => {
                if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                    event.accepted = true
                    applyDetails()
                }
            }
        }

        //: The panel's whole vocabulary, as two plain buttons with their words on
        //: them: the sidebar is narrow, there are only two, and a row of icons made
        //: them read as a toolbar of unrelated actions. Delete is destructive and
        //: says so in its label as well as its icon.
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 6

            Button {
                Layout.fillWidth: true
                flat: true
                text: qsTr("Duplicate")
                icon.name: "ic_fluent_copy_20_regular"
                enabled: host.selectedRow >= 0
                onClicked: host.duplicateVariable()
            }
            Button {
                Layout.fillWidth: true
                flat: true
                text: qsTr("Delete")
                icon.name: "ic_fluent_delete_20_regular"
                enabled: host.selectedRow >= 0
                onClicked: host.deleteVariable()
            }
        }

        Item { Layout.fillHeight: true }
    }
}
