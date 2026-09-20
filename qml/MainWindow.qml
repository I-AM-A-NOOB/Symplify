import QtQuick 2.15
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

    // RinUI's title bar starts a native drag on press, but the same handler's
    // onPositionChanged *also* moves the window by hand -- guarded by a platform
    // test that returns off Windows rather than on it, so on Windows the manual
    // move runs as well. Once the drag has un-maximized the window the handler's
    // local coordinates no longer line up (they shift by half the width
    // difference) and its `window.x + delta` teleports the window: measured from
    // (395, 277) to (0, 300) for a window dragged out of fullscreen. The guard
    // reads isMaximized, which RinUI never defines (its other disjunct,
    // isFullScreen, is undefined too), so it only ever saw `visibility`.
    //
    // dragInProgress is raised by the window_drag manager for the whole gesture,
    // the queued mouse events included -- so the manual move is skipped and the
    // window lands where the system put it, as it does for any other app.
    property bool dragInProgress: false
    property bool isMaximized: dragInProgress || visibility === Window.Maximized

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
        applyLogColors()
        applyLatexColors()
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

    // The log colours its levels with the theme's status roles, and the theme
    // object lives on this side — so the values are pushed into the viewmodel,
    // which builds the log's rich text. `systemAttentionColor` is the accent, so
    // the ramp is dim (debug) -> accent (info) -> caution -> critical.
    //
    // Two conversions are unavoidable here. Theme colours are translucent where
    // the theme says so (secondary text is 60% white), and Qt's rich-text parser
    // takes opaque `#rrggbb` only — so each one is composited over the page's own
    // background, which is what Qt would have done anyway. And a `color` handed
    // straight to Python arrives as a QColor whose `str()` is not a colour at all,
    // so the strings are produced here, where the values are still colours.
    // LaTeX images are SVG and the colour is baked in when one is rendered, so
    // setting it late costs a whole extra pass: the pages used to do this in their
    // own `Component.onCompleted`, which runs *after* their delegates exist, so
    // every entry rendered once in the default black and then again once the
    // colour arrived (and the arrival dropped the cache, so the second pass was
    // unavoidable). Here, with the log colours, it is set before any page is built.
    function applyLatexColors() {
        const ink = Theme.currentTheme.colors.textColor
        calcVM.set_latex_color(ink)
        historyVM.set_latex_color(ink)
    }

    function applyLogColors() {
        const c = Theme.currentTheme.colors
        const bg = c.backgroundColor
        const over = function (fg) {
            return Qt.rgba(fg.r * fg.a + bg.r * (1 - fg.a),
                           fg.g * fg.a + bg.g * (1 - fg.a),
                           fg.b * fg.a + bg.b * (1 - fg.a), 1).toString()
        }
        logVM.colors = {
            "normal": over(c.textColor),
            "secondary": over(c.textSecondaryColor),
            "debug": over(c.textTertialyColor),
            "info": over(c.systemAttentionColor),
            "warning": over(c.systemCautionColor),
            "error": over(c.systemCriticalColor)
        }
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
            applyLogColors()
            applyLatexColors()
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
