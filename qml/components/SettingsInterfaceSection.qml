import QtQuick
import QtQuick.Layouts
import RinUI

//: The Settings page's **Interface** section: theme mode, background effect, accent
//: colour (with the two shades of finetuning) and the window's remembered geometry.
//:
//: A section is a component here because that is what a section is: a `ColumnLayout` with
//: a `BodyStrong` subtitle and one card per row (RinUI's gallery layout), starting at
//: `spacing: 3`. What is per-section is the state: the label/value pairs its combos pass
//: their index through, and `applyAccentMode`, the only reason the accent expander opens
//: itself.
ColumnLayout {

        readonly property var backdropLabels: ["Mica", "Acrylic", "Tabbed", "None"]
        readonly property var backdropValues: ["mica", "acrylic", "tabbed", "none"]

        // Order is a contract with SettingsViewModel's accent modes (the ComboBox
        // passes its index straight through).
        readonly property var accentModeLabels: [qsTr("Default"), qsTr("System"), qsTr("Custom")]
        readonly property var accentModeValues: ["default", "system", "custom"]
        readonly property bool customAccent: settingsVM.accentMode === "custom"


        function indexOf(values, value) {
            const i = values.indexOf(value)
            return i >= 0 ? i : 0
        }

        // Switch the accent mode. Picking Custom is the only reason to look inside
        // the expander, so it opens itself -- the picker lives in there.
        function applyAccentMode(index) {
            settingsVM.accentMode = accentModeValues[index]
            if (accentModeValues[index] === "custom")
                accentExpander.expanded = true
        }

                    Layout.fillWidth: true
                    spacing: 3

                    Text {
                        typography: Typography.BodyStrong
                        text: qsTr("Interface")
                    }

                    SettingCard {
                        Layout.fillWidth: true
                        title: qsTr("Theme mode")
                        description: qsTr("Follow the system, or force light or dark.")
                        icon.name: "ic_fluent_dark_theme_20_regular"

                        ComboBox {
                            Layout.preferredWidth: 150
                            model: ["Auto", "Light", "Dark"]
                            currentIndex: indexOf(model, settingsVM.theme)
                            onActivated: (index) => settingsVM.theme = model[index]
                        }
                    }

                    SettingCard {
                        Layout.fillWidth: true
                        title: qsTr("Background effect")
                        description: qsTr("Window material behind the UI (Windows 11).")
                        icon.name: "ic_fluent_square_hint_sparkles_20_regular"
                        visible: Qt.platform.os === "windows"

                        ComboBox {
                            Layout.preferredWidth: 150
                            model: backdropLabels
                            currentIndex: indexOf(backdropValues, settingsVM.backdrop)
                            onActivated: (index) => settingsVM.backdrop = backdropValues[index]
                        }
                    }

                    // The mode decides the accent (RinUI's own colour, the system
                    // palette, or a picked one); the picker below edits the custom
                    // colour and is only live while that mode is selected.
                    ExpanderRow {
                        id: accentExpander

                        Layout.fillWidth: true
                        title: qsTr("Accent colour")
                        description: qsTr("Used by controls and the selected-item accent.")
                        icon.name: "ic_fluent_color_20_regular"

                        content: ComboBox {
                            Layout.preferredWidth: 150
                            model: accentModeLabels
                            currentIndex: indexOf(accentModeValues, settingsVM.accentMode)
                            onActivated: (index) => applyAccentMode(index)
                        }

                        SettingItem {
                            title: qsTr("Colour")
                            description: customAccent
                                ? qsTr("The colour used while the accent is Custom.")
                                : qsTr("Switch the accent to Custom to change this.")
                            showDivider: false

                            RowLayout {
                                spacing: 8

                                // One fixed rounded rectangle, never resizable: with
                                // shading on it is split into three segments, one per
                                // variant in play; with shading off it is a single
                                // field of the colour. Purely a preview — it takes no
                                // input and follows the accent the UI is using, not
                                // the stored custom colour the button beside it edits.
                                // Outer corners take the Fluent control radius (the
                                // inner ones stay square, which is what makes the
                                // segments read as one shape), and the outline is the
                                // accent-style Button's border.
                                Item {
                                    id: accentStrip

                                    Layout.preferredWidth: 84
                                    Layout.preferredHeight: 26

                                    readonly property int segmentCount:
                                        settingsVM.accentPreview.length

                                    Row {
                                        anchors.fill: parent
                                        spacing: 0

                                        Repeater {
                                            model: settingsVM.accentPreview

                                            delegate: Rectangle {
                                                required property int index
                                                required property var modelData

                                                readonly property bool isFirst: index === 0
                                                readonly property bool isLast:
                                                    index === accentStrip.segmentCount - 1
                                                readonly property int corner:
                                                    Theme.currentTheme.appearance.buttonRadius

                                                width: parent.width / accentStrip.segmentCount
                                                height: parent.height
                                                color: modelData
                                                topLeftRadius: isFirst ? corner : 0
                                                bottomLeftRadius: isFirst ? corner : 0
                                                topRightRadius: isLast ? corner : 0
                                                bottomRightRadius: isLast ? corner : 0
                                            }
                                        }
                                    }

                                    Rectangle {
                                        anchors.fill: parent
                                        color: "transparent"
                                        radius: Theme.currentTheme.appearance.buttonRadius
                                        border.width: Theme.currentTheme.appearance.borderWidth
                                        border.color: Theme.currentTheme.colors.controlBorderAccentColor
                                    }
                                }

                                // The picker wears an icon rather than the colour:
                                // RinUI's DropDownColorPicker draws the colour inside
                                // its own button, so in the other accent modes (where
                                // it is disabled) the face would dim and recolour the
                                // very thing being previewed — which the strip above
                                // already shows, always and unmodified. What opens is
                                // still its proper picker flyout.
                                DropDownColorPicker {
                                    id: accentPicker

                                    Layout.preferredWidth: 40
                                    Layout.preferredHeight: 32
                                    // The stock binding reads an id inside the
                                    // contentItem this replaces, so it is set here.
                                    implicitWidth: 40
                                    enabled: customAccent
                                    color: settingsVM.customAccent
                                    onColorChanged: {
                                        if (customAccent
                                                && !Qt.colorEqual(settingsVM.customAccent, color))
                                            settingsVM.customAccent = color
                                    }

                                    contentItem: Icon {
                                        name: "ic_fluent_color_20_regular"
                                        size: 18
                                        color: accentPicker.enabled
                                            ? Theme.currentTheme.colors.textColor
                                            : Theme.currentTheme.colors.textDisabledColor
                                    }
                                }
                            }
                        }

                        // Whether the accent is finetuned per theme at all. It belongs
                        // to the accent, so it lives here rather than as a card of its
                        // own, and it needs no icon.
                        SettingItem {
                            title: qsTr("Shade per theme")
                            description: qsTr("Finetune the accent for light and dark. Off uses each colour exactly as it is.")
                            showDivider: false

                            Switch {
                                checked: settingsVM.accentShading
                                onToggled: settingsVM.accentShading = checked
                            }
                        }

                        // Where that finetuning comes from, when the platform has an
                        // opinion of its own. Hidden off Windows, since the option can
                        // never apply there, and disabled — with the reason spelled
                        // out — unless it would actually take effect.
                        SettingItem {
                            title: qsTr("Use Windows accent finetuning")
                            description: settingsVM.accentOsShadingAvailable
                                ? qsTr("Uses the light and dark accents Windows derives itself, instead of the built-in blend.")
                                : qsTr("Available on Windows only, with the System accent selected and Shade per theme on.")
                            visible: settingsVM.accentOsShadingSupported
                            enabled: settingsVM.accentOsShadingAvailable
                            showDivider: false

                            Switch {
                                checked: settingsVM.accentOsShading
                                onToggled: settingsVM.accentOsShading = checked
                            }
                        }
                    }

                    SettingCard {
                        Layout.fillWidth: true
                        title: qsTr("Remember size and position")
                        description: qsTr("Restore the window geometry on the next launch.")
                        icon.name: "ic_fluent_window_20_regular"

                        Switch {
                            checked: settingsVM.rememberWindow
                            onToggled: settingsVM.rememberWindow = checked
                        }
                    }

                    SettingCard {
                        Layout.fillWidth: true
                        title: qsTr("Reset to default")
                        description: qsTr("Forget the saved geometry and let the system place the window.")
                        icon.name: "ic_fluent_arrow_reset_20_regular"
                        clickable: true
                        onClicked: settingsVM.resetWindow()
                    }
}
