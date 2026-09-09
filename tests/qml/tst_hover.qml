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
  property int nextId: 1
  property int eqStatusCalls: 0
  property var customRequest: null
  function eqStatus() { eqStatusCalls++; return nextId++ }
  function setEq(value) { return nextId++ }
  function setCustomEq(entryId, gains) {
   customRequest = ({entry_id: entryId, gains: gains}); return nextId++
  }
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
 function test_native_eq_panel_is_capability_driven() {
  service.snapshot = ({
   status:{model:"Test buds",battery:{left:{percentage:80},right:{percentage:60}}},
   anc_modes:[], capabilities:["eq"], session_connected:true,
   eq_write_verified:true, custom_eq_write_verified:true,
   eq:{current_id:4,current_name:"Custom",gain_step_db:1,
    presets:[{id:0,key:"balanced",name:"Balanced"}],
    custom_entries:[{eq_id:4,name:"Custom",min_gain_db:-6,max_gain_db:6,
     bands:[{frequency_hz:62,gain_db:3},{frequency_hz:250,gain_db:1}]}]}
  })
  widget.popupOpen = true
  tryCompare(service, "eqStatusCalls", 1)
  compare(widget.eqPresets.length, 1)
  compare(widget.customEqEntries.length, 1)
  compare(widget.selectedCustom.bands.length, 2)
  service.lastResponse = ({request_id:widget.pendingRequestId,ok:true,result:service.snapshot.eq})
  wait(0)
  service.snapshot.eq.custom_entries.push({eq_id:5,name:"Custom1",min_gain_db:-6,max_gain_db:6,
   bands:[{frequency_hz:62,gain_db:0},{frequency_hz:250,gain_db:0}]})
  service.snapshot = JSON.parse(JSON.stringify(service.snapshot))
  wait(0)
  widget.selectCustomSlot(1)
  compare(widget.selectedCustom.eq_id, 5)
  service.snapshot = JSON.parse(JSON.stringify(service.snapshot))
  wait(0)
  compare(widget.selectedCustom.eq_id, 5)
  widget.applyCustomEq()
  verify(service.customRequest !== null)
  compare(service.customRequest.entry_id, 5)
  compare(service.customRequest.gains.join(","), "0,0")
  widget.pendingRequestId = -1
  widget.popupOpen = false
 }
}
