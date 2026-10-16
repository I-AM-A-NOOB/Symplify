import QtQuick
import QtQuick.Layouts
import RinUI

//: The app's one message box: a title, a wrapped body, and the buttons.
//:
//: Four dialogs used to spell out the same fourteen lines for themselves —
//: `standardButtons: Dialog.Ok`, then a `Text` in `Typography.Body` at the
//: theme's ink, wrapping, 320px wide — so the body's width, face and colour were
//: decided in four places, and the width was even passed in once (the Variables
//: page's `panelWidth`, which is that page's details panel and only happens to be
//: the same number).
//:
//: What actually differs between the four is the title, the words, and (once) an
//: extra Cancel — all of which a caller sets. The prose stays a fixed width on
//: purpose: it is a sentence or two, and the dialog sizes itself around it.
Dialog {
    id: root

    //: For a harness that has to find the open dialog (the app's other probe hooks
    //: exist for the same reason).
    objectName: "messageDialog"

    //: The dialog's prose.
    property string body: ""

    //: Width of the prose. One number, in one place.
    property int bodyWidth: 320

    standardButtons: Dialog.Ok

    Text {
        Layout.fillWidth: true
        width: root.bodyWidth
        wrapMode: Text.WordWrap
        typography: Typography.Body
        color: Theme.currentTheme.colors.textColor
        text: root.body
    }
}
