import QtQuick
import QtQuick.Controls 2.15
import QtQuick.Layouts 2.15
import RinUI

// Settings, grouped with RinUI's SettingExpander/SettingCard so a row is a
// title + description + control. Two API details worth remembering: the icon is
// set with `icon.name:` (assigning `icon:` fails — it is a read-only alias), and
// a SettingExpander's bare children are its collapsible content while its
// `content:`/`action:` go to the header's right slot.
//
// Everything here writes through `settingsVM`, which owns the settings file and
// applies changes live -- the page never touches the store or RinUI directly.
Item {
    id: page

    // Accent presets: RinUI's own default first, then a small WinUI-ish palette.
    readonly property var accentLabels:
        [qsTr("Default"), qsTr("Blue"), qsTr("Teal"), qsTr("Green"),
         qsTr("Magenta"), qsTr("Orange"), qsTr("Purple"), qsTr("Red")]
    readonly property var accentValues:
        ["#605ed2", "#0078d4", "#00838f", "#0f7b0f",
         "#c239b3", "#ca5010", "#744da9", "#c42b1c"]

    readonly property var backdropLabels: ["Mica", "Acrylic", "Tabbed", "None"]
    readonly property var backdropValues: ["mica", "acrylic", "tabbed", "none"]
    readonly property var latexSizes: [16, 20, 24, 28, 32, 40]

    function indexOf(values, value) {
        const i = values.indexOf(value)
        return i >= 0 ? i : 0
    }

    // The page is taller than a short window, so it scrolls. Nothing here has
    // to survive navigation: RinUI recreates the page anyway and every value
    // comes from the settings viewmodel.
    Flickable {
        id: scroll

        anchors.fill: parent
        anchors.margins: 24
        clip: true
        contentWidth: width
        contentHeight: settingsColumn.implicitHeight
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        ColumnLayout {
            id: settingsColumn

            width: scroll.width - 48
            y: 24
            spacing: 14

            Text {
                typography: Typography.Title
                text: qsTr("Settings")
            }

            // ---- Appearance ----
            SettingExpander {
                Layout.fillWidth: true
                title: qsTr("Appearance")
                description: qsTr("Theme mode, backdrop and accent colour.")
                icon.name: "ic_fluent_paint_brush_20_regular"
                expanded: true

                SettingItem {
                    title: qsTr("Theme mode")
                    description: qsTr("Follow the system, or force light or dark.")

                    ComboBox {
                        Layout.preferredWidth: 150
                        model: ["Auto", "Light", "Dark"]
                        currentIndex: page.indexOf(model, settingsVM.theme)
                        onActivated: (index) => settingsVM.theme = model[index]
                    }
                }

                SettingItem {
                    title: qsTr("Backdrop effect")
                    description: qsTr("Window material behind the UI (Windows 11).")
                    visible: Qt.platform.os === "windows"

                    ComboBox {
                        Layout.preferredWidth: 150
                        model: page.backdropLabels
                        currentIndex: page.indexOf(page.backdropValues, settingsVM.backdrop)
                        onActivated: (index) => settingsVM.backdrop = page.backdropValues[index]
                    }
                }

                SettingItem {
                    title: qsTr("Accent colour")
                    description: qsTr("Used by controls and the selected-item accent.")
                    showDivider: false

                    ComboBox {
                        Layout.preferredWidth: 150
                        model: page.accentLabels
                        currentIndex: page.indexOf(page.accentValues, settingsVM.accent)
                        onActivated: (index) => settingsVM.accent = page.accentValues[index]
                    }
                }
            }

            // ---- Rendering ----
            SettingExpander {
                Layout.fillWidth: true
                title: qsTr("Rendering")
                description: qsTr("How results are typeset.")
                icon.name: "ic_fluent_math_formula_20_regular"

                SettingItem {
                    title: qsTr("Result size")
                    description: qsTr("Font size of the rendered result, in points.")
                    showDivider: false

                    ComboBox {
                        Layout.preferredWidth: 150
                        model: page.latexSizes
                        currentIndex: page.indexOf(model, settingsVM.latexSize)
                        onActivated: (index) => settingsVM.latexSize = page.latexSizes[index]
                    }
                }
            }

            // ---- Window ----
            SettingExpander {
                Layout.fillWidth: true
                title: qsTr("Window")
                description: qsTr("Remember how the window was left.")
                icon.name: "ic_fluent_window_20_regular"

                SettingItem {
                    title: qsTr("Remember size and position")
                    description: qsTr("Restore the window geometry on the next launch.")

                    Switch {
                        checked: settingsVM.rememberWindow
                        onToggled: settingsVM.rememberWindow = checked
                    }
                }

                SettingItem {
                    title: qsTr("Forget saved geometry")
                    description: qsTr("Use the default size and let the system place the window.")
                    showDivider: false
                    clickable: true
                    onClicked: settingsVM.resetWindow()
                }
            }

            // ---- Config file ----
            SettingCard {
                Layout.fillWidth: true
                title: qsTr("Settings file")
                description: settingsVM.configMode + " · " + settingsVM.configPath
                icon.name: "ic_fluent_document_20_regular"
                clickable: true
                onClicked: settingsVM.openConfigFolder()
            }

            // Only visible when a write actually failed (read-only install, full disk).
            SettingCard {
                Layout.fillWidth: true
                visible: settingsVM.warning !== ""
                title: qsTr("Settings are not being saved")
                description: settingsVM.warning
                icon.name: "ic_fluent_warning_20_regular"
            }

            SettingCard {
                Layout.fillWidth: true
                title: qsTr("Restore defaults")
                description: qsTr("Reset every setting and apply it immediately.")
                icon.name: "ic_fluent_arrow_reset_20_regular"
                clickable: true
                onClicked: resetDialog.open()
            }

            // ---- About ----
            Text {
                Layout.fillWidth: true
                Layout.topMargin: 6
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
                        text: "Qt " + qtVersion + " · RinUI " + rinuiVersion
                    }
                }
            }

            Item { Layout.fillHeight: true }
        }
    }

    // RinUI's accent colour needs more than the persisted value: its QML
    // Theme.setThemeColor also sets Utils.primaryColor, which is what actually
    // re-colours the controls. The viewmodel stores it, this applies it.
    Connections {
        target: settingsVM

        function onAccentChanged() {
            Theme.setThemeColor(settingsVM.accent)
        }
    }

    Dialog {
        id: resetDialog

        title: qsTr("Restore defaults?")
        standardButtons: Dialog.Ok | Dialog.Cancel

        Text {
            Layout.fillWidth: true
            width: 320
            wrapMode: Text.WordWrap
            typography: Typography.Body
            color: Theme.currentTheme.colors.textColor
            text: qsTr("Every setting, including the remembered window geometry, goes back to its default. This cannot be undone.")
        }

        onAccepted: settingsVM.resetToDefaults()
    }
}
