import QtQuick
import QtTest
TestCase {
 name: "BatteryHover"
 width: 600; height: 100; visible: true
 when: windowShown
 QtObject {
  id: service
  property string connection: "connected"
  property var snapshot: ({status:{model:"Test buds",battery:{left:{percentage:80},right:{percentage:60}}},anc_modes:[]})
  property var lastResponse: null
 }
 QtObject {
  id: host
  property bool vertical: false
  property int barSize: 26
  property color barForeground: "white"
  property color foreground: "white"
  property color background: "black"
  property string fontFamily: "sans-serif"
  property var shell: host
  function serviceFor(name) { return service }
  function showTooltip(item, text) {}
  function hideTooltip(item) {}
 }
 BarWidget { id: widget; bar: host; x: 200; y: 20; width: implicitWidth; height: implicitHeight }
 function test_hover() {
  mouseMove(widget, -100, 50)
  wait(220)
  var compact = widget.width
  verify(!widget.batteryExpanded)
  mouseMove(widget, compact / 2, 13)
  tryCompare(widget, "batteryExpanded", true)
  wait(220)
  verify(widget.width > compact + 50)
  var expanded = widget.width
  mouseMove(widget, expanded - 3, 13)
  verify(widget.batteryExpanded)
  mouseClick(widget, expanded - 3, 13)
  verify(widget.popupOpen)
  mouseMove(widget, -100, 50)
  wait(550)
  compare(widget.width, expanded)
  widget.close()
  wait(150)
  verify(widget.batteryExpanded)
  wait(450)
  compare(widget.width, compact)
  mouseMove(widget, compact / 2, 13)
  wait(220)
  mouseMove(widget, -100, 50)
  wait(150)
  verify(widget.batteryExpanded)
  mouseMove(widget, compact / 2, 13)
  wait(350)
  verify(widget.batteryExpanded)
  service.snapshot = {status:{battery:{case:{percentage:55}}},anc_modes:[]}
  wait(220)
  verify(widget.width > compact)
  verify(widget.width < expanded)
  service.connection = "disconnected"
  wait(220)
  verify(Math.abs(widget.width - compact) < 3)
  verify(!widget.batteryExpanded)
  service.connection = "connected"
  service.snapshot = {status:{battery:{}},anc_modes:[]}
  wait(220)
  compare(widget.width, compact)
 }
}
