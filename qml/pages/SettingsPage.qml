import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

Page {
    id: root

    ScrollView {
        anchors.fill: parent
        anchors.margins: 12
        clip: true

        ColumnLayout {
            width: parent.width
            spacing: 12

            Label {
                text: qsTr("Settings")
                font.pixelSize: 22
                font.bold: true
            }

            // Appearance group (replaces SettingCardGroup)
            Pane {
                Layout.fillWidth: true
                ColumnLayout {
                    width: parent.width
                    spacing: 12

                    Label {
                        text: qsTr("Appearance")
                        font.pixelSize: 16
                        font.bold: true
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        Label {
                            text: qsTr("Application theme")
                            Layout.fillWidth: true
                        }
                        ComboBox {
                            model: [qsTr("Light"), qsTr("Dark"), qsTr("Use system setting")]
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        Label {
                            text: qsTr("Theme color")
                            Layout.fillWidth: true
                        }
                        RadioButton {
                            text: qsTr("Default color")
                            checked: true
                        }
                        RadioButton {
                            text: qsTr("System color")
                        }
                        RadioButton {
                            text: qsTr("Custom color")
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        Label {
                            text: qsTr("Custom color")
                            Layout.fillWidth: true
                        }
                        Button {
                            text: qsTr("Choose color")
                            onClicked: colorDialog.open()
                        }
                        ColorDialog {
                            id: colorDialog
                            title: qsTr("Choose theme color")
                        }
                    }
                }
            }

            // About group
            Pane {
                Layout.fillWidth: true
                ColumnLayout {
                    width: parent.width
                    spacing: 12

                    Label {
                        text: qsTr("About")
                        font.pixelSize: 16
                        font.bold: true
                    }

                    Label {
                        text: qsTr("© 2026 Symplify. Version 0.1.0")
                        wrapMode: Text.Wrap
                        Layout.fillWidth: true
                    }

                    Button {
                        text: qsTr("Check update")
                        onClicked: { /* placeholder */ }
                    }
                }
            }
        }
    }
}
