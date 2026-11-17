import QtQuick
import QtQuick.Layouts
import RinUI

//: The Settings page's **Calculation** section: the parser conveniences the
//: calculator may accept. These are syntax switches, not expression features:
//: turning one off changes what the same text means, and the History page keeps
//: the original text so it can be edited and resent.
SettingsSection {
    label: qsTr("Calculation")

    SettingCard {
        Layout.fillWidth: true
        title: qsTr("Implicit multiplication")
        description: qsTr("Read 2x as 2*x. Off requires an explicit *.")
        icon.name: "ic_fluent_math_formula_20_regular"

        Switch {
            checked: settingsVM.implicitMultiplication
            onToggled: settingsVM.implicitMultiplication = checked
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: qsTr("Caret as power")
        description: qsTr("Read x^2 as x**2. Off uses **; a bare ^ is rejected.")
        icon.name: "ic_fluent_math_formula_20_regular"

        Switch {
            checked: settingsVM.convertXor
            onToggled: settingsVM.convertXor = checked
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: qsTr("Implicit function application")
        description: qsTr("Read sin x as sin(x). Off requires parentheses.")
        icon.name: "ic_fluent_math_formula_20_regular"

        Switch {
            checked: settingsVM.implicitApplication
            onToggled: settingsVM.implicitApplication = checked
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: qsTr("Function exponentiation")
        description: qsTr("Read sin^2(x) as sin(x)**2.")
        icon.name: "ic_fluent_math_formula_20_regular"

        Switch {
            checked: settingsVM.functionExponentiation
            onToggled: settingsVM.functionExponentiation = checked
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: qsTr("Split multi-letter symbols")
        description: qsTr("Read xy as x*y. This can shadow a variable named xy; off by default.")
        icon.name: "ic_fluent_math_formula_20_regular"

        Switch {
            checked: settingsVM.splitSymbols
            onToggled: settingsVM.splitSymbols = checked
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: qsTr("Factorial notation")
        description: qsTr("Read x! as factorial(x).")
        icon.name: "ic_fluent_math_formula_20_regular"

        Switch {
            checked: settingsVM.factorialNotation
            onToggled: settingsVM.factorialNotation = checked
        }
    }
}
