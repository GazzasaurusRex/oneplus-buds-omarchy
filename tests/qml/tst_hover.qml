import QtQuick
import QtTest
import "BarModel.js" as BarModel
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
  property var customRequests: []
  property var profileRequests: []
  property int reportRequests: 0
  property string reportPath: ""
  property var touchRequest: null
  property var holdCycleRequest: null
  property var findRequests: []
  property var findDeviceIds: []
  property var queuedRequests: []
  property var featureRequests: []
  function setFeatureSwitch(feature, enabled) {
   featureRequests = featureRequests.concat([{feature:feature, enabled:enabled}])
   return nextId++
  }
  function request(command, params) {
   queuedRequests = queuedRequests.concat([{command:command, parameters:params}])
   if (command === "eq_status") return eqStatus()
   return nextId++
  }
  function setTouchControl(side, action, value) {
   touchRequest = {side:side, action:action, function:value}; return nextId++
  }
  function setHoldCycle(modes) {
   holdCycleRequest = modes.slice(); return nextId++
  }
  function findEarbuds(ringing, deviceId) {
   findRequests = findRequests.concat([ringing])
   findDeviceIds = findDeviceIds.concat([deviceId || ""])
   return nextId++
  }
  function eqStatus() { eqStatusCalls++; return nextId++ }
  function setEq(value) { return nextId++ }
  function setCustomEq(entryId, gains, deviceId) {
   customRequest = ({entry_id: entryId, gains: gains, device_id:deviceId || ""})
   customRequests = customRequests.concat([customRequest]); return nextId++
  }
  function createCustomEq(name, deviceId) {
   profileRequests = profileRequests.concat([{action:"create", name:name, device_id:deviceId || ""}])
   return nextId++
  }
  function renameCustomEq(entryId, name, deviceId) {
   profileRequests = profileRequests.concat([{action:"rename", entry_id:entryId,
     name:name, device_id:deviceId || ""}])
   return nextId++
  }
  function deleteCustomEq(entryId, deviceId) {
   profileRequests = profileRequests.concat([{action:"delete", entry_id:entryId,
     device_id:deviceId || ""}])
   return nextId++
  }
  function saveDiagnosticReport(path) { reportRequests++; reportPath = path; return nextId++ }
  property string ancRequest: ""
  function setAnc(value) { ancRequest = value; return nextId++ }
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
 Component { id: anotherWidget; BarWidget { bar: host } }
 function test_features_use_model_labels_and_hide_unadvertised_raw_switches() {
  var features = BarModel.featureList({
   feature_switches:{multipoint:true, wear_detection:true, low_latency:false,
    game_equalizer:true, high_quality_audio:false, hearing_enhancement:false,
    spatial_sound:false},
   feature_labels:{multipoint:"Dual connection", wear_detection:"Auto play/pause",
    high_quality_audio:"Hi-Res mode"}, writable_features:[]})
  compare(features.length, 3)
  compare(features[0].label, "Auto play/pause")
  compare(features[1].label, "Dual connection")
  compare(features[2].label, "Hi-Res mode")
  verify(!features[0].writable)
  compare(BarModel.featureList({feature_switches:{low_latency:false}}).length, 1)
 }
 function init() {
  service.connection = "connected"
  service.snapshot = ({status:{model:"Test buds",battery:{left:{percentage:80},right:{percentage:60}}},
   anc_modes:[], capabilities:[], compatibility:"verified", session_connected:true})
  service.lastResponse = null
  service.eqStatusCalls = 0
  service.ancRequest = ""
  service.customRequest = null
  service.customRequests = []
   service.profileRequests = []
  service.reportRequests = 0
  service.reportPath = ""
  service.touchRequest = null
  service.holdCycleRequest = null
  service.findRequests = []
  service.findDeviceIds = []
  service.queuedRequests = []
  service.featureRequests = []
  widget.panelQueue = []
  host.panelAvailableWidth = 600
  widget.popupOpen = false
  widget.pendingRequestId = -1
  widget.pendingKind = ""
  widget.reportDetailsOpen = false
 }
 function touchSnapshot() {
  return {status:{model:"Nord", battery:{}}, anc_modes:[],
   capabilities:["touch_controls"], session_connected:true, compatibility:"verified",
   touch_controls:[
    {side:1,button:1,action:2,action_label:"Double tap",function:6,function_label:"Next track",
     writable:true,options:[{value:0,label:"None"},{value:5,label:"Previous track"},{value:6,label:"Next track"}]},
    {side:2,button:1,action:2,action_label:"Double tap",function:254,function_label:"Unknown (254)",
     writable:true,options:[{value:0,label:"None"},{value:6,label:"Next track"}]},
    {side:1,button:1,action:4,action_label:"Touch & hold",function:8,function_label:"Switch noise control",
     writable:false,options:[]}]}
 }
 function findSnapshot(state) {
  return {status:{model:"Nord",battery:{}},anc_modes:[],
   capabilities:["find_earbuds"],session_connected:true,compatibility:"verified",
   find_state:state,find_device_id:"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
 }
 function test_auto_play_pause_waits_for_readback_and_explains_function_on_hover() {
  var state = findSnapshot("stopped")
  state.capabilities = ["feature_switches"]
  state.feature_switches = {wear_detection:false, high_quality_audio:false}
  state.feature_labels = {wear_detection:"Auto play/pause", high_quality_audio:"Hi-Res mode"}
  state.writable_features = ["wear_detection"]
  service.snapshot = state
  widget.popupOpen = true
  while (widget.pendingRequestId >= 0)
   service.lastResponse = {request_id:widget.pendingRequestId,ok:true,result:{}}
  wait(0)
  var toggle = findChild(widget, "featureToggle_wear_detection")
  verify(toggle !== null)
  verify(toggle.enabled && toggle.interactive && !toggle.checked)
  var row = findChild(widget, "featureRow_wear_detection")
  verify(row.tooltipText.indexOf("pause") !== -1 && row.tooltipText.indexOf("resume") !== -1)
  toggle.toggled()
  compare(service.featureRequests, [{feature:"wear_detection",enabled:true}])
  verify(!toggle.checked && !toggle.enabled)
  var confirmed = JSON.parse(JSON.stringify(state))
  confirmed.feature_switches.wear_detection = true
  service.snapshot = confirmed
  service.lastResponse = {request_id:widget.pendingRequestId,ok:true,result:{verified:true,set_status:0}}
  wait(0)
  toggle = findChild(widget, "featureToggle_wear_detection")
  verify(toggle.checked && toggle.enabled)
  toggle.toggled()
  service.lastResponse = {request_id:widget.pendingRequestId,ok:true,result:{verified:false,set_status:14}}
  wait(0)
  verify(toggle.checked)
  verify(widget.outcome.indexOf("not confirmed") !== -1)
  verify(!findChild(widget, "featureToggle_high_quality_audio").enabled)
  service.connection = "disconnected"
  verify(!toggle.enabled)
 }
 function test_remaining_feature_controls_data() {
  return [{tag:"camera",name:"click_to_take_photo",label:"Camera control",keyword:"camera"},
   {tag:"dual",name:"multipoint",label:"Dual connection",keyword:"two devices"},
   {tag:"hires",name:"high_quality_audio",label:"Hi-Res mode",keyword:"disconnect"}]
 }
 function test_remaining_feature_controls(data) {
  var state = findSnapshot("stopped")
  state.capabilities = ["feature_switches"]
  state.feature_switches = {}; state.feature_switches[data.name] = false
  state.feature_labels = {}; state.feature_labels[data.name] = data.label
  state.writable_features = [data.name]
  service.snapshot = state
  widget.popupOpen = true
  while (widget.pendingRequestId >= 0)
   service.lastResponse = {request_id:widget.pendingRequestId,ok:true,result:{}}
  wait(0)
  var row = findChild(widget,"featureRow_" + data.name)
  verify(row.tooltipText.indexOf(data.keyword) !== -1)
  for (var i = 0; i < 2; ++i) {
   var target = i === 0
   var toggle = findChild(widget,"featureToggle_" + data.name)
   verify(toggle.enabled && toggle.interactive)
   compare(toggle.checked,!target)
   toggle.toggled()
   verify(!toggle.enabled)
   compare(toggle.checked,!target)
   compare(service.featureRequests[i],{feature:data.name,enabled:target})
   var confirmed = JSON.parse(JSON.stringify(state))
   confirmed.feature_switches[data.name] = target
   service.snapshot = confirmed
   service.lastResponse = {request_id:widget.pendingRequestId,ok:true,result:{verified:true,set_status:0}}
   wait(0)
   toggle = findChild(widget,"featureToggle_" + data.name)
   verify(toggle.enabled)
   compare(toggle.checked,target)
  }
 }
 function test_find_play_stop_follow_confirmed_state_and_handle_rejection() {
  service.snapshot = findSnapshot("stopped")
  widget.popupOpen = true
  var button = findChild(widget, "findEarbudsButton")
  verify(button !== null)
  var hint = findChild(widget, "findEarbudsHint")
  verify(!hint.visible)
  verify(button.tooltipText.indexOf("Remove earbuds") !== -1)
  compare(findChild(widget, "findEarbudsIcon").text, "▶")
  button.clicked()
  compare(service.findRequests, [true])
  verify(!widget.finding)
  verify(!button.enabled)
  service.snapshot = findSnapshot("ringing")
  service.lastResponse = {request_id:widget.pendingRequestId,ok:true,
   result:{acknowledged:true,state:"ringing"}}
  wait(0)
  verify(widget.finding && button.enabled)
  compare(button.text, "Stop")
  compare(findChild(widget, "findEarbudsIcon").text, "■")
  compare(button.tooltipText, "")
  button.clicked()
  compare(service.findRequests, [true,false])
  service.snapshot = findSnapshot("unknown")
  service.lastResponse = {request_id:widget.pendingRequestId,ok:true,
   result:{acknowledged:false,state:"unknown",set_status:14}}
  wait(0)
  compare(button.text, "Stop")
  compare(findChild(widget, "findEarbudsIcon").text, "■")
  verify(widget.outcome.indexOf("not confirmed") !== -1)
  verify(hint.text.indexOf("unknown") !== -1)
  button.clicked()
  service.snapshot = findSnapshot("stopped")
  service.lastResponse = {request_id:widget.pendingRequestId,ok:true,
   result:{acknowledged:true,state:"stopped"}}
  wait(0)
  verify(!widget.finding)
  compare(findChild(widget, "findEarbudsIcon").text, "▶")
 }
 function test_find_unknown_start_and_panel_close_keep_stop_available() {
  service.snapshot = findSnapshot("stopped")
  widget.popupOpen = true
  findChild(widget, "findEarbudsButton").clicked()
  service.snapshot = findSnapshot("unknown")
  service.lastResponse = {request_id:widget.pendingRequestId,ok:true,
   result:{acknowledged:false,state:"unknown",set_status:null}}
  wait(0)
  verify(widget.finding)
  widget.close()
  compare(service.findRequests, [true,false])
  verify(widget.finding) // closing cannot establish remote silence
  service.snapshot = findSnapshot("stopped")
  verify(!widget.finding)
 }
 function test_find_close_during_start_queues_stop_and_reopen_uses_shared_state() {
  service.snapshot = findSnapshot("stopped")
  widget.popupOpen = true
  findChild(widget, "findEarbudsButton").clicked()
  widget.close()
  compare(service.findRequests, [true,false])
  service.lastResponse = {request_id:widget.pendingRequestId,ok:true,
   result:{acknowledged:true,state:"ringing"}}
  service.snapshot = findSnapshot("ringing")
  widget.popupOpen = true
  compare(findChild(widget, "findEarbudsButton").text, "Stop")
  compare(findChild(widget, "findEarbudsIcon").text, "■")
  service.connection = "disconnected"
  verify(!findChild(widget, "findEarbudsButton").enabled)
 }
 function test_find_shared_state_expiry_and_destroyed_open_panel() {
  service.snapshot = findSnapshot("stopped")
  var other = createTemporaryObject(anotherWidget, this)
  verify(other !== null)
  widget.popupOpen = true
  other.popupOpen = true
  service.snapshot = findSnapshot("ringing")
  compare(findChild(widget, "findEarbudsButton").text, "Stop")
  compare(findChild(widget, "findEarbudsIcon").text, "■")
  compare(findChild(other, "findEarbudsButton").text, "Stop")
  compare(findChild(other, "findEarbudsIcon").text, "■")
  // An open view going away must stop the same owned search.
  other.destroy()
  wait(0)
  compare(service.findRequests, [false])
  // Automatic stop arrives as a snapshot, without a UI command response.
  service.snapshot = findSnapshot("stopped")
  verify(!widget.finding)
  compare(findChild(widget, "findEarbudsIcon").text, "▶")
 }
 function test_find_close_after_device_switch_cancels_original_pending_start() {
  service.snapshot = findSnapshot("stopped")
  widget.popupOpen = true
  findChild(widget, "findEarbudsButton").clicked()
  var originalId = service.snapshot.find_device_id
  var next = findSnapshot("stopped")
  next.find_device_id = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  service.snapshot = next
  widget.close()
  compare(service.findRequests, [true,false])
  compare(service.findDeviceIds, [originalId,originalId])
 }
 function test_touch_controls_read_and_write_real_widget() {
  service.snapshot = touchSnapshot()
  widget.popupOpen = true
  compare(service.queuedRequests[0].command, "touch_controls")
  service.lastResponse = {request_id:widget.pendingRequestId,ok:true,result:{}}
  wait(0)
  findChild(widget, "touchControlsDisclosure").clicked()
  var left = findChild(widget, "touchSelector_1_2")
  var right = findChild(widget, "touchSelector_2_2")
  verify(left !== null)
  verify(right !== null)
  compare(left.currentLabel(), "Next track")
  compare(left.options.length, 3)
  compare(right.currentLabel(), "Unknown (254)")
  compare(findChild(widget, "touchSelector_1_4").visible, false)
  left.select("5")
  compare(service.touchRequest.side, 1)
  compare(service.touchRequest.action, 2)
  compare(service.touchRequest.function, 5)
  compare(left.currentLabel(), "Next track")  // display only confirmed state
  verify(!left.enabled)
  service.lastResponse = {request_id:widget.pendingRequestId,ok:true,result:{verified:false}}
  wait(0)
  verify(widget.outcome.indexOf("not confirmed") !== -1)
  verify(findChild(widget, "touchSelector_1_2").enabled)
  service.connection = "disconnected"
  wait(0)
  verify(!findChild(widget, "touchSelector_1_2").enabled)
 }
 function test_touch_controls_refresh_and_narrow_layout() {
  service.snapshot = touchSnapshot()
  host.panelAvailableWidth = 400
  widget.popupOpen = true
  service.lastResponse = {request_id:widget.pendingRequestId,ok:true,result:{}}
  wait(0)
  var section = findChild(widget, "touchControlsSection")
  verify(section.visible)
  findChild(widget, "touchControlsDisclosure").clicked()
  wait(0)
  var right = findChild(widget, "touchSide_2")
  var left = findChild(widget, "touchSide_1")
  verify(right.y > left.y)
  verify(right.x + right.width <= section.width)
  findChild(widget, "refreshTouchControls").clicked()
  compare(service.queuedRequests.length, 2)
  service.snapshot = {status:{battery:{}},capabilities:[],anc_modes:[]}
  wait(0)
  verify(!section.visible)
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
 function test_hold_cycle_is_shared_validated_and_applied_explicitly() {
  var state = touchSnapshot()
  state.capabilities.push("hold_cycle")
  state.hold_cycle = {modes:["anc","transparency"],min_selected:2,shared:true,writable:true,
   options:[{value:"anc",label:"Noise cancellation"},{value:"off",label:"Off"},
    {value:"transparency",label:"Transparency"}]}
  service.snapshot = state
  widget.popupOpen = true
  service.lastResponse = {request_id:widget.pendingRequestId,ok:true,result:{}}
  wait(0)
  var apply = findChild(widget, "applyHoldCycle")
  var anc = findChild(widget, "holdCycleOption_anc")
  var off = findChild(widget, "holdCycleOption_off")
  var transparency = findChild(widget, "holdCycleOption_transparency")
  verify(apply !== null)
  verify(!apply.visible)
  findChild(widget, "touchControlsDisclosure").clicked()
  wait(0)
  verify(anc.visible && off.visible && transparency.visible)
  verify(anc.checked)
  verify(!off.checked)
  verify(transparency.checked)
  verify(!apply.enabled)
  verify(findChild(widget, "touchSelector_1_4") === null)
  anc.clicked()
  verify(!apply.enabled)  // only one mode
  off.clicked()
  verify(apply.enabled)
  compare(service.holdCycleRequest, null)
  service.snapshot = JSON.parse(JSON.stringify(state))  // ordinary poll preserves draft
  wait(0)
  verify(!anc.checked && off.checked && transparency.checked)
  findChild(widget, "touchControlsDisclosure").clicked()
  findChild(widget, "touchControlsDisclosure").clicked()
  verify(!anc.checked && off.checked && transparency.checked)
  apply.clicked()
  compare(service.holdCycleRequest.join(","), "off,transparency")
  verify(!apply.enabled)
  verify(!anc.enabled)
  state.hold_cycle.modes = ["off","transparency"]
  service.snapshot = JSON.parse(JSON.stringify(state))
  service.lastResponse = {request_id:widget.pendingRequestId,ok:true,result:{verified:true}}
  wait(0)
  verify(!apply.enabled)
  verify(!anc.checked && off.checked && transparency.checked)
  anc.clicked()
  verify(apply.enabled)
  findChild(widget, "cancelHoldCycle").clicked()
  verify(!anc.checked)
  verify(!apply.enabled)
  anc.clicked()
  apply.clicked()
  // An ignored write restores the actual device state, never the draft.
  service.lastResponse = {request_id:widget.pendingRequestId,ok:true,result:{verified:false}}
  wait(0)
  verify(!anc.checked && off.checked && transparency.checked)
  verify(!apply.enabled)
  verify(widget.outcome.indexOf("not confirmed") !== -1)
  off.forceActiveFocus()
  verify(off.activeFocus)
  findChild(widget, "touchControlsDisclosure").clicked()
  verify(!off.activeFocus)
  findChild(widget, "touchControlsDisclosure").clicked()
  service.connection = "disconnected"
  wait(0)
  verify(!off.enabled)
  verify(!apply.enabled)
 }
 function test_disclosures_default_closed_independent_and_keep_edits() {
  var state = touchSnapshot()
  state.capabilities.push("eq", "bass_engine")
  state.custom_eq_write_verified = true
  state.eq = {current_id:7,current_name:"My curve",gain_step_db:1,
   presets:[{id:3,key:"balanced",name:"Balanced"}],
   custom_entries:[{eq_id:7,name:"My curve",min_gain_db:-6,max_gain_db:6,
    bands:[{frequency_hz:62,gain_db:3},{frequency_hz:250,gain_db:1}]}]}
  service.snapshot = state
  widget.popupOpen = true
  while (widget.pendingRequestId >= 0) {
   service.lastResponse = {request_id:widget.pendingRequestId,ok:true,result:{}}
  }
  wait(0)
  var customHeader = findChild(widget, "customEqDisclosure")
  var touchHeader = findChild(widget, "touchControlsDisclosure")
  var bands = findChild(widget, "customEqBands")
  var touch = findChild(widget, "touchSelector_1_2")
  verify(customHeader !== null)
  verify(touchHeader !== null)
  verify(!bands.visible)
  verify(!touch.visible)
  verify(findChild(widget, "currentEqLabel").visible)
  compare(findChild(widget, "currentEqLabel").text, "Current: My curve")
  var bass = findChild(widget, "bassWaveSection")
  verify(bass !== null)
  verify(customHeader.mapToItem(widget, 0, 0).y < bass.mapToItem(widget, 0, 0).y)
  compare(customHeader.mapToItem(widget, 0, 0).x, findChild(widget, "eqHeading").mapToItem(widget, 0, 0).x)
  compare(customHeader.width, findChild(widget, "eqHeading").width)
  compare(findChild(widget, "currentEqLabel").y, findChild(widget, "eqHeadingTitle").y)
  verify(findChild(widget, "currentEqLabel").x > findChild(widget, "eqHeadingTitle").x)
  var compactHeight = widget.panelHeight
  var fixedWidth = widget.contentWidth
  customHeader.clicked()
  wait(0)
  verify(bands.visible)
  verify(!touch.visible)
  tryVerify(function() { return widget.panelHeight > compactHeight })
  compare(widget.contentWidth, fixedWidth)
  var gain = findChild(widget, "eqHandle_62")
  gain.forceActiveFocus()
  verify(gain.activeFocus)
  keyPress(Qt.Key_Up)
  compare(bands.gains[0],4)
  customHeader.clicked()
  wait(0)
  verify(!bands.visible)
  verify(!gain.activeFocus)
  keyRelease(Qt.Key_Up)
  tryCompare(widget, "panelHeight", compactHeight)
  touchHeader.clicked()
  wait(0)
  verify(touch.visible)
  verify(!bands.visible)
  compare(widget.contentWidth, fixedWidth)
  touch.forceActiveFocus()
  verify(touch.activeFocus)
  touchHeader.clicked()
  verify(!touch.activeFocus)
  customHeader.clicked()
  wait(0)
  compare(bands.gains[0],3) // Collapsing an unfinished gesture cancels it.
  compare(service.customRequest, null)
  compare(service.touchRequest, null)
  touchHeader.clicked()
  gain.forceActiveFocus()
  verify(gain.activeFocus)
  widget.close()
  widget.popupOpen = true
  wait(0)
  verify(!bands.visible)
  verify(!touch.visible)
  verify(!gain.activeFocus)
  compare(widget.contentWidth, fixedWidth)
  service.snapshot = {status:{battery:{}},capabilities:[],anc_modes:[]}
  wait(0)
  verify(!customHeader.visible)
  verify(!touchHeader.visible)
 }
 function test_native_eq_panel_is_capability_driven() {
  service.snapshot = ({
   status:{model:"Test buds",battery:{left:{percentage:80},right:{percentage:60}}},
   anc_modes:[], capabilities:["eq"], session_connected:true,
   eq_write_verified:true, custom_eq_write_verified:true, custom_eq_manage_verified:true,
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
  widget.customEqExpanded = true
  var curve = findChild(widget,"customEqBands")
  var handle = findChild(widget,"eqHandle_62")
  handle.forceActiveFocus()
  keyPress(Qt.Key_Up)
  compare(service.customRequest,null)
  keyRelease(Qt.Key_Up)
  verify(service.customRequest !== null)
  compare(service.customRequest.entry_id, 5)
  compare(service.customRequest.gains.join(","), "1,0")
  widget.pendingRequestId = -1
  service.customRequest = null
  widget.activateCustomSlot(0)
  compare(service.customRequest,null) // The current curve needs no activation write.
  widget.activateCustomSlot(1)
  compare(service.customRequest.entry_id,5)
  compare(service.customRequest.gains.join(","),"0,0")
  widget.pendingRequestId = -1
  widget.popupOpen = false
 }
 function test_curve_autosave_uses_pair_token_and_settles_failed_save_from_readback() {
  var state = findSnapshot("stopped")
  state.capabilities = ["eq"]
  state.custom_eq_write_verified = true
  state.eq = {current_id:7,current_name:"Curve",gain_step_db:1,presets:[],
   custom_entries:[{eq_id:7,name:"Curve",min_gain_db:-6,max_gain_db:6,
    bands:[{frequency_hz:62,gain_db:3},{frequency_hz:250,gain_db:1}]}]}
  service.snapshot=state
  widget.popupOpen=true
  service.lastResponse={request_id:widget.pendingRequestId,ok:true,result:{}}
  widget.customEqExpanded=true
  var curve=findChild(widget,"customEqBands")
  var handle=findChild(widget,"eqHandle_62")
  handle.forceActiveFocus()
  keyPress(Qt.Key_Up)
  compare(curve.gains[0],4)
  service.snapshot=JSON.parse(JSON.stringify(state))
  compare(curve.gains[0],4) // Polling must not reset a local gesture.
  keyRelease(Qt.Key_Up)
  compare(service.customRequests.length,1)
  compare(service.customRequest.device_id,state.find_device_id)
  compare(service.customRequest.gains.join(","),"4,1")
  verify(!curve.enabled)
  service.lastResponse={request_id:widget.pendingRequestId,ok:true,result:{verified:false}}
  wait(0)
  compare(curve.gains[0],3)
  verify(widget.outcome.indexOf("not confirmed")!==-1)
  verify(curve.enabled)
 }
 function test_adaptive_anc_routes_through_panel_service() {
  service.snapshot = ({
   status:{model:"OnePlus Buds 4",product_id:"065414",battery:{},anc:"adaptive",anc_level:null},
   compatibility:"community_tested", anc_modes:["off","on","transparency","adaptive"],
   capabilities:["anc","adaptive_anc"], session_connected:true
  })
  wait(0)
  compare(widget.currentAncMode, "adaptive")
  compare(widget.ancOptions[3].value, "adaptive")
  widget.selectAnc("adaptive")
  compare(service.ancRequest, "adaptive")
  compare(widget.pendingKind, "anc")
  compare(widget.pendingMode, "adaptive")
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

  service.snapshot = ({status:null, anc_modes:[], capabilities:[], session_connected:false,
   compatibility:""})
  wait(0)
  verify(!widget.compatibilityNoticeShown)
  verify(findChild(widget, "compatibilityNotice").visible === false)

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
 function test_custom_eq_profile_can_be_created_and_renamed() {
  var state = {status:{model:"Nord",battery:{}}, anc_modes:[], capabilities:["eq"],
   session_connected:true, eq_write_verified:true, custom_eq_write_verified:true, custom_eq_manage_verified:true,
   eq:{current_id:7,current_name:"Test eq",gain_step_db:1,presets:[],
    custom_entries:[{eq_id:7,name:"Test eq",min_gain_db:-6,max_gain_db:6,
     bands:[{frequency_hz:62,gain_db:3},{frequency_hz:250,gain_db:1}]}]}}
  service.snapshot = state
  widget.popupOpen = true
  while (widget.pendingRequestId >= 0)
   service.lastResponse = {request_id:widget.pendingRequestId,ok:true,result:{}}
  wait(0)
  widget.customEqExpanded = true
  wait(0)
  var row = findChild(widget, "customEqProfileRow")
  var selector = findChild(widget, "customEqSelector")
  var first = findChild(widget, "customEqFirstAction")
  var second = findChild(widget, "customEqSecondAction")
  var field = findChild(widget, "customEqNameField")
  verify(row !== null && selector !== null && first !== null && second !== null)
  verify(field !== null)
  verify(row.visible)
  verify(selector.visible && !field.visible)
  verify(selector.width < row.width)
  verify(first.x > selector.x + selector.width)
  var deleteButton = findChild(widget, "customEqDeleteAction")
  compare(deleteButton.x + deleteButton.width, row.width)
  compare(first.text, "\uF040")
  compare(second.text, "+")

  second.clicked()
  wait(0)
  compare(widget.profileNameMode, "create")
  verify(!selector.visible && field.visible)
  compare(first.text, "\u2715")
  compare(second.text, "\u2713")
  // The name field must own the keyboard, otherwise it cannot be typed into.
  verify(field.activeFocus)
  keyPress(Qt.Key_R)
  wait(0)
  compare(field.text, "r")
  compare(widget.profileNameDraft, "r")
  keyRelease(Qt.Key_R)
  field.text = ""
  widget.profileNameDraft = "Plugin Test"
  second.clicked()
  wait(0)
  compare(service.profileRequests.length, 1)
  compare(service.profileRequests[0].action, "create")
  compare(service.profileRequests[0].name, "Plugin Test")
  compare(widget.pendingKind, "custom_eq_create")
  // The bridge publishes the new profile before the answer arrives.
  service.snapshot.eq.custom_entries.push({eq_id:8,name:"Plugin Test",
   min_gain_db:-6,max_gain_db:6,
   bands:[{frequency_hz:62,gain_db:0},{frequency_hz:250,gain_db:0}]})
  service.snapshot = JSON.parse(JSON.stringify(service.snapshot))
  wait(0)
  service.lastResponse = {request_id:widget.pendingRequestId,ok:true,
   result:{verified:true,current_id:8}}
  wait(0)
  compare(widget.profileNameMode, "")
  verify(selector.visible && !field.visible)
  verify(widget.outcome.indexOf("Verified") !== -1)
  // The dropdown shows the profile that was just created.
  compare(widget.selectedCustom.eq_id, 8)
  compare(selector.value, String(widget.customSlotIndex))

  first.clicked()
  wait(0)
  compare(widget.profileNameMode, "rename")
  // The rename starts from the profile that is selected, which is the one
  // that was just created.
  compare(widget.profileNameDraft, "Plugin Test")
  widget.profileNameDraft = "Rock"
  second.clicked()
  wait(0)
  compare(service.profileRequests.length, 2)
  compare(service.profileRequests[1].action, "rename")
  compare(service.profileRequests[1].entry_id, 8)
  compare(service.profileRequests[1].name, "Rock")
  compare(widget.pendingKind, "custom_eq_rename")
  service.lastResponse = {request_id:widget.pendingRequestId,ok:true,
   result:{verified:true,current_id:8}}
  wait(0)
  compare(widget.profileNameMode, "")

  first.clicked()
  wait(0)
  compare(widget.profileNameMode, "rename")
  first.clicked()
  wait(0)
  compare(widget.profileNameMode, "")
  compare(service.profileRequests.length, 2)
 }

 function test_custom_eq_dropdown_keeps_the_selection_and_delete_asks_first() {
  var state = {status:{model:"Nord",battery:{}}, anc_modes:[], capabilities:["eq"],
   session_connected:true, eq_write_verified:true, custom_eq_write_verified:true, custom_eq_manage_verified:true,
   custom_eq_keep_last:true, custom_eq_max:3, custom_eq_slots:2,
   eq:{current_id:7,current_name:"Test eq",gain_step_db:1,presets:[],
    custom_entries:[{eq_id:7,name:"Test eq",min_gain_db:-6,max_gain_db:6,
     bands:[{frequency_hz:62,gain_db:3},{frequency_hz:250,gain_db:1}]},
     {eq_id:8,name:"Second",min_gain_db:-6,max_gain_db:6,
     bands:[{frequency_hz:62,gain_db:0},{frequency_hz:250,gain_db:0}]}]}}
  service.snapshot = state
  widget.popupOpen = true
  while (widget.pendingRequestId >= 0)
   service.lastResponse = {request_id:widget.pendingRequestId,ok:true,result:{}}
  wait(0)
  widget.customEqExpanded = true
  wait(0)
  var selector = findChild(widget, "customEqSelector")
  var plus = findChild(widget, "customEqSecondAction")
  var trash = findChild(widget, "customEqDeleteAction")
  var hint = findChild(widget, "customEqSlotsHint")
  var rename = findChild(widget, "customEqFirstAction")
  verify(selector !== null && plus !== null && trash !== null)
  verify(trash.visible && trash.enabled)
  verify(plus.enabled)
  verify(!hint.visible)
  // The trash button sits at the far right, after the pencil and the plus.
  compare(trash.text, "\uF1F8")
  verify(rename.x < plus.x)
  verify(plus.x < trash.x)
  verify(trash.x + trash.width <= selector.x + selector.width + selector.width)

  // The chosen name must survive the model rebuild of the next snapshot.
  selector.select("1")
  compare(widget.selectedCustom.eq_id, 8)
  compare(service.customRequest.entry_id, 8)
  compare(selector.value, "1")
  // A successful activation publishes the device readback before replying.
  state.eq.current_id = 8
  state.eq.current_name = "Second"
  service.snapshot = JSON.parse(JSON.stringify(state))
  service.lastResponse = {request_id:widget.pendingRequestId,ok:true,result:{verified:true}}
  wait(0)
  service.snapshot = JSON.parse(JSON.stringify(state))
  wait(0)
  compare(selector.value, "1")
  compare(selector.currentLabel(), "Second")

  // Deleting asks for confirmation first.
  var queuedBefore = service.queuedRequests.length
  trash.clicked()
  wait(0)
  verify(widget.deleteConfirmOpen)
  compare(service.queuedRequests.length, queuedBefore)
  widget.cancelDeleteCustomProfile()
  wait(0)
  verify(!widget.deleteConfirmOpen)
  compare(service.queuedRequests.length, queuedBefore)

  trash.clicked()
  wait(0)
  widget.confirmDeleteCustomProfile()
  wait(0)
  compare(service.queuedRequests.length, queuedBefore)
  var deleteRequest = service.profileRequests[service.profileRequests.length - 1]
  compare(deleteRequest.action, "delete")
  compare(deleteRequest.entry_id, 8)
  service.lastResponse = {request_id:widget.pendingRequestId,ok:true,
   result:{verified:true,current_id:8}}
  wait(0)
  verify(!widget.deleteConfirmOpen)

  // With every slot in use the plus button is greyed out.
  state.custom_eq_slots = 3
  service.snapshot = JSON.parse(JSON.stringify(state))
  wait(0)
  verify(!plus.enabled)
  verify(hint.visible)
 }
 function test_custom_eq_management_requires_separate_permission() {
  var state = {status:{model:"Nord",battery:{}}, anc_modes:[], capabilities:["eq"],
   session_connected:true, eq_write_verified:true, custom_eq_write_verified:true,
   custom_eq_manage_verified:false, custom_eq_max:3, custom_eq_slots:1,
   eq:{current_id:7,current_name:"Test eq",gain_step_db:1,presets:[],
    custom_entries:[{eq_id:7,name:"Test eq",min_gain_db:-6,max_gain_db:6,
     bands:[{frequency_hz:62,gain_db:3}]}]}}
  service.snapshot = state
  widget.popupOpen = true
  widget.customEqExpanded = true
  while (widget.pendingRequestId >= 0)
   service.lastResponse = {request_id:widget.pendingRequestId,ok:true,result:{}}
  wait(0)
  var plus = findChild(widget, "customEqSecondAction")
  var rename = findChild(widget, "customEqFirstAction")
  var del = findChild(widget, "customEqDeleteAction")
  verify(plus !== null && rename !== null && del !== null)
  verify(!plus.enabled && !rename.enabled && !del.enabled)
  state.custom_eq_manage_verified = true
  service.snapshot = JSON.parse(JSON.stringify(state))
  wait(0)
  verify(plus.enabled)
  verify(rename.enabled)
  verify(del.enabled)
  state.custom_eq_keep_last = true
  service.snapshot = JSON.parse(JSON.stringify(state))
  wait(0)
  verify(rename.visible && rename.enabled)
  verify(!del.visible && !del.enabled)
  widget.askDeleteCustomProfile(widget.selectedCustom)
  verify(!widget.deleteConfirmOpen)
 }
}
