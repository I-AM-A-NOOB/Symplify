import QtQuick
import QtQuick.Layouts
import RinUI

//: The Settings page's **About** section: the app, Qt and RinUI versions (all context
//: properties) and the licence.
ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3

                    Text {
                        typography: Typography.BodyStrong
                        text: qsTr("About")
                    }

                    ExpanderRow {
                        Layout.fillWidth: true
                        title: qsTr("About Symplify")
                        description: qsTr("A symbolic calculator built with SymPy, PySide6 and RinUI.")
                        icon.name: "ic_fluent_info_20_regular"

                        SettingItem {
                            title: qsTr("Application")
                            Text {
                                typography: Typography.Body
                                text: "Symplify " + appVersion
                            }
                        }

                        SettingItem {
                            title: "Qt"
                            Text {
                                typography: Typography.Body
                                text: qtVersion
                            }
                        }

                        SettingItem {
                            title: "RinUI"
                            Text {
                                typography: Typography.Body
                                text: rinuiVersion
                            }
                        }

                        SettingItem {
                            title: qsTr("License")
                            showDivider: false
                            Text {
                                typography: Typography.Body
                                text: qsTr("GPLv3")
                            }
                        }
                    }
}
