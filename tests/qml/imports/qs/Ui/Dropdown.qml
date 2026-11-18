import QtQuick

// Shell UI stub, like Button/PanelSlider. Selection follows Dropdown's
// public API, including its assignment before emitting changed.
Item {
 property var options: []
 property string value: ""
 property bool showLabel: true
 property color foreground: "white"
 property string fontFamily: "sans-serif"
 property int rowHeight: 32
 implicitHeight: rowHeight
 signal changed(string value)
 function currentLabel() {
  for (var i = 0; i < options.length; i++)
   if (String(options[i].value) === value) return options[i].label
  return value
 }
 function select(value) {
  this.value = String(value)
  changed(this.value)
 }
}
