import QtQuick 2.15
import QtQuick.Controls 2.15
import RinUI

FluentWindow {
    id: window

    visible: true
    title: qsTr("Symplify")
    width: 1180
    height: 760
    minimumWidth: 860
    minimumHeight: 560

    navigationView.navExpandWidth: 230

    // Top section stays empty (RinUI caps it at 20% of the nav height,
    // which squeezed items into a scrollbar on short windows):
    // main items live in the uncapped middle section, Log/Settings pin to
    // the bottom section.
    navigationItems: [
        {
            title: qsTr("Calculator"),
            page: Qt.resolvedUrl("pages/CalculatorPage.qml"),
            icon: "ic_fluent_math_formula_20_regular"
        },
        {
            title: qsTr("Variables"),
            page: Qt.resolvedUrl("pages/VariablesPage.qml"),
            icon: "ic_fluent_braces_variable_20_regular"
        },
        {
            title: qsTr("History"),
            page: Qt.resolvedUrl("pages/HistoryPage.qml"),
            icon: "ic_fluent_history_20_regular"
        },
        {
            title: qsTr("Log"),
            page: Qt.resolvedUrl("pages/LogPage.qml"),
            icon: "ic_fluent_info_20_regular",
            position: Position.Bottom
        },
        {
            title: qsTr("Settings"),
            page: Qt.resolvedUrl("pages/SettingsPage.qml"),
            icon: "ic_fluent_settings_20_regular",
            position: Position.Bottom
        }
    ]

    Shortcut {
        sequences: ["Ctrl+Tab"]
        onActivated: vm.focusNext()
    }
    Shortcut {
        sequences: ["Ctrl+Shift+Tab"]
        onActivated: vm.focusPrev()
    }

    // History "send to input": restore an entry in the calculator and
    // navigate back to it. Qt.resolvedUrl is required -- safePush's
    // createComponent resolves relative paths against NavigationView.qml.
    Connections {
        target: vm

        function onSendToCode(expression) {
            calcVM.inputText = expression
            calcVM.inputMode = 0
            calcVM.clear_result()
            navigationView.push(Qt.resolvedUrl("pages/CalculatorPage.qml"))
        }

        function onSendToAssign(name, op, expr) {
            calcVM.assignName = name
            calcVM.assignOperator = op
            calcVM.assignValue = expr
            calcVM.inputMode = 1
            calcVM.clear_result()
            navigationView.push(Qt.resolvedUrl("pages/CalculatorPage.qml"))
        }
    }
}
