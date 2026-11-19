pragma Singleton
import QtQuick

//: The app's layout scale, in logical pixels.
//:
//: One vocabulary for every page and region, so a page does not decide its own
//: inset and two pages do not drift apart:
//: * `header` — the page title and its actions. The only place 24 is used.
//: * `content` — the page body / workspace under that title.
//: * `pane` — a panel inside the content (the variables details sidebar).
//: * `control` — padding inside a pane/control row (code input, result header).
//: * `tight` — air between siblings inside one control.
//:
//: `PageScaffold` takes `header` for its title bar and `content` for the body;
//: the Calculator's toolbar takes `header` while its workspace takes `content`.
QtObject {
    readonly property int header: 24
    readonly property int content: 16
    readonly property int pane: 12
    readonly property int control: 8
    readonly property int tight: 4
}
