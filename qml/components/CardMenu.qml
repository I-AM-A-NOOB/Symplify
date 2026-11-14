import QtQuick
import RinUI

//: The app's card context menu: RinUI's `Menu` plus the one gesture rule both
//: card kinds need.
//:
//: RinUI's `Menu` drives `x`/`y` from `posX`/`posY` through its `enter`
//: transition, so setting those on an *open* menu moves nothing: measured, a
//: second right-click at a new point left the menu where the first had put it,
//: and a third moved it off the window. Every gesture therefore closes what is
//: open and opens again, and the re-open waits for `onClosed`: a popup keeps
//: `visible` until its exit transition ends, so `popup()` immediately after
//: `close()` is silently swallowed (measured: the menu stayed closed).
//:
//: `target` is whatever the caller's items act on — a History card reads its
//: own properties, a variant row reads the row's `modelData`. The caller
//: declares the `MenuItem`s; this only owns position, target and re-open.
Menu {
    id: root

    //: The row the items act on (a History card, a variant row's modelData).
    property var target: null

    //: A re-open gesture waiting for the close to finish. Non-null only for a
    //: re-open, so a close by clicking outside leaves it alone.
    property var pendingPoint: null

    //: Open at `point`, in this menu's parent coordinates.
    function openAt(value, point) {
        target = value
        if (visible) {
            pendingPoint = point
            close()
            return
        }
        posX = point.x
        posY = point.y
        popup()
    }

    //: Open centred under `row` (which lives in `host`), for the keyboard routes
    //: that have no pointer.
    function openBelow(host, row, value) {
        openAt(value, host.mapFromItem(row,
                                       (row.width - width) / 2,
                                       row.height + 5))
    }

    onClosed: {
        if (pendingPoint) {
            const point = pendingPoint
            pendingPoint = null
            openAt(target, point)
        }
    }
}
