import QtQuick 2.15
import RinUI

// Horizontal-only scroll container: touch pans natively; the mouse wheel
// does not scroll it (native Qt Quick behavior). The scrollbar appears
// only when the content is wider than the viewport.
Flickable {
    clip: true
    flickableDirection: Flickable.HorizontalFlick
    contentHeight: height

    ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }
}
