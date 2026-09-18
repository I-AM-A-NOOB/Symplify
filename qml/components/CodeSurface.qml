import QtQuick
import Qt5Compat.GraphicalEffects
import RinUI

// The box a code input sits in, painted in the *code* theme's own surface colour
// rather than the UI theme's — Solarized Light's cream, One Dark's #282c34.
//
// It replaces `background:` rather than tinting RinUI's, because a background is a
// whole component and not a colour: keeping the chrome it draws means drawing it
// here. This is RinUI's `TextArea` background (components/Text/TextArea.qml) —
// rounded to `buttonRadius`, bordered, with the accent underline while focused,
// clipped to the rounding through an OpacityMask — with the two colours swapped.
//
// `settingsVM.codeSurface(dark)` answers "" when the family has no opinion (High
// Contrast Light states neither an `editor.background` nor an `editor.foreground`),
// and the UI theme's own surface colour stands in. Same rule as the bracket
// palette: absence is not a value.
Rectangle {
    id: root

    // Bound by the caller: the background cannot see the control's `activeFocus`,
    // and the focus belongs to the text item inside it, not to the scroll view.
    property bool focused: false

    readonly property var colors: Theme.currentTheme.colors
    readonly property var appearance: Theme.currentTheme.appearance

    anchors.fill: parent
    radius: appearance.buttonRadius
    color: settingsVM.codeSurface(Theme.isDark()).background || colors.controlColor
    clip: true
    border.width: appearance.borderWidth
    border.color: colors.controlBorderColor

    layer.enabled: true
    layer.smooth: false
    layer.mipmap: false
    layer.effect: OpacityMask {
        maskSource: Rectangle {
            width: root.width
            height: root.height
            radius: root.radius
        }
    }

    // Bottom indicator: the accent while focused, the border colour otherwise —
    // RinUI's own transition, so the box still reads as a focused field.
    Rectangle {
        width: parent.width
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        radius: 999
        height: root.focused
            ? root.appearance.borderWidth * 2
            : root.appearance.borderWidth
        color: root.focused ? root.colors.primaryColor : root.colors.textControlBorderColor

        Behavior on color { ColorAnimation { duration: Utils.animationSpeed; easing.type: Easing.OutQuint } }
        Behavior on height { NumberAnimation { duration: Utils.animationSpeed; easing.type: Easing.OutQuint } }
    }
}
