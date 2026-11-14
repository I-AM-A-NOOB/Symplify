import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import QmlMathPlot 2.0
import Qt5Compat.GraphicalEffects

//: The calculator's plot surface: the pane header (reset/zoom), the frame with
//: its rounded mask, and the plot itself.
//:
//: The page owns where the pane goes (it is the split's other half) and assigns
//: its geometry; this component owns what the plot looks like and the Tab stop
//: around it. The plot object lives in the viewmodel (RinUI rebuilds a page on
//: every navigation), so this is a view of it and owns no state.
Item {
    id: root

    objectName: "plotPane"
    visible: calcVM.hasPlot

    //: Plot actions live in the pane header, outside the drawing surface.
    //: Overlaying them on the canvas hid the plot's own furniture (axis labels,
    //: cursor read-outs) and made the toolbar collide with the graph instead of
    //: framing it.
    RowLayout {
        id: plotToolbar

        objectName: "plotToolbar"

        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: 3
        height: 32
        spacing: 4

        Text {
            text: qsTr("Plot")
            typography: Typography.Caption
            color: Theme.currentTheme.colors.textSecondaryColor
            Layout.leftMargin: 4
        }

        Item { Layout.fillWidth: true }

        ToolButton {
            objectName: "plotResetButton"
            flat: true
            icon.name: "ic_fluent_arrow_reset_20_regular"
            icon.color: enabled
                ? Theme.currentTheme.colors.textColor
                : Theme.currentTheme.colors.textDisabledColor
            enabled: calcVM.hasPlot
            Accessible.name: qsTr("Reset plot view")
            Tip { text: qsTr("Reset plot view") }
            onClicked: plotView.camera.reset()
        }
        ToolButton {
            objectName: "plotZoomOutButton"
            flat: true
            icon.name: "ic_fluent_zoom_out_20_regular"
            icon.color: enabled
                ? Theme.currentTheme.colors.textColor
                : Theme.currentTheme.colors.textDisabledColor
            enabled: calcVM.hasPlot && plotView.camera.zoomEnabled
            Accessible.name: qsTr("Zoom out")
            Tip { text: qsTr("Zoom out") }
            onClicked: plotView.camera.animate_zoom(
                -120, 0.5, 0.5, plotView.width, plotView.height, 160)
        }
        ToolButton {
            objectName: "plotZoomInButton"
            flat: true
            icon.name: "ic_fluent_zoom_in_20_regular"
            icon.color: enabled
                ? Theme.currentTheme.colors.textColor
                : Theme.currentTheme.colors.textDisabledColor
            enabled: calcVM.hasPlot && plotView.camera.zoomEnabled
            Accessible.name: qsTr("Zoom in")
            Tip { text: qsTr("Zoom in") }
            onClicked: plotView.camera.animate_zoom(
                120, 0.5, 0.5, plotView.width, plotView.height, 160)
        }
    }

    //: The focus ring draws two pixels outside its control, so three pixels of
    //: gutter keep it whole in the split pane.
    Control {
        id: plotFrame

        objectName: "plotFrame"

        anchors.top: plotToolbar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 3
        anchors.topMargin: 0

        //: The same focus arrangement the Segmented items use: a Control is the
        //: Tab stop, so the shared ring can read `visualFocus`/`focusReason` and
        //: appears for Tab/Backtab only. A click lands on the plot itself
        //: (PlotInput focuses it), which leaves this control unfocused and the
        //: ring hidden — exactly what a click does to a button. Keys are
        //: forwarded so both routes drive it.
        focus: true
        activeFocusOnTab: true
        //: Qt Quick Controls took the tab chain over from `activeFocusOnTab`
        //: (6.5): a Control's own `focusPolicy` decides, and NoFocus is its
        //: default.
        focusPolicy: Qt.StrongFocus
        Keys.forwardTo: [plotView]

        onActiveFocusChanged: {
            if (activeFocus)
                return
            //: The plot never loses focus itself (the keys are forwarded), so a
            //: held arrow key would keep panning. qmlmathplot drops held keys
            //: when the camera stops accepting them; these two toggles are that,
            //: through public API.
            const camera = plotView.camera
            const pan = camera.panEnabled
            const zoom = camera.zoomEnabled
            camera.panEnabled = false
            camera.panEnabled = pan
            camera.zoomEnabled = false
            camera.zoomEnabled = zoom
        }

        Rectangle {
            anchors.fill: parent
            //: The graph is the surface, not a card inside a card.
            color: "transparent"

            //: Qt's `clip` is rectangular, so `clip: true` would let the plot's
            //: square canvas paint over this card's rounded corners. The contents
            //: are rendered into a layer and masked with a rounded rectangle
            //: instead.
            Item {
                anchors.fill: parent
                layer.enabled: true
                layer.effect: OpacityMask {
                    maskSource: plotMask
                }

                //: The plot handles the mouse and the forwarded keys; the control
                //: above owns the Tab stop.
                PlotView {
                    id: plotView

                    objectName: "plotView"
                    anchors.fill: parent
                    plot: calcVM.plot
                    //: Not the Tab stop: the control above is, so the ring has
                    //: one owner. A click still focuses the plot (PlotInput
                    //: forces it), which is the mouse path the ring ignores.
                    focus: false
                    activeFocusOnTab: false
                }
            }

            //: A shader bake can refuse an expression (an unsupported function, a
            //: level set too hard for the per-pixel model). The plot must say so
            //: where the plot is, not only in the log.
            Text {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 10
                visible: calcVM.plotError !== ""
                text: calcVM.plotError
                elide: Text.ElideRight
                color: Theme.currentTheme.colors.systemCriticalColor
                typography: Typography.Caption
            }
        }

        //: The mask is outside the masked item (an effect may not include
        //: itself) and never shown: the effect renders it offscreen and reads its
        //: alpha.
        Rectangle {
            id: plotMask

            objectName: "plotMask"
            anchors.fill: parent
            radius: Theme.currentTheme.appearance.buttonRadius
            visible: false
        }

        //: The ring every other control raises, with the same rule: `visualFocus`
        //: and a Tab/Backtab focus reason (see `FocusIndicator`).
        ProjectFocusIndicator {
            objectName: "plotFocusIndicator"
            control: plotFrame
        }
    }
}
