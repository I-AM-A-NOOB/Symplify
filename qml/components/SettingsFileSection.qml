import QtQuick
import QtQuick.Layouts
import RinUI

//: The Settings page's **Settings file** section: where the file is, what mode the store
//: resolved, the warning a read-only location produces, and the reset-everything row
//: with the dialog that confirms it.
ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3

                    Text {
                        typography: Typography.BodyStrong
                        text: qsTr("Settings file")
                    }

                    SettingCard {
                        Layout.fillWidth: true
                        title: qsTr("Open directory")
                        description: settingsVM.configMode + " · " + settingsVM.configPath
                        icon.name: "ic_fluent_folder_20_regular"
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
                        title: qsTr("Reset to default")
                        description: qsTr("Reset every setting and apply it immediately.")
                        icon.name: "ic_fluent_arrow_reset_20_regular"
                        clickable: true
                        onClicked: resetDialog.open()
                    }

    //: The reset-everything row's confirmation, with the row that opens it.
    MessageDialog {
        id: resetDialog

        title: qsTr("Restore defaults?")
        body: qsTr("Every setting, including the remembered window geometry, goes back to its default. This cannot be undone.")
        //: The one dialog here that asks rather than tells.
        standardButtons: Dialog.Ok | Dialog.Cancel

        onAccepted: settingsVM.resetToDefaults()
    }
}
