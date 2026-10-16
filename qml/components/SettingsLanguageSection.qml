import QtQuick
import QtQuick.Layouts
import RinUI

//: The Settings page's **Language** section: one placeholder row, since English is the
//: only language so far.
ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3

                    Text {
                        typography: Typography.BodyStrong
                        text: qsTr("Language")
                    }

                    SettingCard {
                        Layout.fillWidth: true
                        title: qsTr("Display language")
                        description: qsTr("English is the only language so far.")
                        icon.name: "ic_fluent_translate_20_regular"

                        // Placeholder: one entry, so there is nothing to switch to yet.
                        ComboBox {
                            Layout.preferredWidth: 150
                            enabled: false
                            model: ["English"]
                            currentIndex: 0
                        }
                    }
}
