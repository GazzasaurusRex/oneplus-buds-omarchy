import QtQuick
Item {
 property string text
 property bool selected
 property bool bordered
 property bool leftAlign
 property color foreground
 property color background
 property color accent
 property string fontFamily
 property bool focusable
 implicitHeight: 32
 signal clicked()
 Rectangle {
  anchors.fill: parent
  radius: 5
  color: parent.selected ? parent.accent : "#292a2e"
  border.color: parent.selected ? parent.accent : "#46474d"
 }
 Text {
  anchors.fill: parent
  anchors.leftMargin: 9
  text: parent.text
  color: parent.foreground
  font.family: parent.fontFamily
  font.pixelSize: 12
  verticalAlignment: Text.AlignVCenter
  horizontalAlignment: parent.leftAlign ? Text.AlignLeft : Text.AlignHCenter
  elide: Text.ElideRight
 }
 MouseArea { anchors.fill: parent; onClicked: parent.clicked() }
}
