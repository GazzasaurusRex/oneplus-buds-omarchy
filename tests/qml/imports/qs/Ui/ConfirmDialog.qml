import QtQuick
Item {
  property bool opened: false
  property string message: ""
  property string cancelText: "Cancel"
  property string confirmText: "Confirm"
  property int selectedIndex: 1
  property color background: "transparent"
  property color foreground: "white"
  property color scrim: "transparent"
  property color selectedBackground: "transparent"
  property color selectedText: "transparent"
  property string fontFamily: ""
  property int cornerRadius: 0
  signal canceled()
  signal confirmed()
}
