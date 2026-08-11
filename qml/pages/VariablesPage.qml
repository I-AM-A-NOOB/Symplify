import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Page {
    id: root

    // Row selection is tracked manually in the delegate; the Controls
    // TableView has no working built-in selection in this Qt build.
    property int selectedRow: -1

    function selectedName() {
        if (root.selectedRow < 0)
            return ""
        return variablesModel.nameAt(root.selectedRow)
    }

    function selectedValue() {
        if (root.selectedRow < 0)
            return ""
        return variablesModel.valueAt(root.selectedRow)
    }

    function addVariable() {
        var name = varsVM.generateUniqueName()
        varsVM.addVariable(name, "0")
    }

    function deleteSelected() {
        var name = root.selectedName()
        if (name) {
            varsVM.deleteVariable(name)
            root.selectedRow = -1
        }
    }

    function startEdit(column, name, value) {
        if (column === 0) {
            renameNameField.text = name
            renameDialog.open()
        } else {
            editValueField.text = value
            editDialog.open()
        }
    }

    Connections {
        target: varsVM
        function onWarningOccurred(title, content) {
            warningDialog.title = title
            warningContent.text = content
            warningDialog.open()
        }
    }

    Dialog {
        id: warningDialog
        modal: true
        standardButtons: Dialog.Ok
        contentItem: Label {
            id: warningContent
            width: 300
            wrapMode: Text.Wrap
        }
    }

    Dialog {
        id: editDialog
        title: qsTr("Edit variable value")
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        contentItem: ColumnLayout {
            Label { text: qsTr("New value:") }
            TextField {
                id: editValueField
                Layout.fillWidth: true
            }
        }
        onAccepted: {
            var name = root.selectedName()
            if (name)
                varsVM.updateVariable(name, editValueField.text)
        }
    }

    Dialog {
        id: renameDialog
        title: qsTr("Rename variable")
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        contentItem: ColumnLayout {
            Label { text: qsTr("New name:") }
            TextField {
                id: renameNameField
                Layout.fillWidth: true
            }
        }
        onAccepted: {
            var oldName = root.selectedName()
            var newName = renameNameField.text.trim()
            if (oldName && newName)
                varsVM.renameVariable(oldName, newName)
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        Label {
            text: qsTr("Variables")
            font.pixelSize: 22
            font.bold: true
        }

        // Table header
        RowLayout {
            Layout.fillWidth: true
            spacing: 0
            Label {
                Layout.preferredWidth: 220
                Layout.leftMargin: 8
                text: qsTr("Name")
                font.bold: true
            }
            Label {
                Layout.fillWidth: true
                text: qsTr("Value")
                font.bold: true
            }
        }

        TableView {
            id: table
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: variablesModel
            columnWidthProvider: function(column) {
                if (column === 0)
                    return 220
                return Math.max(100, table.width - 220)
            }
            delegate: Rectangle {
                required property string name
                required property string value
                required property int column
                required property int row
                implicitHeight: 40
                color: root.selectedRow === row ? palette.accent : "transparent"

                // Single tap selects the row; double-tap edits/renames in place.
                TapHandler {
                    onTapped: {
                        root.selectedRow = row
                        if (tapCount === 2)
                            root.startEdit(column, name, value)
                    }
                }

                Label {
                    text: column === 0 ? name : value
                    anchors.left: parent.left
                    anchors.leftMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 16
                    elide: Text.ElideRight
                    color: root.selectedRow === row ? palette.highlightedText : palette.windowText                }
            }
        }

        // Toolbar (replaces CommandBar)
        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 6
            ToolButton {
                text: "\uF109" // FluentSystemIcons: add_20
                font.family: "FluentSystemIcons-Regular"
                font.pixelSize: 16
                ToolTip.visible: hovered
                ToolTip.text: qsTr("Add variable")
                onClicked: root.addVariable()
            }
            ToolButton {
                text: "\uF34C" // FluentSystemIcons: delete_20
                font.family: "FluentSystemIcons-Regular"
                font.pixelSize: 16
                ToolTip.visible: hovered
                ToolTip.text: qsTr("Delete selected variable")
                onClicked: root.deleteSelected()
            }
            ToolButton {
                text: "\uF3DD" // FluentSystemIcons: edit_20
                font.family: "FluentSystemIcons-Regular"
                font.pixelSize: 16
                ToolTip.visible: hovered
                ToolTip.text: qsTr("Edit selected variable")
                onClicked: {
                    var value = root.selectedValue()
                    if (root.selectedRow >= 0) {
                        editValueField.text = value
                        editDialog.open()
                    }
                }
            }
            ToolButton {
                text: "\uF66A" // FluentSystemIcons: rename_24
                font.family: "FluentSystemIcons-Regular"
                font.pixelSize: 16
                ToolTip.visible: hovered
                ToolTip.text: qsTr("Rename selected variable")
                onClicked: {
                    var name = root.selectedName()
                    if (root.selectedRow >= 0) {
                        renameNameField.text = name
                        renameDialog.open()
                    }
                }
            }
        }
    }
}
