import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 2.15
import RinUI
import "components"

FluentWindow {
    id: window

    visible: true
    title: qsTr("Symplify")
    // The mark in RinUI's own title bar, left of the title. An SVG and not the
    // .ico: RinUI draws it through `Icon.qml`'s `Image`, which asks for one
    // 16 px pixmap, and the vector keeps it sharp on a 150%/200% display where
    // the same request is 24/32 px. Resolved against this file, so it is
    // `<root>/icon/Symplify.svg` in a checkout and next to the exe when frozen
    // (`ROOT` is the exe's directory there).
    icon: Qt.resolvedUrl("../icon/Symplify.svg")
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

    // Zen is a window-level mode: the page cannot hide the navigation bar or
    // change the custom title bar by itself.
    property bool zenApplied: false
    property bool zenRestoreCollapsed: false
    property bool zenRestoreNavVisible: true
    //: True only when Zen itself entered fullscreen and therefore owns the
    //: exit. An F11 fullscreen made by the user survives leaving Zen.
    property bool zenEnteredFullscreen: false

    // Fullscreen is orthogonal to Zen: F11 uses it in any mode, and Zen may use
    // it as its configured entry behavior. The transition owns a snapshot of
    // the window state; geometry tracking is off while the frame is hidden so
    // the fullscreen rect never overwrites the remembered window geometry.
    property bool fullscreenApplied: false
    //: The real title bar is gone in fullscreen. This transient overlay is the
    //: visible way back: `zenTopArea` is both the strip's rectangle and its
    //: hover target, so the strip is shown while the pointer is inside it.
    //: A touch screen has no hover, so a tap toggles this pin instead.
    property bool zenChromePinned: false
    property bool fullscreenWasFullScreen: false
    property bool fullscreenWasMaximized: false
    property int fullscreenRestoreTitleHeight: 0
    property int fullscreenRestoreDragArea: 5
    property real fullscreenRestoreBackgroundRadius: 0
    property int fullscreenRestoreBackgroundBorder: 1
    property color fullscreenRestoreBackgroundColor: Theme.currentTheme.colors.backgroundColor
    property rect fullscreenRestoreGeometry: Qt.rect(0, 0, 0, 0)

    function enterFullscreen() {
        if (fullscreenApplied)
            return
        fullscreenWasFullScreen = visibility === Window.FullScreen
        fullscreenWasMaximized = visibility === Window.Maximized
        fullscreenRestoreGeometry = Qt.rect(x, y, width, height)
        fullscreenRestoreTitleHeight = titleBarHeight
        //: RinUI insets the window content by the resize band. In fullscreen
        //: there is nothing to resize, and that band is the 4-5px strip of
        //: window background (plus its rounded corner) at the edges.
        fullscreenRestoreDragArea = Utils.windowDragArea
        Utils.windowDragArea = 0
        fullscreenRestoreBackgroundRadius = window.background.radius
        fullscreenRestoreBackgroundBorder = window.background.border.width
        fullscreenRestoreBackgroundColor = window.background.color
        settingsVM.setGeometryTracking(false)
        titleBarHeight = 0
        showFullScreen()
        fullscreenApplied = true
        //: RinUI's own onVisibilityChanged restores the rounded window
        //: background after `showFullScreen`; reassert the square fullscreen
        //: surface on the next turn, when that handler has run. The guards
        //: below are the real protection: the platform may deliver the state
        //: change after this turn on a scaled monitor.
        Qt.callLater(squareFullscreenSurface)
        if (zenApplied)
            showZenInfo()
    }

    function setNativeWindowCorners(rounded) {
        //: WinEventManager is a Windows-only context property.
        if (typeof WinEventManager !== "undefined"
                && WinEventManager.set_window_corners)
            WinEventManager.set_window_corners(window, rounded)
    }

    //: Windows 11 paints a 1px *accent* border inside every maximized window,
    //: and it keeps a frame border in fullscreen too. The app draws its own
    //: frame, so the native one shows as an unfilled rim: at 150%/200% scaling
    //: that 1px reads as the ~2px strip the window edge otherwise shows. Both
    //: states hand the frame to QML and suppress the DWM border; windowed keeps
    //: the rounded corners the system draws.
    function syncNativeFrame() {
        const framed = window.fullscreenApplied
            || window.visibility === Window.Maximized
        setNativeWindowCorners(!framed)
    }

    //: The window surface a fullscreen page sits on, per theme. It also matches
    //: the 1px StackView inset, which otherwise reads as a side strip.
    readonly property color fullscreenSurfaceColor:
        Theme.currentTheme.isDark ? "#202020" : "#F9F9F9"

    //: The native frame follows the window state, not only fullscreen: the
    //: maximized state is equally "the app paints the frame" (RinUI squares the
    //: corners and draws its own 1px border there).
    Connections {
        target: window

        function onVisibilityChanged() {
            window.syncNativeFrame()
        }
    }

    function squareFullscreenSurface() {
        if (!fullscreenApplied || !window.background)
            return
        window.background.radius = 0
        window.background.border.width = 0
        window.background.color = fullscreenSurfaceColor
        setNativeWindowCorners(false)
    }

    //: A fullscreen window has no frame to show, and "apply it once" is not
    //: enough: RinUI's own `onVisibilityChanged` re-rounds the window and puts
    //: its 1px border back, and the platform may deliver the fullscreen state
    //: change *after* the reassert (more often on a scaled monitor, where the
    //: DPI change lands in the same turn). Windows 11 then paints its 1px accent
    //: window border - a visible 2px strip at the screen edge at 200% scaling.
    //: These connections set the surface back the moment anything writes it, so
    //: the result no longer depends on event order.
    Connections {
        target: window.background ? window.background : null

        function onRadiusChanged() {
            if (window.fullscreenApplied && window.background.radius !== 0)
                window.background.radius = 0
        }

        function onColorChanged() {
            if (window.fullscreenApplied
                    && window.background.color !== window.fullscreenSurfaceColor)
                window.background.color = window.fullscreenSurfaceColor
        }
    }

    Connections {
        target: window.background ? window.background.border : null

        function onWidthChanged() {
            if (window.fullscreenApplied && window.background.border.width !== 0)
                window.background.border.width = 0
        }
    }

    //: The DWM side (square corners, no border, no frame thickness) has to be
    //: re-asked whenever the platform may have reset it: every visibility,
    //: screen and DPI change. Both functions no-op outside their state.
    Connections {
        target: window

        function onVisibilityChanged() {
            window.squareFullscreenSurface()
        }

        function onScreenChanged() {
            window.squareFullscreenSurface()
            window.syncNativeFrame()
        }

        function onDevicePixelRatioChanged() {
            window.squareFullscreenSurface()
            window.syncNativeFrame()
        }
    }

    function exitFullscreen() {
        if (!fullscreenApplied)
            return
        titleBarHeight = fullscreenRestoreTitleHeight
        if (fullscreenWasFullScreen) {
            showFullScreen()
        } else if (fullscreenWasMaximized) {
            showMaximized()
        } else {
            visibility = Window.Windowed
            x = fullscreenRestoreGeometry.x
            y = fullscreenRestoreGeometry.y
            width = fullscreenRestoreGeometry.width
            height = fullscreenRestoreGeometry.height
        }
        settingsVM.setGeometryTracking(true)
        Utils.windowDragArea = fullscreenRestoreDragArea
        fullscreenApplied = false
        const restoreRadius = fullscreenRestoreBackgroundRadius
        const restoreBorder = fullscreenRestoreBackgroundBorder
        const restoreColor = fullscreenRestoreBackgroundColor
        Qt.callLater(function() {
            if (fullscreenApplied || !window.background)
                return
            window.background.radius = restoreRadius
            window.background.border.width = restoreBorder
            window.background.color = restoreColor
            //: The restore may land in the maximized state, which suppresses
            //: the native border exactly like fullscreen does.
            syncNativeFrame()
        })
        zenChromePinned = false
        zenInfoLoader.active = false
    }

    //: The strip's height. The same rectangle is the hover target, so there is
    //: no second measurement to keep in step with it.
    readonly property int zenChromeHeight: 40

    function showZenInfo() {
        // Re-activating the loader replays InfoBar's enter animation.
        zenInfoLoader.active = false
        Qt.callLater(function() {
            if (fullscreenApplied && zenApplied)
                zenInfoLoader.active = true
        })
    }

    function handleZenEscape() {
        if (fullscreenApplied)
            exitFullscreen()
        else
            vm.setZenMode(false)
    }

    function toggleFullscreen() {
        if (fullscreenApplied)
            exitFullscreen()
        else
            enterFullscreen()
        //: F11 is the user taking control; leaving Zen must not undo it.
        zenEnteredFullscreen = false
    }

    function enterZen() {
        if (zenApplied)
            return
        zenApplied = true
        const bar = navigationView.navigationBar
        zenRestoreCollapsed = bar.collapsed
        zenRestoreNavVisible = bar.visible
        // Zen removes the navigation entirely, not just its expanded state; it
        // is one content layout in both windowed and fullscreen Zen.
        bar.visible = false
        zenEnteredFullscreen = false
        if (settingsVM.zenFullscreen && !fullscreenApplied) {
            enterFullscreen()
            zenEnteredFullscreen = true
        }
    }

    function leaveZen() {
        if (!zenApplied)
            return
        if (zenEnteredFullscreen && fullscreenApplied)
            exitFullscreen()
        const bar = navigationView.navigationBar
        bar.visible = zenRestoreNavVisible
        bar.collapsed = zenRestoreCollapsed
        zenEnteredFullscreen = false
        zenApplied = false
        zenChromePinned = false
        zenInfoLoader.active = false
    }

    navigationView.navExpandWidth: 230
    //: Fullscreen has no window corners or resize band to show. RinUI's
    //: top-left clip, app-layer border and 1px StackView inset otherwise leave
    //: a thin rounded edge around the page.
    navigationView.contentCornerClipEnabled: !window.fullscreenApplied
    navigationView.appLayerEnabled: !window.fullscreenApplied

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
        applyWindowFrame()
        applyLogColors()
        applyLatexColors()
        applyPlotTheme()
        showKeyboardLoadError()
        // Start the calculation worker after the first frame so its SymPy
        // import does not land on the user's first Enter.
        Qt.callLater(calcVM.warmUpBackend)
    }

    //: RinUI's window frame is a 1px stroke of `windowBorderColor`, which is 7%
    //: opaque, painted directly on the *transparent* window surface. Behind it
    //: is the desktop, so the app shows an unfilled rim: at 150%/200% scaling
    //: the 1px line is a 2px strip of whatever the window sits on (the wallpaper
    //: at the screen edge, mica elsewhere). Compositing the stroke over the
    //: surface colour makes it the solid line it is meant to look like — the
    //: same 1px frame, just opaque. RinUI re-assigns the radius/border in its own
    //: `onVisibilityChanged`, so this is re-applied with the rest of the theme.
    function applyWindowFrame() {
        if (!window.background)
            return
        window.background.border.color = Qt.tint(
            Theme.currentTheme.colors.backgroundColor,
            Theme.currentTheme.colors.windowBorderColor)
    }

    function showKeyboardLoadError() {
        if (vm.keyboardLoadError !== "" && !vm.keyboardLoadErrorShown) {
            keyboardLoadDialog.open()
            vm.markKeyboardLoadErrorShown()
        }
    }

    // The plot's style follows the app's side (seaborn's base style sheets).
    // The plot object lives in the calculator viewmodel and outlives every page,
    // so the window is what re-dresses it — including after a theme switch,
    // which rebuilds RinUI's theme object (see the Connections below).
    function applyPlotTheme() {
        calcVM.setPlotTheme(Theme.currentTheme.isDark)
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
        // One call: the root viewmodel owns the whole `LatexStyle` and hands it to
        // every surface that renders LaTeX, so adding one is a Python-side change.
        vm.set_latex_color(Theme.currentTheme.colors.textColor)
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
        target: vm

        function onZenModeChanged() {
            if (vm.zenMode) {
                window.enterZen()
            } else {
                window.leaveZen()
            }
        }
    }

    Connections {
        target: navigationView

        //: Zen is a calculator view. Leaving the page through the navigation bar
        //: must also leave the window-level mode.
        function onPageChanged() {
            if (vm.zenMode)
                vm.setZenMode(false)
        }
    }

    Shortcut {
        sequence: "F11"
        context: Qt.WindowShortcut
        onActivated: window.toggleFullscreen()
    }

    Connections {
        target: settingsVM

        function onAccentChanged() {
            applyAccent()
        }

        //: A code-family or bracket-mode change also changes the palette. The
        //: Settings page normally owns the screen while it happens, but this
        //: keeps a future live settings surface (and programmatic changes)
        //: correct; `set_palette` is a no-op when nothing actually changed.
        function onChanged() {
            vm.refreshCodeHighlighting(Theme.isDark())
        }
    }

    // A theme switch rebuilds the theme object, so the accent has to be
    // re-applied to the new one (this also covers the OS scheme changing while
    // the theme follows it).
    Connections {
        target: Theme

        function onCurrentThemeChanged() {
            applyAccent()
            applyWindowFrame()
            applyLogColors()
            applyLatexColors()
            applyPlotTheme()
            //: The settings page hides this case: changing the theme there means
            //: navigating away, which rebuilds the Calculator page and attaches
            //: a fresh highlighter. An OS scheme change leaves the live document
            //: (and its old palette) in place, so recolour it explicitly.
            vm.refreshCodeHighlighting(Theme.isDark())
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

        function onKeyboardLoadErrorChanged() {
            showKeyboardLoadError()
        }
    }

    //: Title-bar Zen toggle: a fixed slot immediately left of the window
    //: controls. In normal mode it enters Zen; in Zen it exits. The page
    //: toolbar no longer carries a second Zen button.
    //:
    //: It sits where the fullscreen strip's Exit Zen sits — the 32x32 slot whose
    //: right edge is the minimize control's left edge — so the control does not
    //: jump when Zen enters fullscreen. That rules out `titleBarHost`: RinUI's
    //: title-bar layout ends that host one 48px spacing step before the window
    //: controls, and it clips. The button is therefore parented to the title bar
    //: itself (`titleBarHost` -> its `RowLayout` -> the `TitleBar`), where the
    //: right edge is the window's and nothing lays it out as a cell.
    //: On macOS the window controls are native and live on the left, so the
    //: right edge is free and the old 8px inset stays.
    ToolButton {
        id: titleZenButton
        objectName: "titleZenButton"

        parent: window.titleBarHost ? window.titleBarHost.parent.parent : null
        anchors.right: parent ? parent.right : undefined
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
        //: 4px of air between Zen and the minimize control, and the same 4px is
        //: a spacer in the fullscreen strip so the two slots stay identical.
        anchors.rightMargin: window.isMacOS ? 8
            : 4 + 48 * ((window.minimizeVisible ? 1 : 0)
                        + (window.maximizeVisible ? 1 : 0)
                        + (window.closeVisible ? 1 : 0))
        width: 32
        height: 32
        flat: true
        visible: !window.fullscreenApplied
            && String(navigationView.currentPage).endsWith("CalculatorPage.qml")
        z: 1
        icon.name: vm.zenMode
            ? "ic_fluent_full_screen_minimize_20_regular"
            : "ic_fluent_full_screen_maximize_20_regular"
        icon.color: Theme.currentTheme.colors.textColor
        Accessible.name: vm.zenMode
            ? qsTr("Exit Zen mode") : qsTr("Zen mode")
        Tip {
            text: vm.zenMode ? qsTr("Exit Zen mode") : qsTr("Zen mode")
        }
        onClicked: vm.toggleZen()
    }

    //: Windowed Zen has no strip, so F11 was its only way into full screen,
    //: while the full-screen strip can come back to a window with a button. This
    //: is that missing half, and it exists only in Zen: normal mode already has
    //: the maximize control and F11. The full screen it starts belongs to Zen
    //: (the same rule as `workspace.zen_fullscreen`), so leaving Zen restores the
    //: window instead of leaving the user in a fullscreen without a title bar.
    ToolButton {
        id: titleFullscreenButton
        objectName: "titleFullscreenButton"

        parent: window.titleBarHost ? window.titleBarHost.parent.parent : null
        anchors.right: titleZenButton.left
        anchors.rightMargin: 4
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
        width: 32
        height: 32
        flat: true
        visible: titleZenButton.visible && vm.zenMode
        z: 1
        icon.name: "ic_fluent_arrow_maximize_20_regular"
        icon.color: Theme.currentTheme.colors.textColor
        Accessible.name: qsTr("Enter full screen")
        Tip {
            text: qsTr("Enter full screen")
        }
        onClicked: {
            window.zenEnteredFullscreen = true
            window.enterFullscreen()
        }
    }

    Shortcut {
        sequence: "Escape"
        context: Qt.WindowShortcut
        //: A plain F11 fullscreen hides the title bar too, so Esc must be a way
        //: back from it as well — not only from Zen.
        enabled: window.fullscreenApplied || window.zenApplied
        onActivated: window.handleZenEscape()
    }

    //: Keyboard equivalent of the title-bar Zen control. Entering is limited to
    //: the Calculator — Zen hides the navigation, and the page's own layout is
    //: what makes the mode meaningful — but leaving is always allowed.
    //: Not `Ctrl+Alt+Z`: a system hotkey on at least this machine swallows that
    //: combination before Qt sees it (real keystrokes verified; Ctrl+Alt+M
    //: arrives). "M" reads as the minimal-UI mode.
    Shortcut {
        sequence: "Ctrl+Alt+M"
        context: Qt.WindowShortcut
        enabled: vm.zenMode
            || String(navigationView.currentPage).endsWith("CalculatorPage.qml")
        onActivated: vm.toggleZen()
    }

    //: In fullscreen Zen the real title bar is hidden, and this strip is the
    //: way back. The zone is the strip's own 40px rectangle and the strip is its
    //: child: a `MouseArea` because `containsMouse` is based on that rectangle
    //: alone, it never moves (the slide is the child's transform), and it is a
    //: **sibling of the page, not an ancestor** — it cannot take hover away from
    //: the page. A `HoverHandler` at the window root did exactly that: an ancestor
    //: hover handler silenced hover for the whole page (the result/plot splitters'
    //: hover fills, every button) while the strip was hidden — the regression this
    //: structure fixes.
    MouseArea {
        id: zenTopZone
        objectName: "zenTopZone"
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: window.zenChromeHeight
        visible: window.fullscreenApplied && window.zenApplied
        z: 100
        hoverEnabled: true
        acceptedButtons: Qt.NoButton

        readonly property bool shown: containsMouse || window.zenChromePinned

        //: Touch and pen have no hover (a pen may, but not reliably), so a tap
        //: toggles the pin; the mouse path never consumes clicks here.
        TapHandler {
            acceptedDevices: PointerDevice.TouchScreen | PointerDevice.Pen
            onTapped: window.zenChromePinned = !window.zenChromePinned
        }

        //: The strip itself, sliding and fading on `zenTopZone.shown`. It is a
        //: child so the controls inside it keep the zone hovered (`containsMouse`)
        //: while the pointer rests on them.
        Rectangle {
            id: zenChrome
            objectName: "zenChrome"
            anchors.fill: parent
            visible: zenTopZone.shown || opacity > 0
            //: A fading strip must not keep its controls clickable.
            enabled: zenTopZone.shown
            color: "transparent"
            border.width: 0
            opacity: zenTopZone.shown ? 1 : 0

            transform: Translate {
                id: zenChromeSlide
                y: zenTopZone.shown ? 0 : -zenChrome.height

                Behavior on y {
                    NumberAnimation { duration: 200; easing.type: Easing.OutCubic }
                }
            }

            Behavior on opacity {
                NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
            }

            //: Acrylic, like the other transient RinUI chrome. The page/nav
            //: beneath is the source; the strip itself is not part of that source.
            AcrylicBrush {
                anchors.fill: parent
                sourceItem: navigationView
                radius: 0
                live: zenChrome.visible
            }

            Rectangle {
                anchors.fill: parent
                color: "transparent"
                border.width: Theme.currentTheme.appearance.borderWidth
                border.color: Theme.currentTheme.colors.cardBorderColor
            }

            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                height: parent.height
                spacing: 0

                ToolButton {
                    id: zenExitButton
                    objectName: "zenExitButton"
                    anchors.verticalCenter: parent.verticalCenter
                    width: 32
                    height: 32
                    flat: true
                    icon.name: "ic_fluent_full_screen_minimize_20_regular"
                    icon.color: Theme.currentTheme.colors.textColor
                    Accessible.name: qsTr("Exit Zen mode")
                    Tip { text: qsTr("Exit Zen mode") }
                    onClicked: vm.setZenMode(false)
                }
                //: The 4px gap the windowed slot also applies (see `titleZenButton`).
                Item {
                    width: 4
                    height: parent.height
                }
                CtrlBtn {
                    id: zenMinimizeButton
                    objectName: "zenMinimizeButton"
                    mode: 1
                    height: parent.height
                }
                CtrlBtn {
                    id: zenWindowedButton
                    objectName: "zenWindowedButton"
                    mode: 0
                    height: parent.height
                    //: "Windowed" means leave fullscreen, not leave Zen. It wears the
                    //: collapse arrow rather than `mode`'s single-square maximize (or
                    //: the Windows restore-down pair): in the strip every other
                    //: control undoes what it entered — Zen leaves Zen, fullscreen
                    //: leaves fullscreen — and an arrow pointing back into the frame
                    //: says that without needing the word.
                    icon: "ic_fluent_arrow_minimize_20_regular"
                    //: The stock CtrlBtn would maximize instead.
                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton
                        onClicked: window.exitFullscreen()
                    }
                }
                CtrlBtn {
                    id: zenCloseButton
                    objectName: "zenCloseButton"
                    mode: 2
                    height: parent.height
                }
            }
        }
    }

    //: The exit instructions are their own top InfoBar, not text inside the
    //: transient title strip. It is recreated on each fullscreen entry so its
    //: enter animation and timeout play again.
    Loader {
        id: zenInfoLoader
        objectName: "zenInfoLoader"
        active: false
        anchors.top: parent.top
        anchors.topMargin: 48
        anchors.horizontalCenter: parent.horizontalCenter
        z: 102

        sourceComponent: InfoBar {
            width: Math.min(620, window.width - 48)
            title: qsTr("Zen mode")
            text: qsTr("Move pointer to the top (or tap) for controls · Esc: full screen → Zen → normal")
            severity: Severity.Info
            closable: true
            timeout: 5000
            position: Position.Top
        }
    }

    MessageDialog {
        id: keyboardLoadDialog
        title: qsTr("Keyboard could not be loaded")
        body: vm.keyboardLoadError
    }
}
