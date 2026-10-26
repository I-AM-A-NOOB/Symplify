import QtQuick
import QtQuick.Layouts
import RinUI

//: The Settings page's **Language** section.
//:
//: The concrete list is compiled translations discovered beside the app
//: (`i18n/symplify_<code>.qm`); the source language is English. "System default"
//: follows the OS locale and falls back to English when no matching catalogue
//: exists.
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
        description: qsTr("System default follows the operating system. Changes apply immediately.")
        icon.name: "ic_fluent_translate_20_regular"

        ComboBox {
            id: languageCombo

            Layout.preferredWidth: 210

            //: `settingsVM.languages` contains compiled translations only. The
            //: system row is prepended here so its label is itself translatable.
            model: {
                const system = [{code: "system", name: qsTr("System default")}]
                return system.concat(settingsVM.languages)
            }
            textRole: "name"

            function syncLanguage() {
                const code = settingsVM.language
                for (let i = 0; i < model.length; ++i) {
                    if (model[i].code === code) {
                        currentIndex = i
                        return
                    }
                }
                currentIndex = 0
            }

            Component.onCompleted: syncLanguage()
            onActivated: settingsVM.language = model[currentIndex].code

            Connections {
                target: settingsVM
                function onLanguageChanged() {
                    languageCombo.syncLanguage()
                }
            }
        }
    }
}
