import QtQuick 2.15
import QtQuick.Controls 2.15
import RinUI

FluentWindow {
    id: window

    visible: true
    title: qsTr("Symplify")
    // Size comes from the settings, read once at creation: assigning the size
    // later (from the viewmodel) and then maximizing leaves the window drawn at
    // the old size with a white border around it on Windows. Setting it here
    // means there is no resize at all -- the window is simply created correct.
    width: settingsVM.startupWidth
    height: settingsVM.startupHeight
    minimumWidth: 860
    minimumHeight: 560

    navigationView.navExpandWidth: 230

    // Settings own the window geometry (settingsVM remembers it when enabled).
    // Called before the window is shown, so the restore is invisible.
    //
    // The accent lives here too, and this is its only owner: applying it needs
    // to happen at startup, whenever the setting changes, and again after every
    // theme switch — RinUI rebuilds the theme object on a switch, which restores
    // the binding below, so the exact value has to be re-asserted each time. The
    // window outlives the pages, so none of that can live on a page.
    Component.onCompleted: {
        settingsVM.attachWindow(window)
        applyAccent()
    }

    // RinUI's accent handling, and why this is not just a call to Theme:
    //
    //   * RinUI's Python `set_theme_color` only persists the value; what
    //     re-colours the controls is `Utils.primaryColor`, which the QML
    //     `Theme.setThemeColor` sets as well.
    //   * RinUI then derives the theme's `primaryColor` from it, with its own
    //     dark-mode adjustment. That adjustment is a scale on the HSV value and
    //     desaturates hard, so the accent is resolved here instead (see
    //     `SettingsViewModel.accentForScheme`): `system` is the OS colour exactly
    //     as the OS tuned it for this scheme, and `default`/`custom` take the
    //     WinUI-style lightening step for dark themes.
    //   * Assigning the property replaces RinUI's binding. That is fine because
    //     this is now the binding's only owner and every theme change is
    //     followed by a re-apply below.
    function applyAccent() {
        Theme.setThemeColor(settingsVM.accent)
        Theme.currentTheme.colors.primaryColor =
            settingsVM.accentForScheme(Theme.currentTheme.isDark)
    }

    Connections {
        target: settingsVM

        function onAccentChanged() {
            applyAccent()
        }
    }

    // A theme switch rebuilds the theme object, so the accent has to be
    // re-applied to the new one (this also covers the OS scheme changing while
    // the theme follows it).
    Connections {
        target: Theme

        function onCurrentThemeChanged() {
            applyAccent()
        }
    }

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
