import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window 2.15
import RinUI

//: The calculator's result surface: the backend state, the copy actions, the
//: outcome line, the formula strip and the alternative forms — plus the empty
//: pane's watermark behind them.
//:
//: A component of its own because it is one pane with one job: the page owns the
//: split, the input and the toolbar, and sizes this pane; nothing here decides
//: layout. The mark is a sibling of (and behind) the scroller so it cannot steal
//: a click, and the scroller holds only what there is to read — the plot is the
//: page's sibling pane, never a child here (a long formula must not drag it).
Item {
    id: root

    objectName: "resultPane"

    //: The calculation backend's state, shown beside the result's copy actions.
    //: "busy" rather than "calculating…" keeps the row short enough for the
    //: split view's minimum width.
    readonly property string backendStatusText:
        calcVM.backendStatus === "calculating" ? qsTr("Backend: busy")
        : calcVM.backendStatus === "timedout" ? qsTr("Backend: timed out")
        : calcVM.backendStatus === "failed" ? qsTr("Backend: failed")
        : qsTr("Backend: ready")

    readonly property color backendStatusColor:
        calcVM.backendStatus === "timedout" || calcVM.backendStatus === "failed"
            ? Theme.currentTheme.colors.systemCriticalColor
            : calcVM.backendStatus === "calculating"
                ? Theme.currentTheme.colors.primaryColor
                : Theme.currentTheme.colors.textSecondaryColor

    //: The keyboard's Zen route lands the reader here: the outcome and the
    //: formula are what Zen exists to read, and the scroller is their owner.
    function focusResult() {
        resultScroll.forceActiveFocus()
    }

    //: The empty state's monogram: the app's Σ tinted into the theme's neutral,
    //: or one item of a user-configured pool rendered in the result's own style.
    Item {
        id: watermark

        objectName: "resultWatermark"

        //: The same emptiness the outcome line uses: a value or a failure means
        //: there is something to read, and the mark steps aside. (`resultText` is
        //: the plain outcome; a failure leaves it empty and sets `isError`.)
        readonly property bool empty:
            calcVM.resultText === "" && !calcVM.isError
        readonly property bool random:
            settingsVM.resultWatermark === "random"
        //: The random render arrives at the watermark's own fixed size; it is
        //: never blown up to the pane. Only a pool item bigger than the pane
        //: shrinks, and it keeps its aspect while doing so.
        readonly property real randomScale:
            !random
                || calcVM.watermarkWidth <= 0
                || calcVM.watermarkHeight <= 0
            ? 1
            : Math.min(1,
                       width / calcVM.watermarkWidth,
                       height / calcVM.watermarkHeight)

        anchors.fill: parent
        anchors.topMargin: resultHeaderRow.height + 12
        anchors.leftMargin: 24
        anchors.rightMargin: 24
        anchors.bottomMargin: 32
        visible: empty
        //: Both kinds are drawn in the same ink (the theme's text colour), so
        //: one fade here weights them alike.
        opacity: empty ? 0.2 : 0

        Behavior on opacity {
            NumberAnimation { duration: 150; easing.type: Easing.OutQuad }
        }

        Image {
            //: Both kinds are the viewmodel's artwork: the monogram tinted to
            //: the formula ink, or the rolled pool item rendered at a fixed size.
            anchors.centerIn: parent
            width: parent.random
                ? Math.round(calcVM.watermarkWidth * watermark.randomScale)
                : Math.min(Math.round(parent.width),
                           Math.round(parent.height * 0.6),
                           140)
            height: parent.random
                ? Math.round(calcVM.watermarkHeight * watermark.randomScale)
                : width
            fillMode: Image.PreserveAspectFit
            smooth: true
            sourceSize: Qt.size(
                Math.round(width * Screen.devicePixelRatio),
                Math.round(height * Screen.devicePixelRatio))
            source: calcVM.watermarkSvgUrl
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        //: The backend state belongs to the result it governs, so it sits above
        //: the result rather than in the page toolbar. The toolbar is the
        //: actions; this is the surface's own state.
        RowLayout {
            id: resultHeaderRow

            Layout.fillWidth: true
            Layout.preferredHeight: 32
            spacing: 6

            ProgressRing {
                visible: calcVM.backendBusy
                size: 14
                strokeWidth: 2
                //: RinUI's ring animation ignores `visible`; without this the
                //: idle result area keeps an invisible Canvas animating.
                indeterminate: visible
            }

            Text {
                text: root.backendStatusText
                typography: Typography.Caption
                color: root.backendStatusColor
            }

            Item { Layout.fillWidth: true }

            ToolButton {
                objectName: "resultCancelButton"
                visible: calcVM.backendBusy
                flat: true
                icon.name: "ic_fluent_stop_20_regular"
                icon.color: Theme.currentTheme.colors.systemCriticalColor
                Accessible.name: qsTr("Cancel calculation")
                Tip { text: qsTr("Cancel calculation") }
                onClicked: calcVM.cancelCalculation()
            }

            ToolButton {
                objectName: "resultCopyButton"
                flat: true
                icon.name: "ic_fluent_clipboard_letter_20_regular"
                icon.color: enabled
                    ? Theme.currentTheme.colors.textColor
                    : Theme.currentTheme.colors.textDisabledColor
                enabled: calcVM.resultText !== ""
                Accessible.name: qsTr("Copy result")
                Tip { text: qsTr("Copy result") }
                onClicked: vm.copyText(calcVM.resultText)
            }
            ToolButton {
                objectName: "resultCopyLatexButton"
                flat: true
                icon.name: "ic_fluent_clipboard_math_formula_20_regular"
                icon.color: enabled
                    ? Theme.currentTheme.colors.textColor
                    : Theme.currentTheme.colors.textDisabledColor
                enabled: calcVM.resultLatex !== ""
                Accessible.name: qsTr("Copy LaTeX")
                Tip { text: qsTr("Copy LaTeX") }
                onClicked: vm.copyText(calcVM.resultLatex)
            }
        }

        //: The scroller contains only what there is to read: the outcome, the
        //: formula and the alternative forms. The plot is the page's sibling
        //: pane, so scrolling a long answer cannot drag it away and the wheel
        //: over the plot is the plot's.
        Flickable {
            id: resultScroll

            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentHeight: resultColumn.implicitHeight

            ScrollBar.vertical: ScrollBar { }

            ColumnLayout {
                id: resultColumn

                width: resultScroll.width
                spacing: 12

                //: What there is to *read*, and the only place that says it: the
                //: value as markup in the code colours, a failure's prose, or the
                //: placeholder while nothing has been calculated. The formula
                //: below is the LaTeX's alone. Selectable — a result is something
                //: to copy out — but never editable, and borderless. It wraps
                //: instead of eliding (rich text ignores `elide`), which is why
                //: the viewmodel's unelided `highlighted` is the right call here.
                //:
                //: Living inside the scroll area rather than beside the copy
                //: buttons is what makes a long outcome scroll with the formula
                //: instead of pushing it out of the window. The same component
                //: the history cards use (see `CopyableLabel`).
                CopyableLabel {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    //: Height follows the text: the fixed 4.2-line box left a
                    //: band of empty space between the outcome and its formula,
                    //: which read as the LaTeX block's own top margin.
                    wrap: true
                    textFormat: isProse ? TextEdit.PlainText : TextEdit.RichText
                    readonly property bool isProse: calcVM.isError
                    readonly property bool hasResult: calcVM.resultText !== ""
                    color: isProse
                        ? Theme.currentTheme.colors.systemCriticalColor
                        : (hasResult
                            ? Theme.currentTheme.colors.textColor
                            : Theme.currentTheme.colors.textSecondaryColor)
                    text: isProse
                        ? calcVM.errorMessage
                        : (hasResult
                            ? (vm ? vm.highlighted(calcVM.resultText, Theme.isDark()) : "")
                            : qsTr("Press Ctrl+Return to calculate"))
                }

                //: The natural-height rendering, horizontally scrollable when it
                //: is wider than the panel (see `MathStrip`, including the room
                //: its overlay bar needs). The strip is only as tall as the
                //: artwork, so with nothing to render it takes no space at all.
                MathStrip {
                    Layout.fillWidth: true
                    //: The outcome line above is the gap; no second one.
                    paddingTop: 0

                    naturalWidth: calcVM.latexWidth
                    naturalHeight: calcVM.latexHeight
                    source: calcVM.latexSvgUrl
                }

                //: The alternative forms of the answer (N, expanded, factored, …),
                //: in the History card's own row anatomy. Empty and invisible when
                //: there is no different form worth showing.
                VariantsCard {
                    Layout.fillWidth: true
                    variants: calcVM.variants
                }
            }
        }
    }
}
