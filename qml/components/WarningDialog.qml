import QtQuick
import RinUI

//: The app's one "a viewmodel refused something" dialog: a `MessageDialog` plus
//: the wiring to the viewmodel that reports it.
//:
//: `CalculatorViewModel` and `VariablesViewModel` both announce refusals the same
//: way (`warningOccurred(title, content)`), and both pages had the same three-line
//: `Connections` block copied into them. A refusal is not something a page should
//: have to remember to wire: it is one line here, and every page that can be
//: refused says only whose refusals it shows.
MessageDialog {
    id: root

    //: The viewmodel whose `warningOccurred(title, content)` opens this dialog.
    property QtObject source: null

    //: The signal carries its own title (a refused name is the title), so this is
    //: only what an empty-handed caller would see.
    title: qsTr("Warning")

    Connections {
        target: root.source

        function onWarningOccurred(title, content) {
            root.title = title
            root.body = content
            root.open()
        }
    }
}
