import QtQuick 2.15
import QtQuick.Layouts 2.15
import RinUI

Item {
    id: page

    function themeIndex() {
        const i = ["Auto", "Light", "Dark"].indexOf(Theme.getTheme())
        return i >= 0 ? i : 0
    }

    function backdropIndex() {
        const values = ["mica", "acrylic", "tabbed", "none"]
        const i = values.indexOf(Theme.getBackdropEffect())
        return i >= 0 ? i : 3
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 14

        Text {
            Layout.fillWidth: true
            typography: Typography.Title
            text: qsTr("Settings")
        }

        Text {
            Layout.fillWidth: true
            typography: Typography.Subtitle
            text: qsTr("Appearance")
        }

        Frame {
            Layout.fillWidth: true

            ColumnLayout {
                width: parent.width
                spacing: 14

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Text {
                        typography: Typography.Body
                        text: qsTr("Theme mode")
                    }
                    Item { Layout.fillWidth: true }
                    ComboBox {
                        id: themeCombo

                        model: ["Auto", "Light", "Dark"]
                        currentIndex: page.themeIndex()
                        onActivated: (index) => Theme.setTheme(model[index])
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Text {
                        typography: Typography.Body
                        text: qsTr("Backdrop effect")
                    }
                    Item { Layout.fillWidth: true }
                    ComboBox {
                        id: backdropCombo

                        visible: Qt.platform.os === "windows"
                        enabled: visible
                        model: ["Mica", "Acrylic", "Tabbed", "None"]
                        currentIndex: page.backdropIndex()
                        onActivated: (index) => {
                            const values = ["mica", "acrylic", "tabbed", "none"]
                            Theme.setBackdropEffect(values[index])
                        }
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            typography: Typography.Subtitle
            text: qsTr("About")
        }

        Frame {
            Layout.fillWidth: true

            ColumnLayout {
                width: parent.width
                spacing: 8

                Text {
                    typography: Typography.Body
                    text: "Symplify " + appVersion
                }
                Text {
                    typography: Typography.Caption
                    color: Theme.currentTheme.colors.textSecondaryColor
                    text: qsTr("A symbolic calculator built with SymPy, PySide6 and RinUI.")
                }
                Text {
                    typography: Typography.Caption
                    color: Theme.currentTheme.colors.textSecondaryColor
                    text: (typeof qtRuntimeVersionString !== "undefined"
                           ? "Qt " + qtRuntimeVersionString + " · " : "") + "RinUI 0.4.4"
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
}
