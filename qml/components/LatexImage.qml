import QtQuick 2.15
import QtQuick.Window 2.15

// An SVG image rendered crisp at the display's pixel density: the item
// keeps the artwork's logical size while the render resolution
// (sourceSize) is scaled by devicePixelRatio. Left-aligned by default.
Image {
    id: root

    // Natural (logical) size of the artwork.
    property int naturalWidth: 0
    property int naturalHeight: 0

    smooth: true
    fillMode: Image.PreserveAspectFit
    width: naturalWidth
    height: naturalHeight
    sourceSize: Qt.size(
        naturalWidth * Screen.devicePixelRatio,
        naturalHeight * Screen.devicePixelRatio)
}
