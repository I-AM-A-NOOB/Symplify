import QtQuick
import QtQuick.Layouts
import RinUI

//: The Settings page's **Language** section.
//:
//: The concrete list is compiled translations discovered beside the app
//: (`i18n/symplify_<code>.qm`); the source language is English. "System default"
//: follows the OS locale and falls back to English when no matching catalogue
//: exists.
SettingsSection {
    label: qsTr("Language")

    SettingCard {
        Layout.fillWidth: true
        title: qsTr("Display language")
        description: qsTr("System default follows the operating system. Changes apply immediately.")
        icon.name: "ic_fluent_translate_20_regular"

        ComboBox {
            id: languageCombo

            Layout.preferredWidth: 210

            //: `settingsVM.languages` contains compiled translations only. The
            //: system row is prepended here so its label is itself translatable,
            //: and it names the language the OS resolves to: "System default"
            //: alone leaves the reader guessing what picking it will do.
            //:
            //: A `ListModel`, not a JavaScript array: the label contains `qsTr`,
            //: so an array bound to it is rebuilt by `engine.retranslate()`, and
            //: assigning a new model resets `currentIndex` to 0 — the picker
            //: snapped back to "System default" after every switch, until the
            //: page was built again. Updating the row in place keeps the
            //: selection.
            ListModel {
                id: languageModel
            }

            function systemRowName() {
                return qsTr("System default")
                    + " (" + settingsVM.systemLanguageName + ")"
            }

            function refreshModel() {
                const rows = [{code: "system", name: systemRowName()}]
                    .concat(settingsVM.languages)
                while (languageModel.count > rows.length)
                    languageModel.remove(languageModel.count - 1)
                for (let i = 0; i < rows.length; ++i) {
                    if (i < languageModel.count) {
                        languageModel.setProperty(i, "code", rows[i].code)
                        languageModel.setProperty(i, "name", rows[i].name)
                    } else {
                        languageModel.append(rows[i])
                    }
                }
            }

            function syncLanguage() {
                const code = settingsVM.language
                for (let i = 0; i < languageModel.count; ++i) {
                    if (languageModel.get(i).code === code) {
                        currentIndex = i
                        return
                    }
                }
                currentIndex = 0
            }

            model: languageModel
            textRole: "name"

            Component.onCompleted: {
                refreshModel()
                syncLanguage()
            }
            onActivated: settingsVM.language = languageModel.get(currentIndex).code

            Connections {
                target: settingsVM
                function onLanguageChanged() {
                    //: The system row's label is in the new UI language; update
                    //: it in place (a model reset would snap the selection to it).
                    languageModel.setProperty(0, "name", languageCombo.systemRowName())
                    languageCombo.syncLanguage()
                }
            }
        }
    }
}
