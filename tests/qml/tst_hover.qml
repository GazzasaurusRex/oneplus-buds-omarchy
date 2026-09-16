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
  property int reportRequests: 0
  property string reportPath: ""
  function eqStatus() { eqStatusCalls++; return nextId++ }
  function setEq(value) { return nextId++ }
  function setCustomEq(entryId, gains) {
   customRequest = ({entry_id: entryId, gains: gains}); return nextId++
  }
  function saveDiagnosticReport(path) { reportRequests++; reportPath = path; return nextId++ }
 }
 QtObject {
  id: host
  property bool vertical: false
  property int barSize: 26
  property color barForeground: "white"
  property color foreground: "white"
  property color background: "black"
  property string fontFamily: "sans-serif"
  property real panelAvailableWidth: 600
  property var shell: host
  function serviceFor(name) { return service }
  function showTooltip(item, text) {}
  function hideTooltip(item) {}
 }
 BarWidget { id: widget; bar: host; x: 200; y: 20; width: implicitWidth; height: implicitHeight }
 function init() {
  service.connection = "connected"
  service.snapshot = ({status:{model:"Test buds",battery:{left:{percentage:80},right:{percentage:60}}},
   anc_modes:[], capabilities:[], compatibility:"verified", session_connected:true})
  service.lastResponse = null
  service.eqStatusCalls = 0
  service.customRequest = null
  service.reportRequests = 0
  service.reportPath = ""
  host.panelAvailableWidth = 600
  widget.popupOpen = false
  widget.pendingRequestId = -1
  widget.pendingKind = ""
  widget.reportDetailsOpen = false
 }
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
  verify(widget.useTwoColumnLayout)
  compare(widget.eqPresets.length, 1)
  compare(widget.customEqEntries.length, 1)
  compare(widget.selectedCustom.bands.length, 2)
  verify(widget.reportActionShown)
  compare(widget.reportActionLabel, "Report a problem")
  verify(widget.panelHeight <= 510)
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
 function test_panel_falls_back_when_width_is_narrow() {
  service.snapshot = ({status:{model:"Test buds",battery:{}}, anc_modes:["off","on"],
   capabilities:["eq"], session_connected:true, eq_write_verified:true,
   eq:{current_id:0,current_name:"Hans Zimmer Soundscape Tuning",presets:[],custom_entries:[]}})
  host.panelAvailableWidth = 559
  tryCompare(widget, "useTwoColumnLayout", false)
  host.panelAvailableWidth = 600
  tryCompare(widget, "useTwoColumnLayout", true)
 }
 function test_compatibility_notice_states_and_bounds() {
  service.snapshot = ({status:{model:"OnePlus Buds Pro",product_id:"060C14",battery:{}},
   compatibility:"verified", anc_modes:["off","on"], capabilities:[], session_connected:true})
  widget.popupOpen = true
  compare(widget.experimentalDevice, false)
  compare(widget.communityTestedDevice, false)
  verify(!widget.compatibilityNoticeShown)
  verify(widget.reportActionShown)
  compare(widget.reportActionLabel, "Report a problem")

  service.snapshot = ({status:{model:"OnePlus Buds Pro 2",product_id:"062014",battery:{}},
   compatibility:"verified", anc_modes:["off","on"], capabilities:[], session_connected:true})
  wait(0)
  compare(widget.experimentalDevice, false)
  verify(!widget.compatibilityNoticeShown)
  verify(widget.reportActionShown)
  compare(widget.reportActionLabel, "Report a problem")

  service.snapshot = ({status:{model:null,product_id:"A1B2C3",battery:{}},
   compatibility:"experimental", anc_modes:[], capabilities:[], session_connected:false})
  wait(0)
  verify(widget.experimentalDevice)
  verify(widget.compatibilityNoticeShown)
  verify(widget.reportActionShown)
  compare(widget.reportActionLabel, "Report compatibility")
  verify(widget.panelHeight <= 560)

  service.snapshot = ({status:{model:"Community model",product_id:"C0FFEE",battery:{}},
   compatibility:"community_tested", anc_modes:[], capabilities:[], session_connected:false})
  wait(0)
  verify(widget.communityTestedDevice)
  verify(widget.compatibilityNoticeShown)
  verify(widget.reportActionShown)
  compare(widget.reportActionLabel, "Report a problem")
  verify(widget.panelHeight <= 560)
  widget.popupOpen = false
 }

 function test_all_compatibility_states_share_report_workflow() {
  var states = ["verified", "community_tested", "experimental"]
  for (var i = 0; i < states.length; i++) {
   service.snapshot = ({status:{model:"Test buds",product_id:"TEST",battery:{}},
    compatibility:states[i], anc_modes:[], capabilities:[], session_connected:true})
   wait(0)
   widget.saveDiagnosticReport("file:///tmp/report.txt")
   compare(widget.pendingKind, "diagnostic_report")
   widget.pendingRequestId = -1
   widget.pendingKind = ""
  }
  compare(service.reportRequests, 3)
 }

 function test_report_filename_and_submission_outcomes() {
  service.snapshot = ({status:{model:"OnePlus Buds Pro 2",product_id:"062014",battery:{}},
   compatibility:"verified", anc_modes:[], capabilities:[], session_connected:true})
  widget.popupOpen = true
  widget.reportDetailsOpen = true
  widget.prepareReportFileDialog()
  verify(widget.proposedReportFilename.length > 0)
  verify(/^oneplus-buds-pro-2-report-[0-9]{4}-[0-9]{2}-[0-9]{2}\.txt$/.test(
   widget.proposedReportFilename))
  verify(widget.reportDialogSelectedFile.endsWith("/" + widget.proposedReportFilename))

  widget.saveDiagnosticReport("file:///tmp/oneplus-buds-pro-2-report-2026-09-16.txt")
  var successId = widget.pendingRequestId
  compare(service.reportRequests, 1)
  compare(service.reportPath, "file:///tmp/oneplus-buds-pro-2-report-2026-09-16.txt")
  service.lastResponse = ({request_id:successId,ok:true,
   result:{saved:true,filename:"oneplus-buds-pro-2-report-2026-09-16.txt"}})
  wait(0)
  verify(widget.reportSaved)
  verify(findChild(widget, "reportSavedGuidance").visible)
  compare(widget.savedReportFilename, "oneplus-buds-pro-2-report-2026-09-16.txt")
  compare(widget.savedReportLocation, "/tmp/oneplus-buds-pro-2-report-2026-09-16.txt")
  verify(widget.reportIssueUrl.indexOf("template=compatibility.md") !== -1)
  verify(widget.reportIssueUrl.indexOf("report=") === -1)

  widget.prepareReportFileDialog()
  widget.cancelDiagnosticReport()
  verify(!widget.reportSaved)
  verify(!findChild(widget, "reportSavedGuidance").visible)
  compare(widget.savedReportFilename, "")

  widget.saveDiagnosticReport("file:///tmp/failed-report.txt")
  var failureId = widget.pendingRequestId
  service.lastResponse = ({request_id:failureId,ok:false,
   error:{message:"Diagnostic report could not be saved"}})
  wait(0)
  verify(!widget.reportSaved)
  verify(!findChild(widget, "reportSavedGuidance").visible)
  compare(widget.savedReportFilename, "")
  widget.popupOpen = false
 }
}
