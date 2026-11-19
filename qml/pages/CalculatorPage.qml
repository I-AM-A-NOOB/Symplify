import QtQuick
import QtQuick.Controls 2.15
import QtQuick.Layouts 2.15
import QtQuick.Window 2.15
import RinUI
import "../components"

Item {
    id: page

    //: The result pane has a minimum that still fits the backend status and the
    //: compact copy buttons, plus a readable width where the copy labels fit.
    //: The plot takes a fixed share when it sits beside the result and the spare
    //: height when it sits below it.
    readonly property int inputPanelWidth: settingsVM.inputPanelWidth
    readonly property int resultPaneMinWidth: 270
    readonly property int resultPaneReadableWidth: 340
    readonly property int resultPaneMinHeight: 140
    readonly property int plotPaneMinWidth: 240
    readonly property int plotPanePreferredWidth: 340
    readonly property int plotPaneMinHeight: 180
    readonly property real paneHandleWidth: 16
    readonly property real splitterPillThickness: 4
    readonly property real splitterPillLength: 24
    //: The page's title/actions margin and the workspace's own margin. Only the
    //: title row uses 24; the panes below it sit at 16 (see `Spacing`).
    readonly property int headerInset: Spacing.header
    readonly property int contentInset: Spacing.content

    //: WinUI3 ContentSizer tones: the rest state is the page surface, the hover
    //: band is the closest neutral fill, and the pill is the opaque system
    //: neutral (not a text colour, so it does not vary with state or alpha).
    readonly property color splitterHoverFill: Theme.currentTheme.isDark
        ? Theme.currentTheme.colors.controlTertiaryColor
        : Theme.currentTheme.colors.subtleSecondaryColor
    readonly property color splitterPillColor:
        Theme.currentTheme.colors.systemNeutralColor

    //: One ratio for both orientations. Dragging the result/plot divider writes
    //: it; rotating the layout reads it back, so the panes keep their relative
    //: share instead of snapping to a default.
    property real resultShare: settingsVM.resultShare
    property real pendingResultShare: 0.5
    property real pendingInputWidth: 0

    onResultShareChanged: {
        if (Math.abs(resultShare - settingsVM.resultShare) > 0.0001) {
            pendingResultShare = resultShare
            resultShareSaveTimer.restart()
        }
    }

    function scheduleInputWidth(width) {
        if (width < 280)
            return
        if (Math.round(width) !== settingsVM.inputPanelWidth) {
            pendingInputWidth = width
            inputWidthSaveTimer.restart()
        }
    }

    Timer {
        id: resultShareSaveTimer
        interval: 250
        onTriggered: settingsVM.resultShare = pendingResultShare
    }

    Timer {
        id: inputWidthSaveTimer
        interval: 250
        onTriggered: settingsVM.inputPanelWidth =
            Math.round(pendingInputWidth)
    }

    //: Below this window height the side-by-side result/plot split squeezes
    //: both panes; show one at a time behind a small tab row instead.
    readonly property bool tabbedPanes: calcVM.hasPlot && Window.height < 620
    property int smallPaneIndex: 0

    //: The toolbar labels fit at this content width; below it the two copy
    //: actions become icon-only buttons with their words in tooltips.
    readonly property bool wideHeader: page.width >= 900

    //: Wide layouts put the plot beside the result. The width test is the real
    //: constraint; the ratio keeps a tall, narrow window from looking like a
    //: three-column desktop layout. The plot pane is hidden when there is
    //: nothing to draw, so this is also false then.
    readonly property bool plotBesideResult:
        calcVM.hasPlot
        && !tabbedPanes
        && resultArea.width >= resultPaneReadableWidth + plotPanePreferredWidth
                                + paneHandleWidth
        && page.width / Math.max(1, page.height) >= 1.2

    //: Which side the previous layout put the plot on. The geometry binds to
    //: this while the flip runs, so the animation starts from a normalized
    //: layout of the *current* container rather than stale pixel sizes.
    property bool layoutFromHorizontal: false
    property bool wasPlotBesideResult: false
    //: A plot appearing for the first time has no previous orientation: start
    //: directly at its target. Animating from `layoutFromHorizontal == false`
    //: used to paint the result full-width with the plot below it for one
    //: decision timer, then flip to the side-by-side layout in fullscreen.
    //: Set after the first plot's appearance animation, or immediately when a
    //: page is rebuilt with a plot already present. A later orientation change
    //: still uses the normal layout transition.
    property bool plotWasVisible: false
    //: True while the first plot is growing from the no-plot state into its
    //: target layout. It reuses `layoutProgress`/`layoutAnimation`; the result
    //: starts at full size and the plot starts at zero.
    property bool plotAppearing: false
    //: True while an existing plot is shrinking out after `hasPlot` turns
    //: false. The result grows back to the full area with the same tween.
    property bool plotCollapsing: false
    property bool plotCollapseFromHorizontal: false
    property real plotCollapseShare: 0.5

    Component.onCompleted: {
        if (calcVM.hasPlot) {
            plotWasVisible = true
            settlePlotLayout()
        }
    }

    function settlePlotLayout() {
        layoutFromHorizontal = plotBesideResult
        wasPlotBesideResult = plotBesideResult
        if (!splitArea)
            return
        splitArea.stopLayoutAnimation()
        splitArea.layoutPending = false
        splitArea.layoutProgress = 1
    }

    function beginPlotAppearance() {
        if (!calcVM.hasPlot || plotAppearing)
            return
        plotAppearing = true
        layoutFromHorizontal = plotBesideResult
        wasPlotBesideResult = plotBesideResult
        plotCollapsing = false
        if (!splitArea)
            return
        splitArea.prepareLayoutAnimation()
        plotLayoutSettleTimer.restart()
    }

    function finishPlotAppearance() {
        plotAppearing = false
        plotWasVisible = true
        wasPlotBesideResult = plotBesideResult
    }

    function beginPlotCollapse() {
        if (!plotWasVisible || plotAppearing || plotCollapsing)
            return
        if (!splitArea)
            return
        plotWasVisible = false
        plotCollapsing = true
        plotCollapseFromHorizontal = wasPlotBesideResult
        plotCollapseShare = plotCollapseFromHorizontal
            ? splitArea.horizontalShare : splitArea.verticalShare
        plotLayoutSettleTimer.stop()
        splitArea.prepareLayoutAnimation()
        splitArea.startLayoutAnimation()
    }

    function finishPlotCollapse() {
        plotCollapsing = false
        plotWasVisible = false
    }

    //: Let the first target settle (the split area/layout width arrives in a
    //: later frame) before starting the tween. This is only a settle delay; the
    //: tween itself is the same `layoutProgress` animation used for a flip.
    Timer {
        id: plotLayoutSettleTimer
        interval: 50
        onTriggered: {
            if (!calcVM.hasPlot)
                return
            if (page.tabbedPanes) {
                page.finishPlotAppearance()
                splitArea.layoutPending = false
                splitArea.layoutProgress = 1
                return
            }
            page.layoutFromHorizontal = page.plotBesideResult
            page.wasPlotBesideResult = page.plotBesideResult
            splitArea.startLayoutAnimation()
        }
    }

    Connections {
        target: calcVM

        function onPlotChanged() {
            if (calcVM.hasPlot) {
                if (page.plotCollapsing) {
                    page.plotCollapsing = false
                    page.plotWasVisible = false
                }
                if (!page.plotWasVisible)
                    page.beginPlotAppearance()
            } else {
                plotLayoutSettleTimer.stop()
                page.plotAppearing = false
                if (page.plotWasVisible && !page.plotCollapsing)
                    page.beginPlotCollapse()
                else if (!page.plotCollapsing) {
                    page.plotWasVisible = false
                    if (splitArea)
                        splitArea.stopLayoutAnimation()
                    if (splitArea) {
                        splitArea.layoutPending = false
                        splitArea.layoutProgress = 1
                    }
                }
            }
        }
    }

    onPlotBesideResultChanged: {
        if (!calcVM.hasPlot)
            return
        if (plotAppearing) {
            // The target may still be settling during the delay or tween.
            wasPlotBesideResult = plotBesideResult
            if (!splitArea.layoutAnimationRunning)
                plotLayoutSettleTimer.restart()
            return
        }
        if (!plotWasVisible) {
            beginPlotAppearance()
            return
        }
        layoutFromHorizontal = wasPlotBesideResult
        wasPlotBesideResult = plotBesideResult
        splitArea.beginLayoutTransition()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: page.contentInset
        //: The title keeps the header's top margin; Zen hides it, so the
        //: workspace takes the content value on all four sides there.
        anchors.topMargin: vm.zenMode ? page.contentInset : page.headerInset
        //: The workspace is the page's floor: the split handle and both panes
        //: reach the bottom edge. The 16px gap this used to carry left the
        //: ContentSizer pill and the pane boundary floating above the frame.
        anchors.bottomMargin: 0
        spacing: vm.zenMode ? 0 : 14

        // ---- Page toolbar ----
        //: One row above both panes. The title is the page's, not the input
        //: pane's: it stays put when the input is collapsed and reads as the
        //: heading of the whole workspace. The mode switch and the loud action
        //: live here for the same reason — they act on the page's input, not on
        //: a panel's furniture.
        RowLayout {
            objectName: "calculatorToolbar"
            Layout.fillWidth: true
            //: The title and actions keep the header inset (24) while the
            //: workspace below them uses content (16).
            Layout.leftMargin: page.headerInset - page.contentInset
            Layout.rightMargin: page.headerInset - page.contentInset
            spacing: page.wideHeader ? 8 : 6
            visible: !vm.zenMode

            Text {
                //: The same page-title face as every `PageHeader`, so switching
                //: pages does not change the heading's size or weight. The
                //: toolbar's spacing still tightens below 900px.
                typography: Typography.Subtitle
                text: qsTr("Calculator")
                Layout.alignment: Qt.AlignVCenter
            }

            //: `calcVM.inputMode` is the single source of truth (it survives page
            //: switches); the Segmented only syncs from it, so a rebuilt page
            //: never writes its default index back into the VM.
            Segmented {
                id: modeSwitch

                Layout.alignment: Qt.AlignVCenter
                Component.onCompleted: currentIndex = calcVM.inputMode

                SegmentedItem {
                    text: qsTr("Code")
                    onClicked: inputPane.switchToCode()
                }
                SegmentedItem {
                    text: qsTr("Assign")
                    onClicked: inputPane.switchToAssign()
                }
            }

            Connections {
                target: calcVM

                function onInputModeChanged() {
                    modeSwitch.currentIndex = calcVM.inputMode
                    inputPane.beginModeTransition()
                    if (calcVM.inputMode === 0)
                        inputPane.focusCode()
                    else
                        inputPane.focusAssignName()
                }
            }

            //: The page's one loud action, outside the bar: it is what this page is
            //: *for*, and it is the only thing here that acts on the input as a
            //: whole. Accent-styled, which RinUI's `Button` draws as its primary
            //: fill — `highlighted`, never `flat`, since `flat` outranks
            //: `highlighted` in the colour choice.
            Button {
                highlighted: true
                text: qsTr("Calculate")
                //: The accent name from the icon font RinUI ships.
                icon.name: "ic_fluent_calculator_20_regular"
                icon.color: enabled
                    ? Theme.currentTheme.colors.textAccentColor
                    : Theme.currentTheme.colors.textDisabledColor
                Layout.alignment: Qt.AlignVCenter

                Tip {
                    text: parent.text
                }

                onClicked: inputPane.runCalculation()
            }

            //: The examples write into the input instead of acting on it, so
            //: they are a dropdown of their own rather than one more action.
            //: Icon-only here: the bar has to keep the title, the mode and the
            //: loud action in one line at the minimum window width.
            DropDownButton {
                flat: true
                text: ""
                icon.name: "ic_fluent_math_formula_sparkle_20_regular"
                icon.color: enabled
                    ? Theme.currentTheme.colors.textColor
                    : Theme.currentTheme.colors.textDisabledColor
                Layout.alignment: Qt.AlignVCenter
                Accessible.name: qsTr("Examples")

                Tip {
                    text: qsTr("Examples")
                }

                MenuItem {
                    text: "diff(x**2, x)"
                    onTriggered: inputPane.setExample("diff(x**2, x)")
                }
                MenuItem {
                    text: "integrate(x**2, x)"
                    onTriggered: inputPane.setExample("integrate(x**2, x)")
                }
                MenuItem {
                    text: "limit(sin(x)/x, x, 0)"
                    onTriggered: inputPane.setExample("limit(sin(x)/x, x, 0)")
                }
                MenuItem {
                    text: "solve(x**2 - 4, x)"
                    onTriggered: inputPane.setExample("solve(x**2 - 4, x)")
                }
                MenuItem {
                    text: "Matrix([[1, 2], [3, 4]])"
                    onTriggered: inputPane.setExample("Matrix([[1, 2], [3, 4]])")
                }
            }

            //: Clear stays a normal, icon-only toolbar button. Undo and Redo do
            //: not live here: they belong with the cursor keys they edit beside
            //: (see `KeyboardPanel`), which is also where the mock-up puts them.
            ToolButton {
                objectName: "clearInputButton"

                flat: true
                icon.name: "ic_fluent_clear_formatting_20_regular"
                icon.color: enabled
                    ? Theme.currentTheme.colors.textColor
                    : Theme.currentTheme.colors.textDisabledColor
                Layout.alignment: Qt.AlignVCenter
                Accessible.name: qsTr("Clear input")

                Tip { text: qsTr("Clear input") }
                onClicked: inputPane.clearInput()
            }


        }

        // ---- Workspace: input / result and plot ----
        SplitView {
            id: workspace

            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Horizontal

            handle: Rectangle {
                implicitWidth: page.paneHandleWidth
                implicitHeight: page.paneHandleWidth
                color: inputSplitHover.hovered
                    ? page.splitterHoverFill : "transparent"
                visible: inputPane.visible

                Behavior on color {
                    ColorAnimation {
                        duration: 120
                        easing.type: Easing.OutCubic
                    }
                }

                HoverHandler { id: inputSplitHover }

                //: WinUI3's ContentSizer: a 20px neutral hover band and a fixed
                //: 8x36 pill. The pill's size and opaque neutral colour do not
                //: change on hover; only the band appears.
                Rectangle {
                    anchors.centerIn: parent
                    width: page.splitterPillThickness
                    height: page.splitterPillLength
                    radius: page.splitterPillThickness / 2
                    color: page.splitterPillColor
                }
            }

            // The input is a resizable pane, not a details sidebar. Zen hides it
            // entirely; the SplitView then gives the result/plot area the width.
            InputPane {
                id: inputPane

                SplitView.preferredWidth: page.inputPanelWidth
                SplitView.minimumWidth: 280
            }

            Connections {
                target: inputPane
                function onWidthChanged() {
                    page.scheduleInputWidth(inputPane.width)
                }
            }

            // Right area: result and plot. The result/plot divider is one
            // ratio, not two layout states: dragging it writes `resultShare`,
            // and the horizontal and vertical bindings both read it back.
            Item {
                id: resultArea

                SplitView.fillWidth: true
                SplitView.minimumWidth: page.resultPaneMinWidth
                //: The result/plot handle extends into the page's right inset
                //: (see `plotHandle.width`), so this pane must not clip it.
                //: Every pane inside still clips its own content.
                clip: false

                Item {
                    id: splitArea
                    objectName: "splitArea"

                    anchors.fill: parent

                    readonly property real horizontalLength:
                        Math.max(0, width - page.paneHandleWidth)
                    readonly property real verticalLength:
                        Math.max(0, height - page.paneHandleWidth)
                    //: The small-window Result/Plot tabs occupy this strip.
                    readonly property real tabbedHeaderHeight:
                        page.tabbedPanes ? 40 : 0
                    //: While the 16ms decision timer runs, keep the *old*
                    //: orientation visible. Otherwise the bindings would already
                    //: show the new layout, then jump back to animate from it.
                    property bool layoutPending: false
                    readonly property bool targetHorizontal:
                        page.plotCollapsing
                            ? page.plotCollapseFromHorizontal
                            : layoutPending ? page.layoutFromHorizontal
                                            : page.plotBesideResult
                    readonly property real splitLength:
                        targetHorizontal ? horizontalLength : verticalLength
                    //: Clamp each orientation against its own dimensions. Using
                    //: the raw share during a flip made the plot overshoot when
                    //: its share was over half (the result share was below the
                    //: result minimum), then snap back to the clamped size at
                    //: the end of the animation.
                    readonly property real horizontalShare: {
                        if (horizontalLength <= 0)
                            return page.resultShare
                        const low = page.resultPaneMinWidth / horizontalLength
                        const high = 1 - page.plotPaneMinWidth / horizontalLength
                        return Math.max(low, Math.min(high, page.resultShare))
                    }
                    readonly property real verticalShare: {
                        if (verticalLength <= 0)
                            return page.resultShare
                        const low = page.resultPaneMinHeight / verticalLength
                        const high = 1 - page.plotPaneMinHeight / verticalLength
                        return Math.max(low, Math.min(high, page.resultShare))
                    }
                    readonly property real effectiveShare:
                        targetHorizontal ? horizontalShare : verticalShare

                    //: 0 at the old orientation, 1 at the new one. The panes'
                    //: geometry is interpolated from normalized dimensions of
                    //: the *current* split area, not from stale pixel sizes, so
                    //: a window resize cannot push the plot height negative.
                    property real layoutProgress: 1
                    readonly property bool layoutAnimationRunning:
                        layoutAnimation.running
                    onLayoutProgressChanged: {
                        if (layoutProgress >= 1) {
                            if (page.plotAppearing)
                                page.finishPlotAppearance()
                            else if (page.plotCollapsing)
                                page.finishPlotCollapse()
                        }
                    }

                    function stopLayoutAnimation() {
                        layoutAnimation.stop()
                    }

                    function prepareLayoutAnimation() {
                        layoutAnimation.stop()
                        layoutPending = false
                        layoutProgress = 0
                    }

                    function startLayoutAnimation() {
                        layoutPending = false
                        layoutProgress = 0
                        layoutAnimation.restart()
                    }

                    function beginLayoutTransition() {
                        layoutAnimation.stop()
                        layoutProgress = 1
                        layoutPending = true
                        layoutDecisionTimer.restart()
                    }

                    function applyLayoutTransition() {
                        //: Let the window resize settle before touching the
                        //: plot. qmlmathplot hangs if its canvas is resized in
                        //: the same event cycle as a small window resize.
                        if (Window.height < 620) {
                            layoutProgress = 1
                            layoutPending = false
                            return
                        }
                        layoutProgress = 0
                        layoutPending = false
                        layoutAnimation.restart()
                    }

                    Timer {
                        id: layoutDecisionTimer
                        interval: 16
                        onTriggered: splitArea.applyLayoutTransition()
                    }

                    NumberAnimation {
                        id: layoutAnimation
                        target: splitArea
                        property: "layoutProgress"
                        from: 0
                        to: 1
                        duration: Utils.animationSpeed
                        easing.type: Easing.OutCubic

                        onFinished: {
                            if (page.plotCollapsing)
                                page.finishPlotCollapse()
                            else if (page.plotAppearing)
                                page.finishPlotAppearance()
                        }
                    }

                    readonly property real resultWidth: {
                        if (page.tabbedPanes || (!calcVM.hasPlot && !page.plotCollapsing))
                            return width
                        if (page.plotCollapsing) {
                            const start = page.plotCollapseFromHorizontal
                                ? horizontalLength * page.plotCollapseShare : width
                            return start + (width - start) * layoutProgress
                        }
                        if (layoutPending)
                            return targetHorizontal
                                ? horizontalLength * horizontalShare : width
                        const end = targetHorizontal
                            ? horizontalLength * horizontalShare : width
                        const start = page.plotAppearing
                            ? width
                            : page.layoutFromHorizontal
                                ? horizontalLength * horizontalShare : width
                        return start + (end - start) * layoutProgress
                    }
                    readonly property real resultHeight: {
                        if (page.tabbedPanes)
                            return Math.max(0, height - tabbedHeaderHeight)
                        if (!calcVM.hasPlot && !page.plotCollapsing)
                            return height
                        if (page.plotCollapsing) {
                            const start = page.plotCollapseFromHorizontal
                                ? height : verticalLength * page.plotCollapseShare
                            return start + (height - start) * layoutProgress
                        }
                        if (layoutPending)
                            return targetHorizontal
                                ? height : verticalLength * verticalShare
                        const end = targetHorizontal
                            ? height : verticalLength * verticalShare
                        const start = page.plotAppearing
                            ? height
                            : page.layoutFromHorizontal
                                ? height : verticalLength * verticalShare
                        return start + (end - start) * layoutProgress
                    }

                    Segmented {
                        id: paneTabs

                        visible: page.tabbedPanes
                        anchors.top: parent.top
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: 220
                        height: 32
                        z: 2
                        currentIndex: page.smallPaneIndex

                        SegmentedItem {
                            text: qsTr("Result")
                            onClicked: page.smallPaneIndex = 0
                        }
                        SegmentedItem {
                            text: qsTr("Plot")
                            onClicked: page.smallPaneIndex = 1
                        }
                    }

                    ResultPane {
                        id: resultPane

                        y: splitArea.tabbedHeaderHeight
                        width: splitArea.resultWidth
                        height: splitArea.resultHeight
                        visible: !page.tabbedPanes || page.smallPaneIndex === 0
                    }

            //: The divider writes the one result share both orientations read.
            //: It is a plain MouseArea rather than a SplitView handle so the
            //: ratio survives an orientation change by construction.
            Rectangle {
                id: plotHandle

                visible: calcVM.hasPlot && !page.tabbedPanes
                color: plotSplitHover.containsMouse
                    ? page.splitterHoverFill : "transparent"
                x: splitArea.targetHorizontal ? resultPane.width : 0
                y: splitArea.targetHorizontal ? 0 : resultPane.height
                //: A vertical handle is the full split height. The horizontal
                //: one runs to the page's right edge, through the inset the
                //: panes keep, so it can be grabbed beside the last pixel of
                //: the content rather than stopping at the plot card.
                width: splitArea.targetHorizontal
                    ? page.paneHandleWidth
                    : splitArea.width + page.contentInset
                height: splitArea.targetHorizontal
                    ? splitArea.height : page.paneHandleWidth

                Behavior on color {
                    ColorAnimation {
                        duration: 120
                        easing.type: Easing.OutCubic
                    }
                }

                MouseArea {
                    id: plotSplitHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: splitArea.targetHorizontal
                        ? Qt.SplitHCursor : Qt.SplitVCursor

                    onPositionChanged: (mouse) => {
                        if (!pressed || splitArea.splitLength <= 0)
                            return
                        const point = mapToItem(splitArea, mouse.x, mouse.y)
                        if (splitArea.targetHorizontal) {
                            page.resultShare = Math.max(0, Math.min(1,
                                (point.x - page.paneHandleWidth / 2)
                                    / splitArea.splitLength))
                        } else {
                            page.resultShare = Math.max(0, Math.min(1,
                                (point.y - page.paneHandleWidth / 2)
                                    / splitArea.splitLength))
                        }
                    }
                }

                //: The same opaque ContentSizer pill, rotated with the
                //: result/plot layout. It is hidden during the flip so it cannot
                //: float across the content.
                Rectangle {
                    //: Centred on the *pane*, not on the handle: the horizontal
                    //: handle extends through the right inset, and the pill has
                    //: to stay on the content boundary it represents.
                    x: splitArea.targetHorizontal
                        ? (page.paneHandleWidth - width) / 2
                        : (splitArea.width - width) / 2
                    y: splitArea.targetHorizontal
                        ? (splitArea.height - height) / 2
                        : (page.paneHandleWidth - height) / 2
                    visible: !splitArea.layoutPending
                        && splitArea.layoutProgress >= 1
                    width: splitArea.targetHorizontal
                        ? page.splitterPillThickness : page.splitterPillLength
                    height: splitArea.targetHorizontal
                        ? page.splitterPillLength : page.splitterPillThickness
                    radius: page.splitterPillThickness / 2
                    color: page.splitterPillColor
                }
            }

            // The plot is a sibling of the result pane, never a child of its
            // scroller. That is what keeps a long formula from dragging the
            // plot away and lets the wheel over the plot stay with the plot.
            // The plot itself lives in the viewmodel (RinUI rebuilds a page on
            // every navigation), so this is a view of it and owns no state.
            PlotPane {
                id: plotPane

                visible: (calcVM.hasPlot || page.plotCollapsing)
                    && (!page.tabbedPanes || page.smallPaneIndex === 1)
                keepAlive: page.plotCollapsing
                x: page.tabbedPanes ? 0
                    : splitArea.targetHorizontal
                        ? resultPane.width + page.paneHandleWidth : 0
                y: page.tabbedPanes ? splitArea.tabbedHeaderHeight
                    : splitArea.targetHorizontal
                        ? 0 : resultPane.height + page.paneHandleWidth
                width: page.tabbedPanes ? splitArea.width
                    : splitArea.targetHorizontal
                        ? Math.max(0, splitArea.width - resultPane.width
                            - page.paneHandleWidth)
                        : splitArea.width
                height: page.tabbedPanes
                    ? Math.max(0, splitArea.height - splitArea.tabbedHeaderHeight)
                    : splitArea.targetHorizontal
                        ? splitArea.height
                        : Math.max(0, splitArea.height - resultPane.height
                            - page.paneHandleWidth)
            }
                    }
                }
            }
        }

    Connections {
        target: vm

        function onZenModeChanged() {
            Qt.callLater(function() {
                if (vm.zenMode)
                    resultPane.focusResult()
                else
                    inputPane.fallbackTarget().forceActiveFocus()
            })
        }
    }

    Shortcut {
        sequences: ["Ctrl+Return"]
        onActivated: inputPane.runCalculation()
    }

    //: The calculator's own refusals — a SymPy built-in name, which is stored but
    //: worth saying out loud. The dialog and its wiring are the shared pair.
    WarningDialog {
        source: calcVM
    }
}
