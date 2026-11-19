import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import QmlMathPlot 2.0

//: The calculator's plot surface: the pane header (reset/zoom), a square
//: 1px-bordered surface around the plot, and the plot itself.
//:
//: The page owns where the pane goes (it is the split's other half) and assigns
//: its geometry; this component owns what the plot looks like and the Tab stop
//: around it. The plot object lives in the viewmodel (RinUI rebuilds a page on
//: every navigation), so this is a view of it and owns no state.
Item {
    id: root

    objectName: "plotPane"
    visible: calcVM.hasPlot
    //: Keep the PlotView's RHI surface alive while the page animates the panel
    //: out; `calcVM.hasPlot` is already false when the collapse starts, and a
    //: loader dropped immediately would remove the visible panel contents too.
    property bool keepAlive: false
    //: The PlotView only exists while there is something to draw. Its GPU/RHI
    //: resources are the expensive part of this pane, and an empty calculator
    //: must not pay for them.
    readonly property var plotViewItem: plotLoader.item

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
        height: 32
        spacing: 4

        Text {
            text: qsTr("Plot")
            typography: Typography.Caption
            color: Theme.currentTheme.colors.textSecondaryColor
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
            onClicked: root.plotViewItem.camera.reset()
        }
        ToolButton {
            objectName: "plotZoomOutButton"
            flat: true
            icon.name: "ic_fluent_zoom_out_20_regular"
            icon.color: enabled
                ? Theme.currentTheme.colors.textColor
                : Theme.currentTheme.colors.textDisabledColor
            enabled: calcVM.hasPlot && root.plotViewItem
                && root.plotViewItem.camera.zoomEnabled
            Accessible.name: qsTr("Zoom out")
            Tip { text: qsTr("Zoom out") }
            onClicked: root.plotViewItem.camera.animate_zoom(
                -120, 0.5, 0.5, root.plotViewItem.width,
                root.plotViewItem.height, 160)
        }
        ToolButton {
            objectName: "plotZoomInButton"
            flat: true
            icon.name: "ic_fluent_zoom_in_20_regular"
            icon.color: enabled
                ? Theme.currentTheme.colors.textColor
                : Theme.currentTheme.colors.textDisabledColor
            enabled: calcVM.hasPlot && root.plotViewItem
                && root.plotViewItem.camera.zoomEnabled
            Accessible.name: qsTr("Zoom in")
            Tip { text: qsTr("Zoom in") }
            onClicked: root.plotViewItem.camera.animate_zoom(
                120, 0.5, 0.5, root.plotViewItem.width,
                root.plotViewItem.height, 160)
        }
    }

    //: The focus ring draws two pixels outside its control, so the left edge
    //: keeps a 3px gutter from the result/plot splitter. The right and bottom
    //: use the page's content inset instead (see `rightMargin`/`bottomMargin`),
    //: which leaves the ring room without an extra gutter.
    Control {
        id: plotFrame

        objectName: "plotFrame"

        anchors.top: plotToolbar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 3
        anchors.topMargin: 8
        //: The card's right and bottom sit on the same content inset as the
        //: result text and the copy buttons (16), so those two gaps read as one
        //: rectangle. The 3px gutter stays only on the left, where the
        //: result/plot splitter has no page margin for the focus ring to use.
        anchors.rightMargin: 0
        anchors.bottomMargin: Spacing.content

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
        //: The card is square; the one-pixel border is the only chrome. Inset
        //: the plot by the border width so the canvas cannot paint over it.
        padding: Theme.currentTheme.appearance.borderWidth
        Keys.forwardTo: root.plotViewItem ? [root.plotViewItem] : []

        background: Rectangle {
            objectName: "plotCard"

            color: "transparent"
            border.width: Theme.currentTheme.appearance.borderWidth
            border.color: Theme.currentTheme.colors.cardBorderColor
        }

        onActiveFocusChanged: {
            if (activeFocus)
                return
            if (!root.plotViewItem)
                return
            //: The plot never loses focus itself (the keys are forwarded), so a
            //: held arrow key would keep panning. qmlmathplot drops held keys
            //: when the camera stops accepting them; these two toggles are that,
            //: through public API.
            const camera = root.plotViewItem.camera
            const pan = camera.panEnabled
            const zoom = camera.zoomEnabled
            camera.panEnabled = false
            camera.panEnabled = pan
            camera.zoomEnabled = false
            camera.zoomEnabled = zoom
        }

        Rectangle {
            anchors.fill: parent
            anchors.margins: plotFrame.padding
            color: "transparent"

            //: The plot handles the mouse and the forwarded keys; the control
            //: above owns the Tab stop. The Loader owns its GPU/RHI lifetime.
            Loader {
                id: plotLoader
                anchors.fill: parent
                active: calcVM.hasPlot || root.keepAlive

                sourceComponent: Component {
                    PlotView {
                        objectName: "plotView"
                        anchors.fill: parent
                        plot: calcVM.plot
                        //: Not the Tab stop: the control above is, so the
                        //: ring has one owner. A click still focuses the
                        //: plot (PlotInput forces it), which is the mouse
                        //: path the ring ignores.
                        focus: false
                        activeFocusOnTab: false
                    }
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

        //: The ring every other control raises, with the same rule: `visualFocus`
        //: and a Tab/Backtab focus reason (see `FocusIndicator`).
        ProjectFocusIndicator {
            objectName: "plotFocusIndicator"
            control: plotFrame
        }
    }
}
