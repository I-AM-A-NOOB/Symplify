import QtQuick
import QtQuick.Layouts
import RinUI

//: The Settings page's **Calculation** section: the parser conveniences the
//: calculator may accept. These are syntax switches, not expression features:
//: turning one off changes what the same text means, and the History page keeps
//: the original text so it can be edited and resent.
//:
//: They are one list rather than six cards: each switch is an independent
//: parser transformation, and the expanded body reads like the code-theme
//: list next door. The checkboxes deliberately do not exclude one another.
SettingsSection {
    label: qsTr("Calculation")

    function enabledTransformations() {
        let count = 0
        if (settingsVM.implicitMultiplication) ++count
        if (settingsVM.convertXor) ++count
        if (settingsVM.implicitApplication) ++count
        if (settingsVM.functionExponentiation) ++count
        if (settingsVM.splitSymbols) ++count
        if (settingsVM.factorialNotation) ++count
        return count
    }

    ExpanderRow {
        id: transformationsRow

        objectName: "parserTransformations"
        Layout.fillWidth: true
        title: qsTr("Transformations")
        description: qsTr("How the parser reads conveniences such as 2x or x^2. Changing one changes what the same text means.")
        icon.name: "ic_fluent_math_format_linear_20_regular"

        content: Text {
            text: qsTr("%1 of %2 enabled")
                .arg(enabledTransformations())
                .arg(6)
            color: Theme.currentTheme.colors.textSecondaryColor
        }

        Loader {
            Layout.fillWidth: true
            active: transformationsRow.expanded
            onLoaded: item.width = width
            sourceComponent: Component {
                CheckboxSettingGroup {
                    CheckboxSettingRow {
                        label: qsTr("Implicit multiplication")
                        hint: qsTr("Read 2x as 2*x. Off requires an explicit *.")
                        checked: settingsVM.implicitMultiplication
                        onToggled: settingsVM.implicitMultiplication =
                            !settingsVM.implicitMultiplication
                    }

                    CheckboxSettingRow {
                        label: qsTr("Caret as power")
                        hint: qsTr("Read x^2 as x**2. Off uses **; a bare ^ is rejected.")
                        checked: settingsVM.convertXor
                        onToggled: settingsVM.convertXor = !settingsVM.convertXor
                    }

                    CheckboxSettingRow {
                        label: qsTr("Implicit function application")
                        hint: qsTr("Read sin x as sin(x). Off requires parentheses.")
                        checked: settingsVM.implicitApplication
                        onToggled: settingsVM.implicitApplication =
                            !settingsVM.implicitApplication
                    }

                    CheckboxSettingRow {
                        label: qsTr("Function exponentiation")
                        hint: qsTr("Read sin^2(x) as sin(x)**2.")
                        checked: settingsVM.functionExponentiation
                        onToggled: settingsVM.functionExponentiation =
                            !settingsVM.functionExponentiation
                    }

                    CheckboxSettingRow {
                        label: qsTr("Split multi-letter symbols")
                        hint: qsTr("Read xy as x*y. This can shadow a variable named xy; off by default.")
                        checked: settingsVM.splitSymbols
                        onToggled: settingsVM.splitSymbols = !settingsVM.splitSymbols
                    }

                    CheckboxSettingRow {
                        label: qsTr("Factorial notation")
                        hint: qsTr("Read x! as factorial(x).")
                        checked: settingsVM.factorialNotation
                        onToggled: settingsVM.factorialNotation =
                            !settingsVM.factorialNotation
                    }
                }
            }
        }
    }
}
