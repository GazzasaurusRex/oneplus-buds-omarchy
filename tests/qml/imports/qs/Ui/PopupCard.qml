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
 visible: false
}
