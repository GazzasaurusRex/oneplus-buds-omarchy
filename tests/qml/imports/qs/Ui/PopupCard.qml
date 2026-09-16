import QtQuick
Item {
 property var anchorItem
 property var bar
 property var owner
 property bool open
 property int contentWidth
 property int contentHeight
 property real availableCardWidth: bar && bar.panelAvailableWidth
   ? bar.panelAvailableWidth : 600
 function fittedContentWidth(n) { return Math.min(n, availableCardWidth) }
 function fittedContentHeight(n) { return n }
 width: contentWidth
 height: contentHeight
 x: anchorItem ? anchorItem.width - width : 0
 y: anchorItem ? anchorItem.height + 8 : 0
 visible: open
 Rectangle {
  anchors.fill: parent
  z: -1
  radius: 10
  color: "#202124"
  border.color: "#414247"
 }
}
