import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Dialogs
import QtCore
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "BarModel.js" as BarModel

BarWidget {
  id: root
  moduleName: "oneplus-buds.control"

  readonly property var budsService: bar && bar.shell
    ? bar.shell.serviceFor(moduleName) : null
  readonly property string connection: budsService
    ? String(budsService.connection || "stopped") : "unavailable"
  readonly property var snapshot: budsService ? budsService.snapshot : null
  readonly property var presentation: BarModel.presentation(connection, snapshot)
  readonly property var ancOptions: BarModel.ancModes(snapshot)
  readonly property string currentAncMode: BarModel.currentAncMode(snapshot)
  readonly property var lastResponse: budsService ? budsService.lastResponse : null
  readonly property var eqStatus: snapshot ? snapshot.eq : null
  readonly property var eqPresets: BarModel.eqPresets(snapshot)
  readonly property var customEqEntries: BarModel.customEqEntries(snapshot)
  readonly property string compatibilityKind: BarModel.compatibility(snapshot)
  readonly property string compatibilityLabel: BarModel.compatibilityLabel(snapshot)
  readonly property string reportActionLabel: BarModel.reportActionLabel(snapshot)
  readonly property string reportIssueUrl: BarModel.compatibilityIssueUrl(snapshot)
  readonly property string reportSubmissionActionLabel: experimentalDevice
    ? "Submit compatibility report on GitHub" : "Open GitHub issue"
  readonly property string reportDialogSelectedFile: String(reportFileDialog.selectedFile || "")
  readonly property bool experimentalDevice: compatibilityKind === "experimental"
  readonly property bool communityTestedDevice: compatibilityKind === "community_tested"
  // Without a known device there is nothing to call experimental, so the
  // notice stays hidden while nothing is connected.
  readonly property bool compatibilityNoticeShown: !!(snapshot && snapshot.status)
    && (experimentalDevice || communityTestedDevice)
  readonly property bool reportAvailable: connection === "connected"
    && snapshot !== null && snapshot.status !== null
  readonly property bool reportActionShown: reportAvailable && !reportDetailsOpen
  readonly property var selectedCustom: customEqEntries.length > 0
    ? customEqEntries[Math.max(0, Math.min(customSlotIndex, customEqEntries.length - 1))] : null
  readonly property bool eqAvailable: !!(snapshot && snapshot.capabilities
    && snapshot.capabilities.indexOf("eq") !== -1)
  // Local fork: the phone app's feature switches and the bass engine level.
  readonly property var featureSwitches: (snapshot && snapshot.feature_switches)
    ? snapshot.feature_switches : {}
  readonly property bool featureSwitchesAvailable: !!(snapshot && snapshot.capabilities
    && snapshot.capabilities.indexOf("feature_switches") !== -1)
  readonly property bool touchControlsAvailable: !!(snapshot && snapshot.capabilities
    && snapshot.capabilities.indexOf("touch_controls") !== -1)
  readonly property var touchControls: snapshot && snapshot.touch_controls
    ? snapshot.touch_controls : []
  readonly property var holdCycle: snapshot ? snapshot.hold_cycle : null
  readonly property bool holdCycleAvailable: !!(snapshot && snapshot.capabilities
    && snapshot.capabilities.indexOf("hold_cycle") !== -1)
  property var holdCycleDraft: []
  property bool holdCycleDirty: false
  readonly property bool holdCycleEditable: !!(holdCycle && holdCycle.writable
    && connection === "connected" && snapshot && snapshot.session_connected
    && pendingRequestId < 0)
  readonly property bool holdCycleDraftValid: !!(holdCycle
    && holdCycleDraft.length >= holdCycle.min_selected)
  onHoldCycleChanged: {
    if (!holdCycle || !holdCycleDirty) resetHoldCycleDraft()
  }
  // The heading is the name the device carries, not a hard coded model name.
  readonly property string deviceName: {
    var status = snapshot && snapshot.status
    if (!status) return "OnePlus earbuds"
    var name = status.name ? String(status.name) : ""
    if (name) return name
    return status.model ? String(status.model) : "OnePlus earbuds"
  }
  // Local fork: geometry probe for layout diagnostics.
  readonly property real popupX: popup.x
  readonly property real popupWidth: popup.width
  readonly property real contentWidth: popup.contentWidth
  readonly property real controlSectionsWidth: controlSections.width
  readonly property real eqColumnWidth: eqColumn.width
  readonly property real bandFlowWidth: customCurve.width
  readonly property real scrollbarWidth: panelScroll.ScrollBar.vertical
    ? panelScroll.ScrollBar.vertical.width : 0
  readonly property bool scrollbarVisible: !!(panelScroll.ScrollBar.vertical
    && panelScroll.ScrollBar.vertical.visible)
  readonly property bool scrollbarActive: !!(panelScroll.ScrollBar.vertical
    && panelScroll.ScrollBar.vertical.active)
  readonly property real viewHeight: panelScroll.height
  readonly property real contentHeight: panelScroll.contentHeight
  readonly property real screenWidth: Screen.width
  readonly property bool bassEngineAvailable: !!(snapshot && snapshot.capabilities
    && snapshot.capabilities.indexOf("bass_engine") !== -1)
  readonly property int bassLevel: (snapshot && snapshot.bass_level !== null
    && snapshot.bass_level !== undefined) ? Number(snapshot.bass_level) : 0
  readonly property bool bassEngineEnabled: featureSwitches.bass_engine === true
  readonly property var featureList: BarModel.featureList(snapshot)
  readonly property bool useTwoColumnLayout: eqAvailable
    && popup.availableCardWidth >= Style.space(560)
  readonly property int panelHeight: popup.contentHeight

  readonly property bool lifecycleUsable: connection === "connected"
    && snapshot !== null && snapshot.session_connected === true
    && snapshot.status !== null && ancOptions.length > 0
  onLifecycleUsableChanged: {
    if (budsService && typeof budsService.observeLifecycle === "function")
      budsService.observeLifecycle(lifecycleUsable ? "ui_usable" : "ui_unavailable",
        snapshot && snapshot.status ? snapshot.status.product_id : null)
  }

  // Local fork: a lost connection invalidates a request that can no longer
  // be answered, so the panel must not stay disabled.
  onConnectionChanged: {
    if (connection !== "connected" && pendingRequestId >= 0) {
      if (pendingKind === "custom_eq") customCurve.settle()
      pendingRequestId = -1
      pendingKind = ""
      pendingMode = ""
      requestWatchdog.stop()
    }
  }

  property bool popupOpen: false
  property int pendingRequestId: -1
  // Local fork: the find-my-earbuds tone is a toggle. Like the phone app,
  // the tone stops when the panel is closed.
  readonly property string findState: snapshot && snapshot.find_state
    ? String(snapshot.find_state) : "stopped"
  readonly property bool finding: findState === "ringing" || findState === "unknown"
  property string findRequestDeviceId: ""
  onFindStateChanged: {
    if (findState === "stopped" && outcomeKind === "find") outcome = ""
  }
  // Local fork: diagnostic channel for read-only protocol discovery.
  property int diagnosticRequestId: -1
  property string diagnosticResult: ""
  property string pendingMode: ""
  property string outcome: ""
  property string outcomeKind: ""
  property string pendingKind: ""
  property int customSlotIndex: 0
  property bool customSelectionDirty: false
  readonly property string customEqDeviceKey: snapshot && snapshot.find_device_id
    ? String(snapshot.find_device_id) : ""
  property bool customEqExpanded: false
  // Local fork: the profile dropdown turns into a name field while a profile
  // is created or renamed, the way the phone app does it.
  property string profileNameMode: ""
  property string profileNameDraft: ""
  property int profileRenameEntryId: -1
  property bool deleteConfirmOpen: false
  property int pendingDeleteEntryId: -1
  property string pendingDeleteName: ""
  readonly property bool customEqWritable: !!(snapshot
    && snapshot.custom_eq_write_verified === true
    && snapshot.session_connected === true
    && connection === "connected" && pendingRequestId < 0)
  // Local fork: the earbuds hold a fixed number of custom profiles. The plus
  // button is greyed out when every slot is taken.
  readonly property int customEqMax: snapshot && snapshot.custom_eq_max
    ? Number(snapshot.custom_eq_max) : 0
  readonly property int customEqSlots: snapshot && snapshot.custom_eq_slots !== undefined
    ? Number(snapshot.custom_eq_slots) : customEqEntries.length
  readonly property bool customEqSlotsFull: customEqMax > 0
    && customEqSlots >= customEqMax
  property bool touchControlsExpanded: false
  property bool reportDetailsOpen: false
  property bool reportSaved: false
  property string proposedReportFilename: ""
  property string pendingReportLocation: ""
  property string savedReportFilename: ""
  property string savedReportLocation: ""

  onCompatibilityKindChanged: {
    reportDetailsOpen = false
    clearReportResult()
  }

  function syncCustomSlotFromEq() {
    if (!eqStatus || !customEqEntries.length) return
    for (var i = 0; i < customEqEntries.length; i++) {
      if (customEqEntries[i].eq_id === eqStatus.current_id) {
        setCustomSlotIndex(i)
        return
      }
    }
    setCustomSlotIndex(0)
  }

  // Dropdown writes its own value on selection. Keep it in sync with the
  // existing slot index when profiles or the selected slot change.
  function applyCustomSlotIndex() {
    if (!customEqEntries.length) return
    var index = Math.max(0, Math.min(customSlotIndex, customEqEntries.length - 1))
    if (customEqSelector && customEqSelector.value !== String(index))
      customEqSelector.value = String(index)
  }

  function setCustomSlotIndex(index) {
    customSlotIndex = index
    applyCustomSlotIndex()
  }

  function selectCustomSlot(index) {
    if (index < 0 || index >= customEqEntries.length) return
    setCustomSlotIndex(index)
    customSelectionDirty = true
  }

  onEqStatusChanged: {
    if (!customSelectionDirty) syncCustomSlotFromEq()
  }
  property bool hoverExpanded: false
  readonly property bool batteryExpanded: !vertical && presentation.label !== ""
    && (hoverExpanded || popupOpen)

  onPopupOpenChanged: {
    if (popupOpen) {
      customEqExpanded = false
      touchControlsExpanded = false
      resetHoldCycleDraft()
      cancelProfileName()
      cancelDeleteCustomProfile()
      customSelectionDirty = false
      syncCustomSlotFromEq()
      collapseTimer.stop()
      requestWatchdog.stop()
      if (bar) bar.hideTooltip(root)
      // Local fork: load the feature switches and the bass engine level that
      // the phone app shows, so the panel starts with the real state. The
      // requests are queued because the bridge handles one command at a time.
      if (budsService && connection === "connected") {
        panelQueue = []
        if (snapshot && snapshot.capabilities
            && snapshot.capabilities.indexOf("eq") !== -1)
          panelQueue.push({ kind: "eq_status", command: "eq_status", params: {} })
        if (snapshot && snapshot.capabilities
            && snapshot.capabilities.indexOf("feature_switches") !== -1)
          panelQueue.push({ kind: "feature_switches", command: "feature_switches",
            params: {} })
        if (snapshot && snapshot.capabilities
            && snapshot.capabilities.indexOf("bass_engine") !== -1)
          panelQueue.push({ kind: "bass_status", command: "bass_status", params: {} })
        if (touchControlsAvailable)
          panelQueue.push({ kind: "touch_read", command: "touch_controls", params: {} })
        sendNextPanelRequest()
      }
    } else if (!hitArea.containsMouse) {
      collapseTimer.restart()
    }
    // Local fork: like the phone app, the find-my-earbuds tone stops when the
    // panel is closed.
    if (!popupOpen) stopFindingOnClose()
  }

  Component.onDestruction: {
    if (popupOpen) stopFindingOnClose()
  }

  function stopFindingOnClose() {
    if ((finding || (pendingKind === "find" && pendingMode === "find"))
        && !(pendingKind === "find" && pendingMode === "stop")
        && budsService && connection === "connected") {
      var target = pendingKind === "find" && pendingMode === "find"
        ? findRequestDeviceId : snapshot && snapshot.find_device_id
      budsService.findEarbuds(false, target)
    }
  }

  function close() { popupOpen = false }

  function resetHoldCycleDraft() {
    holdCycleDraft = holdCycle && holdCycle.modes ? holdCycle.modes.slice() : []
    holdCycleDirty = false
  }

  function toggleHoldCycleMode(mode) {
    if (!holdCycleEditable) return
    var draft = holdCycleDraft.slice()
    var index = draft.indexOf(mode)
    if (index >= 0) draft.splice(index, 1)
    else draft.push(mode)
    // Keep the app's display order for a stable request and comparison.
    holdCycleDraft = holdCycle.options.map(function(option) { return option.value })
      .filter(function(value) { return draft.indexOf(value) >= 0 })
    holdCycleDirty = JSON.stringify(holdCycleDraft) !== JSON.stringify(holdCycle.modes)
  }

  function applyHoldCycle() {
    if (!budsService || !holdCycleEditable || !holdCycleDraftValid || !holdCycleDirty) return
    var requestId = budsService.setHoldCycle(holdCycleDraft.slice())
    if (requestId === null) return
    pendingRequestId = requestId
    pendingKind = "hold_cycle"
    pendingMode = "hold cycle"
    outcome = ""
    requestWatchdog.restart()
  }

  function refreshTouchControls() {
    if (!touchControlsAvailable || connection !== "connected" || pendingRequestId >= 0) return
    panelQueue.push({kind: "touch_read", command: "touch_controls", params: {}})
    sendNextPanelRequest()
  }

  function setTouchControl(side, action, value) {
    if (!budsService || connection !== "connected" || pendingRequestId >= 0) return
    var requestId = budsService.setTouchControl(side, action, value)
    if (requestId === null) return
    pendingRequestId = requestId
    pendingKind = "touch_write"
    pendingMode = "touch controls"
    outcome = ""
    requestWatchdog.restart()
  }

  // Local fork: the panel loads its state with a small request queue, because
  // the bridge answers one command at a time.
  property var panelQueue: []

  function sendNextPanelRequest() {
    if (!budsService || connection !== "connected") return
    if (pendingRequestId >= 0 || panelQueue.length === 0) return
    var entry = panelQueue.shift()
    var requestId = budsService.request(entry.command, entry.params)
    if (requestId === null) return
    pendingRequestId = requestId
    pendingKind = entry.kind
    // Local fork: a request can be lost when the helper restarts underneath
    // it. Without a watchdog the panel would stay disabled forever.
    requestWatchdog.restart()
  }

  // Local fork: give up on a request that never gets an answer.
  function abandonPendingRequest() {
    if (pendingRequestId < 0) return
    if (pendingKind === "custom_eq") customCurve.settle()
    pendingRequestId = -1
    pendingKind = ""
    pendingMode = ""
    outcome = "The request timed out"
    sendNextPanelRequest()
  }

  function selectAnc(mode) {
    if (!budsService || connection !== "connected" || pendingRequestId >= 0) return
    var supported = false
    for (var i = 0; i < ancOptions.length; i++)
      if (ancOptions[i].value === mode) supported = true
    if (!supported) return

    var requestId = budsService.setAnc(mode)
    if (requestId === null) {
      outcome = "Could not start request"
      return
    }
    pendingRequestId = requestId
    pendingMode = mode
    pendingKind = "anc"
    outcome = ""
  }

  function selectEq(value) {
    if (!budsService || connection !== "connected" || pendingRequestId >= 0) return
    var requestId = budsService.setEq(value)
    if (requestId === null) { outcome = "Could not start request"; return }
    pendingRequestId = requestId
    pendingKind = "eq"
    pendingMode = String(value)
    outcome = ""
  }

  // Local fork: the phone app's feature switches and bass engine.
  function toggleFeature(name, enabled) {
    if (!budsService || connection !== "connected" || pendingRequestId >= 0) return
    var requestId = budsService.setFeatureSwitch(name, enabled === true)
    if (requestId === null) { outcome = "Could not start request"; return }
    pendingRequestId = requestId
    pendingKind = "feature"
    pendingMode = String(name)
    outcome = ""
  }

  function setBassLevel(level) {
    if (!budsService || connection !== "connected" || pendingRequestId >= 0) return
    var requestId = budsService.setBassLevel(Number(level))
    if (requestId === null) { outcome = "Could not start request"; return }
    pendingRequestId = requestId
    pendingKind = "bass"
    pendingMode = String(level)
    outcome = ""
  }

  function findEarbuds() {
    if (!budsService || connection !== "connected" || pendingRequestId >= 0) return
    var ringing = !finding
    var target = snapshot && snapshot.find_device_id ? String(snapshot.find_device_id) : ""
    var requestId = budsService.findEarbuds(ringing, target)
    if (requestId === null) { outcome = "Could not start request"; return }
    pendingRequestId = requestId
    pendingKind = "find"
    findRequestDeviceId = target
    pendingMode = ringing ? "find" : "stop"
    outcome = ""
    requestWatchdog.restart()
  }

  function saveCustomEq(entryId, gains, deviceKey) {
    if (!selectedCustom || selectedCustom.eq_id !== entryId || !customEqExpanded
        || !budsService || connection !== "connected" || pendingRequestId >= 0
        || !snapshot || snapshot.session_connected !== true
        || snapshot.custom_eq_write_verified !== true || deviceKey !== customEqDeviceKey) return
    var requestId = budsService.setCustomEq(entryId, gains.slice(), deviceKey)
    if (requestId === null) {
      outcome = "Could not start request"
      customCurve.settle()
      return
    }
    pendingRequestId = requestId
    pendingKind = "custom_eq"
    pendingMode = selectedCustom.name
    outcome = ""
    requestWatchdog.restart()
  }

  function activateCustomSlot(index) {
    if (index < 0 || index >= customEqEntries.length) return
    selectCustomSlot(index)
    var entry = customEqEntries[index]
    if (eqStatus && eqStatus.current_id !== entry.eq_id)
      saveCustomEq(entry.eq_id, entry.bands.map(function(b) { return b.gain_db }), customEqDeviceKey)
  }

  // Local fork: create a new custom profile in the next free device slot.
  function startProfileCreate() {
    if (!customEqWritable || customEqSlotsFull) return
    profileNameMode = "create"
    profileNameDraft = ""
    profileRenameEntryId = -1
    outcome = ""
    customEqNameField.text = ""
    focusProfileNameField()
  }

  // Local fork: rename the profile that is selected in the dropdown.
  function startProfileRename() {
    if (!customEqWritable || !selectedCustom) return
    profileNameMode = "rename"
    profileRenameEntryId = selectedCustom.eq_id
    profileNameDraft = String(selectedCustom.name || "")
    outcome = ""
    customEqNameField.text = profileNameDraft
    focusProfileNameField()
  }

  // The panel owns the keyboard while it is open. The focused item inside
  // the panel only receives the keys after it became the active focus item,
  // so the name field asks for it explicitly and once more a moment later.
  function focusProfileNameField() {
    customEqNameField.forceActiveFocus()
    Qt.callLater(function() {
      customEqNameField.forceActiveFocus()
      if (root.profileNameMode === "rename") customEqNameField.selectAll()
    })
    profileFocusTimer.restart()
  }

  function cancelProfileName() {
    profileNameMode = ""
    profileNameDraft = ""
    profileRenameEntryId = -1
  }

  function commitProfileName() {
    var value = String(profileNameDraft || "").trim()
    if (!value) { outcome = "The profile name must not be empty"; return }
    if (profileNameMode === "create") createCustomProfile(value)
    else if (profileNameMode === "rename") renameCustomProfile(profileRenameEntryId, value)
    else cancelProfileName()
  }

  function createCustomProfile(name) {
    if (!budsService || connection !== "connected" || pendingRequestId >= 0) return
    var requestId = budsService.createCustomEq(name, customEqDeviceKey)
    if (requestId === null) { outcome = "Could not start request"; return }
    pendingRequestId = requestId
    pendingKind = "custom_eq_create"
    pendingMode = name
    outcome = ""
    requestWatchdog.restart()
  }

  function renameCustomProfile(entryId, name) {
    if (!budsService || connection !== "connected" || pendingRequestId >= 0) return
    var requestId = budsService.renameCustomEq(entryId, name, customEqDeviceKey)
    if (requestId === null) { outcome = "Could not start request"; return }
    pendingRequestId = requestId
    pendingKind = "custom_eq_rename"
    pendingMode = name
    outcome = ""
    requestWatchdog.restart()
  }

  // Local fork: deleting a custom profile frees a slot for a new one, so the
  // panel asks before it removes a profile from the earbuds.
  function askDeleteCustomProfile(entry) {
    if (!customEqWritable || !entry) return
    pendingDeleteEntryId = entry.eq_id
    pendingDeleteName = String(entry.name || "")
    deleteConfirmOpen = true
    outcome = ""
  }

  function cancelDeleteCustomProfile() {
    deleteConfirmOpen = false
    pendingDeleteEntryId = -1
    pendingDeleteName = ""
  }

  function confirmDeleteCustomProfile() {
    var entryId = pendingDeleteEntryId
    cancelDeleteCustomProfile()
    if (!budsService || connection !== "connected" || pendingRequestId >= 0) return
    if (entryId < 0) return
    var requestId = budsService.deleteCustomEq(entryId, customEqDeviceKey)
    if (requestId === null) { outcome = "Could not start request"; return }
    pendingRequestId = requestId
    pendingKind = "custom_eq_delete"
    pendingMode = "custom profile"
    outcome = ""
    requestWatchdog.restart()
  }

  function saveDiagnosticReport(fileUrl) {
    if (!budsService || pendingRequestId >= 0) return
    var destination = String(fileUrl || "")
    var requestId = budsService.saveDiagnosticReport(destination)
    if (requestId === null) { outcome = "Could not start report"; return }
    pendingRequestId = requestId
    pendingKind = "diagnostic_report"
    pendingMode = ""
    pendingReportLocation = destination
    outcome = ""
    clearReportResult()
  }

  function clearReportResult() {
    reportSaved = false
    savedReportFilename = ""
    savedReportLocation = ""
  }

  function prepareReportFileDialog() {
    clearReportResult()
    outcome = ""
    proposedReportFilename = BarModel.reportFilename(snapshot, new Date())
    var folder = String(reportFileDialog.currentFolder || "")
    reportFileDialog.selectedFile = folder + (folder.endsWith("/") ? "" : "/")
      + proposedReportFilename
  }

  function openReportFileDialog() {
    prepareReportFileDialog()
    reportFileDialog.open()
  }

  function acceptReportFile(fileUrl) {
    var selected = String(fileUrl || "")
    var textDestination = BarModel.textReportUrl(selected)
    if (selected !== textDestination) {
      reportFileDialog.selectedFile = textDestination
      Qt.callLater(function() { reportFileDialog.open() })
      return
    }
    saveDiagnosticReport(textDestination)
  }

  function cancelDiagnosticReport() {
    clearReportResult()
    pendingReportLocation = ""
    outcome = ""
  }

  function openReportIssue() {
    Qt.openUrlExternally(reportIssueUrl)
  }

  // Local fork: send a bridge command from the shell for read-only protocol
  // discovery, e.g. diagnostic_query. The answer is exposed through status().
  function diagPing(): string {
    return "pong:" + String(diagnosticRequestId)
  }

  function diagnostic(payload): string {
    if (!budsService || connection !== "connected") return ""
    diagnosticResult = ""
    try {
      var request = JSON.parse(payload || "{}")
      diagnosticRequestId = budsService.request(
        String(request.command || ""), request.parameters || {})
    } catch (error) {
      diagnosticResult = JSON.stringify({error: String(error)})
      diagnosticRequestId = -1
    }
    return String(diagnosticRequestId)
  }

  onLastResponseChanged: {
    var response = lastResponse
    // Local fork: capture the answer of a diagnostic request before the
    // regular pending-request bookkeeping runs.
    if (response && diagnosticRequestId >= 0
        && Number(response.request_id) === diagnosticRequestId) {
      diagnosticRequestId = -1
      diagnosticResult = JSON.stringify(response.ok === true
        ? (response.result || {})
        : {error: response.error || {}})
    }
    if (!response || Number(response.request_id) !== pendingRequestId) return
    pendingRequestId = -1
    pendingMode = ""
    var completedKind = pendingKind
    outcomeKind = completedKind
    pendingKind = ""
    if (completedKind === "hold_cycle") resetHoldCycleDraft()
    // Local fork: continue the startup queue (feature switches, bass level).
    sendNextPanelRequest()
    if (completedKind === "diagnostic_report") {
      if (response.ok === true) {
        reportSaved = true
        savedReportFilename = response.result && response.result.filename
          ? String(response.result.filename) : "diagnostic report"
        savedReportLocation = BarModel.reportLocationLabel(
          pendingReportLocation, savedReportFilename,
          StandardPaths.writableLocation(StandardPaths.HomeLocation))
        outcome = ""
      } else {
        clearReportResult()
        outcome = response.error && response.error.message
          ? String(response.error.message) : "Diagnostic report could not be saved"
      }
      pendingReportLocation = ""
      return
    }
    if (response.ok === true && (completedKind === "eq_status"
        || completedKind === "eq" || completedKind === "custom_eq"
        || completedKind === "custom_eq_create"
        || completedKind === "custom_eq_rename"
        || completedKind === "custom_eq_delete")) {
      customSelectionDirty = false
      syncCustomSlotFromEq()
    }
    if (completedKind === "custom_eq") customCurve.settle()
    if (completedKind === "custom_eq_create" && response.ok === true) {
      // Show the freshly created profile in the dropdown.
      var createdId = response.result ? Number(response.result.current_id) : -1
      for (var i = 0; i < customEqEntries.length; i++) {
        if (customEqEntries[i].eq_id === createdId) {
          setCustomSlotIndex(i)
          customSelectionDirty = true
          break
        }
      }
      cancelProfileName()
    }
    if (completedKind === "custom_eq_rename" && response.ok === true)
      cancelProfileName()
    if (completedKind === "custom_eq_delete" && response.ok === true)
      cancelDeleteCustomProfile()
    if (response.ok === true) {
      if (completedKind === "custom_eq" && (!response.result || response.result.verified !== true)) {
        outcome = "EQ change was not confirmed by earbuds"
      } else if (completedKind === "hold_cycle" && (!response.result || response.result.verified !== true)) {
        outcome = "Hold cycle was not confirmed by earbuds"
      } else if (completedKind === "touch_write" && (!response.result || response.result.verified !== true)) {
        outcome = "Touch assignment was not confirmed by earbuds"
      } else if (completedKind === "feature" && (!response.result || response.result.verified !== true)) {
        outcome = "Switch change was not confirmed by earbuds"
      } else if (response.result && response.result.verified === true) {
        outcome = "Verified on earbuds"
      } else if (completedKind === "bass") {
        outcome = "Bass level sent"
      } else if (completedKind === "find") {
        if (response.result && response.result.acknowledged === true) {
          outcome = response.result.state === "ringing" ? "Earbuds are ringing" : "Ringing stopped"
        } else {
          outcome = root.finding
            ? "Search command was not confirmed. Use Stop to end the sound."
            : "Earbuds did not accept the search command"
        }
      } else if (completedKind === "feature") {
        outcome = "Switch updated"
      } else {
        outcome = ""
      }
    } else {
      var detail = response.error && response.error.message
        ? String(response.error.message) : "Change could not be verified"
      outcome = detail
    }
  }

  visible: true
  implicitWidth: icon.implicitWidth + Style.space(14)
    + (batteryExpanded ? Style.space(5) + batteryLabel.implicitWidth : 0)
  implicitHeight: barSize

  Behavior on implicitWidth {
    NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
  }

  Timer {
    id: collapseTimer
    interval: 300
    onTriggered: if (!hitArea.containsMouse && !root.popupOpen) root.hoverExpanded = false
  }

  // Local fork: watchdog for a bridge request that never gets an answer.
  Timer {
    id: requestWatchdog
    interval: 15000
    repeat: false
    onTriggered: root.abandonPendingRequest()
  }

  // Local fork: the popup needs a moment before the name field can take the
  // keyboard focus.
  Timer {
    id: profileFocusTimer
    interval: 150
    repeat: false
    onTriggered: {
      if (root.profileNameMode === "") return
      customEqNameField.forceActiveFocus()
    }
  }

  Item {
    anchors.fill: parent
    anchors.leftMargin: Style.space(7)
    anchors.rightMargin: Style.space(7)
    clip: true

    Text {
      id: icon
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      textFormat: Text.PlainText
      text: root.presentation.icon
      color: root.presentation.connected
        ? root.bar.barForeground : Qt.darker(root.bar.barForeground, 1.5)
      font.family: root.bar.fontFamily
      font.pixelSize: Style.font.body
    }

    Text {
      id: batteryLabel
      anchors.left: icon.right
      anchors.leftMargin: Style.space(5)
      anchors.verticalCenter: parent.verticalCenter
      visible: !root.vertical && text !== ""
      textFormat: Text.PlainText
      text: root.presentation.label
      color: root.bar.barForeground
      font.family: root.bar.fontFamily
      font.pixelSize: Style.font.bodySmall
    }
  }

  MouseArea {
    id: hitArea
    anchors.fill: parent
    hoverEnabled: true
    acceptedButtons: Qt.LeftButton
    cursorShape: Qt.PointingHandCursor
    onClicked: root.popupOpen = !root.popupOpen
    onEntered: {
      collapseTimer.stop()
      root.hoverExpanded = true
      if (root.bar && !root.popupOpen) root.bar.showTooltip(root, root.presentation.tooltip)
    }
    onExited: {
      collapseTimer.restart()
      if (root.bar) root.bar.hideTooltip(root)
    }
  }

  // Local fork: the panel is a KeyboardPanel, not a PopupCard. An xdg-popup
  // only receives key events after a click routes the focus through its
  // parent surface, so a name field inside it could not be typed into. The
  // KeyboardPanel primes the layer-shell keyboard focus when it opens and
  // hands the keys to the focused item inside the panel.
  KeyboardPanel {
    id: popup
    anchorItem: root
    bar: root.bar
    owner: root
    open: root.popupOpen
    // Local fork: the card must keep a constant width. The popup is clamped
    // to the screen when it opens, using the width it has at that moment. A
    // width that grows later - for example when the device snapshot arrives
    // after the panel was opened - pushes the right edge of the card off the
    // screen and cuts off the controls in the right-hand column.
    contentWidth: popup.fittedContentWidth(Style.space(600))
    contentHeight: popup.fittedContentHeight(panelContent.implicitHeight)

    // Local fork: deleting a custom profile asks for confirmation first.
    ConfirmDialog {
      id: deleteConfirm
      anchors.fill: parent
      z: 10
      opened: root.deleteConfirmOpen
      message: "Delete the custom profile “" + root.pendingDeleteName + "”?"
      cancelText: "Cancel"
      confirmText: "Delete"
      fontFamily: root.bar.fontFamily
      onCanceled: root.cancelDeleteCustomProfile()
      onConfirmed: root.confirmDeleteCustomProfile()
    }

    Flickable {
      id: panelScroll
      anchors.fill: parent
      contentWidth: width
      contentHeight: panelContent.implicitHeight
      clip: true
      boundsBehavior: Flickable.StopAtBounds
      flickableDirection: Flickable.VerticalFlick
      Controls.ScrollBar.vertical: Controls.ScrollBar {
        id: panelScrollBar
        policy: Controls.ScrollBar.AsNeeded
      }

      function reveal(item) {
        var top = item.mapToItem(panelContent, 0, 0).y
        if (top < contentY) contentY = top
        else if (top + item.height > contentY + height)
          contentY = top + item.height - height
      }

      Column {
        id: panelContent
        // Local fork: the scroll bar overlays the flickable, so the content
        // needs its own lane. Without it the bar covers the right edge of the
        // panel and swallows clicks on the up/down buttons of the right-hand
        // equalizer column.
        width: panelScroll.width - (panelScrollBar.visible ? panelScrollBar.width : 0)
        spacing: Style.space(12)

        // The heading is the name the device carries.
        Text {
          id: headingText
          width: parent.width
          textFormat: Text.PlainText
          text: root.deviceName
          color: root.bar.foreground
          font.family: root.bar.fontFamily
          font.pixelSize: Style.font.subtitle
          font.bold: true
          wrapMode: Text.Wrap
          elide: Text.ElideRight
        }

        Text {
          width: parent.width
          textFormat: Text.PlainText
          text: root.presentation.label || BarModel.titleCase(root.connection)
          color: root.bar.foreground
          font.family: root.bar.fontFamily
          font.pixelSize: Style.font.bodySmall
          wrapMode: Text.Wrap
        }
        Item {
          id: controlSections
          width: parent.width
          height: implicitHeight
          implicitHeight: root.useTwoColumnLayout
            ? Math.max(noiseColumn.implicitHeight, eqColumn.implicitHeight)
              + (featuresColumn.visible
                ? Style.space(14) + featuresColumn.implicitHeight : 0)
            : noiseColumn.implicitHeight
              + (eqColumn.visible ? Style.space(14) + eqColumn.implicitHeight : 0)
              + (featuresColumn.visible
                ? Style.space(14) + featuresColumn.implicitHeight : 0)

          Column {
            id: noiseColumn
            x: 0
            y: 0
            width: root.useTwoColumnLayout
              ? (controlSections.width - Style.space(16)) / 2 : controlSections.width
            spacing: Style.space(8)

            Repeater {
              model: BarModel.ancGroups(root.snapshot)

              delegate: Column {
                id: section
                required property var modelData
                width: noiseColumn.width
                spacing: Style.space(5)

                Text {
                  width: parent.width
                  text: section.modelData.title
                  textFormat: Text.PlainText
                  color: root.bar.foreground
                  font.family: root.bar.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                }

                Repeater {
                  model: section.modelData.options

                  delegate: Button {
                    required property var modelData
                    width: section.width
                    height: Math.max(implicitHeight, Style.space(32))
                    text: modelData.label
                    selected: modelData.value === root.currentAncMode
                      || (modelData.value === "on" && root.snapshot
                        && root.snapshot.status && root.snapshot.status.anc === "on")
                    bordered: true
                    leftAlign: true
                    enabled: root.connection === "connected" && root.pendingRequestId < 0
                    opacity: enabled ? 1.0 : 0.5
                    foreground: root.bar.foreground
                    background: root.bar.background
                    accent: Color.accent
                    fontFamily: root.bar.fontFamily
                    focusable: true
                    onActiveFocusChanged: if (activeFocus) panelScroll.reveal(this)
                    Keys.onDownPressed: nextItemInFocusChain().forceActiveFocus(Qt.TabFocusReason)
                    Keys.onUpPressed: nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)
                    Keys.onEscapePressed: root.close()
                    onClicked: root.selectAnc(modelData.value)
                  }
                }
              }
            }
          }

          Column {
            id: eqColumn
            x: root.useTwoColumnLayout ? noiseColumn.width + Style.space(16) : 0
            y: root.useTwoColumnLayout ? 0 : noiseColumn.implicitHeight + Style.space(14)
            width: root.useTwoColumnLayout ? noiseColumn.width : controlSections.width
            spacing: Style.space(5)
            visible: root.eqAvailable

            Row {
              id: eqHeading
              objectName: "eqHeading"
              width: parent.width
              spacing: Style.space(8)

              Text {
                id: eqHeadingTitle
                objectName: "eqHeadingTitle"
                text: "Earbud EQ"
                textFormat: Text.PlainText
                color: root.bar.foreground
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
                font.bold: true
              }

              Text {
                width: Math.max(0, eqHeading.width - eqHeadingTitle.width - eqHeading.spacing)
                objectName: "currentEqLabel"
                text: root.eqStatus ? "Current: " + root.eqStatus.current_name : "Loading native EQ…"
                textFormat: Text.PlainText
                color: root.bar.foreground
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
                horizontalAlignment: Text.AlignRight
                elide: Text.ElideRight
              }
            }

            Flow {
              id: eqPresetFlow
              width: parent.width
              spacing: Style.space(5)

              Repeater {
                model: root.eqPresets
                delegate: Button {
                  required property var modelData
                  width: modelData.name.length > 16 ? eqPresetFlow.width
                    : (eqPresetFlow.width - eqPresetFlow.spacing) / 2
                  height: Math.max(implicitHeight, Style.space(32))
                  text: modelData.name
                  selected: !!(root.eqStatus && root.eqStatus.current_id === modelData.id)
                  bordered: true
                  leftAlign: true
                  enabled: root.connection === "connected" && root.pendingRequestId < 0
                    && root.snapshot.eq_write_verified === true
                  opacity: enabled ? 1.0 : 0.5
                  foreground: root.bar.foreground
                  background: root.bar.background
                  accent: Color.accent
                  fontFamily: root.bar.fontFamily
                  onClicked: root.selectEq(modelData.key)
                }
              }
            }

            Column {
              objectName: "customEqSection"
              width: parent.width
              spacing: Style.space(5)
              visible: root.customEqEntries.length > 0

              Button {
                objectName: "customEqDisclosure"
                width: parent.width
                visible: root.customEqEntries.length > 0
                text: (root.customEqExpanded ? "▾  " : "▸  ") + "Custom EQ"
                leftAlign: true
                bordered: true
                foreground: root.bar.foreground
                background: root.bar.background
                accent: Color.accent
                fontFamily: root.bar.fontFamily
                focusable: true
                onActiveFocusChanged: if (activeFocus) panelScroll.reveal(this)
                onClicked: root.customEqExpanded = !root.customEqExpanded
              }

              Row {
                id: customEqProfileRow
                objectName: "customEqProfileRow"
                width: parent.width
                spacing: Style.space(4)
                visible: root.customEqExpanded && root.customEqEntries.length > 0

                readonly property real actionWidth: Style.space(28)
                readonly property real fieldWidth: Math.max(0, width
                  - 3 * actionWidth - 3 * spacing)

                Dropdown {
                  id: customEqSelector
                  objectName: "customEqSelector"
                  width: parent.fieldWidth
                  height: Style.space(32)
                  rowHeight: height
                  showLabel: false
                  foreground: root.bar.foreground
                  fontFamily: root.bar.fontFamily
                  visible: root.profileNameMode === ""
                  options: root.customEqEntries.map(function(entry, index) {
                    return {value: String(index), label: entry.name}
                  })
                  value: String(root.customSlotIndex)
                  onOptionsChanged: root.applyCustomSlotIndex()
                  enabled: root.customEqExpanded && root.pendingRequestId < 0
                  onChanged: function(value) { root.activateCustomSlot(Number(value)) }
                }

                Controls.TextField {
                  id: customEqNameField
                  objectName: "customEqNameField"
                  width: parent.fieldWidth
                  height: Style.space(32)
                  visible: root.profileNameMode !== ""
                  // The panel is an xdg-popup: it only owns the keyboard while
                  // it has grabbed the focus, so the name field needs both.
                  focus: root.profileNameMode !== ""
                  selectByMouse: true
                  font.family: root.bar.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  onTextEdited: root.profileNameDraft = text
                  onAccepted: root.commitProfileName()
                  Keys.onEscapePressed: root.cancelProfileName()
                }

                Button {
                  id: customEqFirstAction
                  objectName: "customEqFirstAction"
                  width: parent.actionWidth
                  height: Style.space(28)
                  text: root.profileNameMode === "" ? "\uF040" : "✕"
                  bordered: false
                  enabled: root.profileNameMode === ""
                    ? root.customEqWritable && !!root.selectedCustom
                    : root.pendingRequestId < 0
                  opacity: enabled ? 1.0 : 0.5
                  foreground: root.bar.foreground
                  background: root.bar.background
                  accent: Color.accent
                  fontFamily: root.bar.fontFamily
                  onClicked: {
                    if (root.profileNameMode === "") root.startProfileRename()
                    else root.cancelProfileName()
                  }

                  HoverHandler { id: customEqFirstHover }

                  Controls.ToolTip {
                    visible: customEqFirstHover.hovered && customEqFirstAction.visible
                    text: root.profileNameMode === "" ? "Rename profile" : "Cancel"
                    delay: 400
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.bodySmall
                    palette.toolTipBase: root.bar.background
                    palette.toolTipText: root.bar.foreground
                    palette.dark: Color.accent
                  }
                }


                Button {
                  id: customEqSecondAction
                  objectName: "customEqSecondAction"
                  width: parent.actionWidth
                  height: Style.space(28)
                  text: root.profileNameMode === "" ? "+" : "✓"
                  bordered: false
                  enabled: root.profileNameMode === ""
                    ? root.customEqWritable && !root.customEqSlotsFull
                    : root.pendingRequestId < 0
                    && String(root.profileNameDraft || "").trim().length > 0
                  opacity: enabled ? 1.0 : 0.5
                  foreground: root.bar.foreground
                  background: root.bar.background
                  accent: Color.accent
                  fontFamily: root.bar.fontFamily
                  onClicked: {
                    if (root.profileNameMode === "") root.startProfileCreate()
                    else root.commitProfileName()
                  }

                  HoverHandler { id: customEqSecondHover }

                  Controls.ToolTip {
                    visible: customEqSecondHover.hovered && customEqSecondAction.visible
                    text: root.profileNameMode === ""
                      ? (root.customEqSlotsFull ? "All custom EQ slots are in use"
                        : "New profile")
                      : "Save name"
                    delay: 400
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.bodySmall
                    palette.toolTipBase: root.bar.background
                    palette.toolTipText: root.bar.foreground
                    palette.dark: Color.accent
                  }
                }

                Button {
                  id: customEqDeleteAction
                  objectName: "customEqDeleteAction"
                  width: parent.actionWidth
                  height: Style.space(28)
                  text: "\uF1F8"
                  bordered: false
                  enabled: root.profileNameMode === ""
                    && root.customEqWritable && !!root.selectedCustom
                  opacity: enabled ? 1.0 : 0.5
                  foreground: root.bar.foreground
                  background: root.bar.background
                  accent: Color.accent
                  fontFamily: root.bar.fontFamily
                  onClicked: root.askDeleteCustomProfile(root.selectedCustom)

                  HoverHandler { id: customEqDeleteHover }

                  Controls.ToolTip {
                    visible: customEqDeleteHover.hovered && customEqDeleteAction.visible
                    text: "Delete profile"
                    delay: 400
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.bodySmall
                    palette.toolTipBase: root.bar.background
                    palette.toolTipText: root.bar.foreground
                    palette.dark: Color.accent
                  }
                }
              }

              Text {
                objectName: "customEqSlotsHint"
                width: parent.width
                visible: root.customEqExpanded && root.customEqSlotsFull
                text: "All custom EQ slots are in use. Delete a profile to add another."
                color: root.bar.foreground
                opacity: 0.72
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
                wrapMode: Text.Wrap
              }

              EqCurveEditor {
                id: customCurve
                objectName: "customEqBands"
                width: parent.width
                height: implicitHeight
                visible: root.customEqExpanded && root.customEqEntries.length > 0
                enabled: root.customEqExpanded && root.connection === "connected"
                  && root.snapshot && root.snapshot.session_connected === true
                  && root.snapshot.custom_eq_write_verified === true && root.pendingRequestId < 0
                entry: root.selectedCustom
                contextKey: root.customEqDeviceKey
                step: root.eqStatus && root.eqStatus.gain_step_db ? root.eqStatus.gain_step_db : 1
                foreground: root.bar.foreground
                background: root.bar.background
                fontFamily: root.bar.fontFamily
                onEditingStarted: root.customSelectionDirty = true
                onReleased: function(entryId, values, deviceKey) {
                  root.saveCustomEq(entryId, values, deviceKey)
                }
              }

            }

            // Local fork: the phone app's BassWave control (feature switch
            // 0x1d plus the -10..+10 level).
            Column {
              objectName: "bassWaveSection"
              width: parent.width
              visible: root.bassEngineAvailable
              spacing: Style.space(4)
              topPadding: Style.space(6)

              Row {
                width: parent.width
                spacing: Style.space(8)

                Text {
                  width: parent.width - Style.space(56)
                  text: "BassWave"
                  textFormat: Text.PlainText
                  color: root.bar.foreground
                  font.family: root.bar.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                }

                ToggleSwitch {
                  width: Style.space(40)
                  checked: root.bassEngineEnabled
                  busy: root.pendingRequestId >= 0
                  enabled: root.connection === "connected" && root.pendingRequestId < 0
                  onToggled: root.toggleFeature("bass_engine", !root.bassEngineEnabled)
                }
              }

              Text {
                width: parent.width
                text: "Bass level " + (root.bassLevel > 0 ? "+" : "") + root.bassLevel
                textFormat: Text.PlainText
                color: root.bar.foreground
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
              }

              PanelSlider {
                id: bassSlider
                width: parent.width
                bar: root.bar
                minimum: -10
                maximum: 10
                step: 1
                integer: true
                value: root.bassLevel
                enabled: root.connection === "connected" && root.pendingRequestId < 0
                onReleased: function(value) { root.setBassLevel(Math.round(value)) }
              }
            }

          }

          // Local fork: the phone app's feature switches.
          Column {
            id: featuresColumn
            x: 0
            y: root.useTwoColumnLayout
              ? Math.max(noiseColumn.implicitHeight, eqColumn.implicitHeight)
                + Style.space(14)
              : noiseColumn.implicitHeight
                + (eqColumn.visible ? Style.space(14) + eqColumn.implicitHeight : 0)
                + Style.space(14)
            width: parent.width
            spacing: Style.space(5)
            visible: root.featureSwitchesAvailable

            Text {
              width: parent.width
              text: "Features"
              textFormat: Text.PlainText
              color: root.bar.foreground
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
              visible: root.featureList.length > 0
            }

            Grid {
              id: featureGrid
              width: parent.width
              columns: root.useTwoColumnLayout ? 2 : 1
              rows: root.useTwoColumnLayout
                ? Math.ceil(root.featureList.length / 2) : root.featureList.length
              flow: Grid.TopToBottom
              columnSpacing: Style.space(16)
              rowSpacing: Style.space(5)

              Repeater {
                model: root.featureList

                delegate: Row {
                  required property var modelData
                  objectName: "featureRow_" + modelData.name
                  readonly property string tooltipText: modelData.tooltip || ""
                  width: root.useTwoColumnLayout
                    ? (featureGrid.width - featureGrid.columnSpacing) / 2 : featureGrid.width
                  spacing: Style.space(8)
                  HoverHandler { id: featureHover }
                  Controls.ToolTip {
                    visible: featureHover.hovered && parent.tooltipText !== ""
                    text: parent.tooltipText
                    delay: 400
                    width: Math.min(implicitWidth, parent.width)
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.bodySmall
                    palette.toolTipBase: root.bar.background
                    palette.toolTipText: root.bar.foreground
                    palette.dark: Color.accent
                  }

                  Text {
                    width: parent.width - Style.space(56)
                    text: modelData.label + (modelData.writable ? "" : "  (read-only)")
                    textFormat: Text.PlainText
                    color: root.bar.foreground
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.bodySmall
                    wrapMode: Text.Wrap
                    anchors.verticalCenter: parent.verticalCenter
                    opacity: modelData.writable ? 1.0 : 0.6
                  }

                  ToggleSwitch {
                    objectName: "featureToggle_" + modelData.name
                    width: Style.space(40)
                    checked: modelData.enabled
                    busy: root.pendingRequestId >= 0
                    // Local fork: switches that are not verified for this model
                    // stay visible but cannot be written.
                    interactive: modelData.writable
                    enabled: modelData.writable && root.connection === "connected"
                      && root.pendingRequestId < 0
                    opacity: modelData.writable ? 1.0 : 0.6
                    onToggled: root.toggleFeature(modelData.name, !modelData.enabled)
                  }
                }
              }
            }
          }
        }

        Column {
          id: touchSection
          objectName: "touchControlsSection"
          width: parent.width
          spacing: Style.space(8)
          visible: root.touchControlsAvailable

          Row {
            width: parent.width
            spacing: Style.space(8)
            Button {
              objectName: "touchControlsDisclosure"
              width: parent.width - (refreshTouchButton.visible
                ? refreshTouchButton.width + parent.spacing : 0)
              text: (root.touchControlsExpanded ? "▾  " : "▸  ") + "Touch controls"
              leftAlign: true
              bordered: true
              foreground: root.bar.foreground
              background: root.bar.background
              accent: Color.accent
              fontFamily: root.bar.fontFamily
              focusable: true
              onActiveFocusChanged: if (activeFocus) panelScroll.reveal(this)
              onClicked: root.touchControlsExpanded = !root.touchControlsExpanded
            }
            Button {
              id: refreshTouchButton
              objectName: "refreshTouchControls"
              width: Style.space(90)
              text: "Refresh"
              visible: root.touchControlsExpanded
              bordered: true
              foreground: root.bar.foreground
              background: root.bar.background
              accent: Color.accent
              fontFamily: root.bar.fontFamily
              enabled: root.touchControlsExpanded && root.connection === "connected" && root.pendingRequestId < 0
              onClicked: root.refreshTouchControls()
            }
          }

          Text {
            visible: root.touchControlsExpanded && root.touchControls.length === 0
            width: parent.width
            text: root.pendingKind === "touch_read" ? "Reading touch controls…"
              : "No touch assignments loaded. Use Refresh to read the earbuds."
            color: root.bar.foreground
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.bodySmall
            wrapMode: Text.Wrap
          }

          Column {
            objectName: "holdCycleEditor"
            width: parent.width
            spacing: Style.space(5)
            visible: root.touchControlsExpanded && root.holdCycleAvailable
            enabled: root.touchControlsExpanded

            Text {
              width: parent.width
              text: "Touch & hold · both earbuds"
              color: root.bar.foreground
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
            }
            Text {
              width: parent.width
              visible: !root.holdCycle
              text: "Use Refresh to read the hold modes."
              color: root.bar.foreground
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.bodySmall
              wrapMode: Text.Wrap
            }
            Flow {
              width: parent.width
              spacing: Style.space(8)
              Repeater {
                model: root.holdCycle ? root.holdCycle.options : []
                delegate: Controls.CheckBox {
                  required property var modelData
                  objectName: "holdCycleOption_" + modelData.value
                  text: modelData.label
                  font.family: root.bar.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  palette.windowText: root.bar.foreground
                  checked: root.holdCycleDraft.indexOf(modelData.value) >= 0
                  enabled: root.holdCycleEditable
                  onClicked: root.toggleHoldCycleMode(modelData.value)
                  onActiveFocusChanged: if (activeFocus) panelScroll.reveal(this)
                }
              }
            }
            Text {
              width: parent.width
              visible: !!root.holdCycle
              text: "Choose at least two modes to cycle through."
              opacity: root.holdCycleDraftValid ? 0.6 : 1.0
              color: root.bar.foreground
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.bodySmall
              wrapMode: Text.Wrap
            }
            Row {
              spacing: Style.space(8)
              visible: !!root.holdCycle
              Button {
                objectName: "applyHoldCycle"
                width: Style.space(100)
                text: "Apply"
                bordered: true
                foreground: root.bar.foreground
                background: root.bar.background
                accent: Color.accent
                fontFamily: root.bar.fontFamily
                enabled: root.holdCycleEditable && root.holdCycleDirty && root.holdCycleDraftValid
                onClicked: root.applyHoldCycle()
              }
              Button {
                objectName: "cancelHoldCycle"
                width: Style.space(100)
                text: "Cancel"
                bordered: true
                foreground: root.bar.foreground
                background: root.bar.background
                accent: Color.accent
                fontFamily: root.bar.fontFamily
                enabled: root.holdCycleEditable && root.holdCycleDirty
                onClicked: root.resetHoldCycleDraft()
              }
            }
          }

          Flow {
            id: touchColumns
            width: parent.width
            visible: root.touchControlsExpanded
            enabled: root.touchControlsExpanded
            spacing: Style.space(16)
            Repeater {
              model: [1, 2]
              delegate: Column {
                id: touchSide
                required property int modelData
                objectName: "touchSide_" + modelData
                width: touchColumns.width >= Style.space(500)
                  ? (touchColumns.width - touchColumns.spacing) / 2 : touchColumns.width
                spacing: Style.space(6)
                visible: root.touchControls.length > 0

                Text {
                  text: touchSide.modelData === 1 ? "Left earbud" : "Right earbud"
                  color: root.bar.foreground
                  font.family: root.bar.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  font.bold: true
                }
                Repeater {
                  model: root.touchControls.filter(function(entry) {
                    return entry.side === touchSide.modelData && entry.button === 1
                      && !(root.holdCycleAvailable && entry.action === 4)
                  })
                  delegate: Column {
                    id: touchRow
                    required property var modelData
                    width: touchSide.width
                    spacing: Style.space(2)
                    Text {
                      width: parent.width
                      text: touchRow.modelData.action_label
                      color: root.bar.foreground
                      opacity: 0.72
                      font.family: root.bar.fontFamily
                      font.pixelSize: Style.font.bodySmall
                    }
                    Dropdown {
                      objectName: "touchSelector_" + touchRow.modelData.side + "_" + touchRow.modelData.action
                      width: parent.width
                      showLabel: false
                      foreground: root.bar.foreground
                      fontFamily: root.bar.fontFamily
                      visible: touchRow.modelData.writable
                      property var choices: {
                        var options = touchRow.modelData.options || []
                        if (!options.some(function(o) { return o.value === touchRow.modelData.function }))
                          return [{value: touchRow.modelData.function, label: touchRow.modelData.function_label}].concat(options)
                        return options
                      }
                      options: choices
                      value: String(touchRow.modelData.function)
                      enabled: root.connection === "connected" && root.pendingRequestId < 0
                        && snapshot && snapshot.session_connected === true
                      onChanged: function(selectedValue) {
                        var selectedFunction = Number(selectedValue)
                        if (selectedFunction !== touchRow.modelData.function)
                          root.setTouchControl(touchRow.modelData.side, touchRow.modelData.action, selectedFunction)
                        // Keep showing confirmed state until readback arrives,
                        // including when validation or transmission fails.
                        value = Qt.binding(function() { return String(touchRow.modelData.function) })
                      }
                    }
                    Text {
                      width: parent.width
                      visible: !touchRow.modelData.writable
                      text: touchRow.modelData.function_label
                      color: root.bar.foreground
                      font.family: root.bar.fontFamily
                      font.pixelSize: Style.font.bodySmall
                      wrapMode: Text.Wrap
                    }
                  }
                }
              }
            }
          }
          Text {
            width: parent.width
            visible: root.touchControlsExpanded
            text: "Call gestures use the earbuds’ fixed settings."
            color: root.bar.foreground
            opacity: 0.6
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.bodySmall
            wrapMode: Text.Wrap
          }
        }

        Column {
          width: parent.width
          spacing: Style.space(5)
          visible: snapshot && snapshot.capabilities
            && snapshot.capabilities.indexOf("find_earbuds") !== -1

          Button {
            id: findEarbudsButton
            objectName: "findEarbudsButton"
            width: parent.width
            height: Math.max(implicitHeight, Style.space(32))
            text: root.finding ? "Stop" : "Find my earbuds"
            tooltipText: root.finding ? "" : "Remove earbuds before playing a sound."
            selected: root.finding
            bordered: true
            leftAlign: true
            enabled: root.connection === "connected" && snapshot
              && snapshot.session_connected === true && root.pendingRequestId < 0
            opacity: enabled ? 1.0 : 0.5
            foreground: root.bar.foreground
            background: root.bar.background
            accent: Color.accent
            fontFamily: root.bar.fontFamily
            onClicked: root.findEarbuds()

            Text {
              objectName: "findEarbudsIcon"
              anchors.right: parent.right
              anchors.rightMargin: Style.space(12)
              anchors.verticalCenter: parent.verticalCenter
              text: root.finding ? "■" : "▶"
              textFormat: Text.PlainText
              color: findEarbudsButton.foreground
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.body
            }
          }

          Text {
            objectName: "findEarbudsHint"
            visible: root.pendingKind === "find" || root.finding
            width: parent.width
            text: root.pendingKind === "find" ? (root.pendingMode === "find"
                ? "Starting sound…" : "Stopping sound…")
              : root.findState === "unknown" ? "Search status unknown. Use Stop to end the sound."
              : root.finding ? "Sound playing · automatic stop after 50 s."
              : ""
            textFormat: Text.PlainText
            color: root.bar.foreground
            opacity: 0.7
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.bodySmall
            wrapMode: Text.Wrap
          }
        }

        Column {
          id: compatibilityNotice
          objectName: "compatibilityNotice"
          width: parent.width
          spacing: Style.space(3)
          visible: root.compatibilityNoticeShown

          Text {
            width: parent.width
            text: root.compatibilityLabel
            textFormat: Text.PlainText
            color: root.bar.foreground
            opacity: root.communityTestedDevice ? 0.72 : 0.88
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.bodySmall
            font.bold: root.experimentalDevice
          }

          Text {
            width: parent.width
            visible: root.experimentalDevice
            text: "This model has not been hardware verified."
            textFormat: Text.PlainText
            color: root.bar.foreground
            opacity: 0.72
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.bodySmall
            wrapMode: Text.Wrap
          }

        }

        Column {
          id: reportSection
          objectName: "diagnosticReportSection"
          width: parent.width
          spacing: Style.space(3)
          visible: root.reportAvailable

          Text {
            id: reportAction
            objectName: "reportAction"
            visible: root.reportActionShown
            text: root.reportActionLabel
            textFormat: Text.PlainText
            color: Color.accent
            opacity: 0.82
            font.family: root.bar.fontFamily
            font.pixelSize: Style.font.bodySmall
            font.underline: reportActionMouse.containsMouse

            MouseArea {
              id: reportActionMouse
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: root.reportDetailsOpen = true
            }
          }

          Column {
            width: parent.width
            spacing: Style.space(3)
            visible: root.reportDetailsOpen

            Text {
              width: parent.width
              text: "The report includes versions, capabilities, connection state and safe protocol counters. Addresses, names, paths and secrets are omitted or redacted. Nothing is uploaded."
              textFormat: Text.PlainText
              color: root.bar.foreground
              opacity: 0.72
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.bodySmall
              wrapMode: Text.Wrap
            }

            Text {
              id: saveReportAction
              objectName: "saveDiagnosticReportAction"
              visible: !root.reportSaved
              text: "Choose where to save report…"
              textFormat: Text.PlainText
              color: Color.accent
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.underline: saveReportMouse.containsMouse
              enabled: root.pendingRequestId < 0
              opacity: enabled ? 1.0 : 0.5

              MouseArea {
                id: saveReportMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: parent.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                enabled: parent.enabled
                onClicked: root.openReportFileDialog()
              }
            }

            Column {
              id: reportSavedGuidance
              objectName: "reportSavedGuidance"
              visible: root.reportSaved
              width: parent.width
              spacing: Style.space(3)

              Text {
                objectName: "reportSavedConfirmation"
                width: parent.width
                text: "Your diagnostic report has been saved."
                textFormat: Text.PlainText
                color: root.bar.foreground
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
                font.bold: true
                wrapMode: Text.Wrap
              }

              Text {
                objectName: "reportSavedLocation"
                width: parent.width
                text: root.savedReportLocation !== ""
                  ? "Saved to: " + root.savedReportLocation
                  : "Saved as: " + root.savedReportFilename
                textFormat: Text.PlainText
                color: root.bar.foreground
                opacity: 0.76
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
                wrapMode: Text.WrapAnywhere
              }

              Text {
                width: parent.width
                text: "Open a GitHub issue and manually attach the report file so the problem can be investigated. Nothing is uploaded automatically."
                textFormat: Text.PlainText
                color: root.bar.foreground
                opacity: 0.72
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
                wrapMode: Text.Wrap
              }

              Text {
                id: openIssueAction
                objectName: "openCompatibilityIssueAction"
                text: root.reportSubmissionActionLabel
                textFormat: Text.PlainText
                color: Color.accent
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
                font.underline: openIssueMouse.containsMouse

                MouseArea {
                  id: openIssueMouse
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: root.openReportIssue()
                }
              }
            }
          }
        }

        Text {
          width: parent.width
          visible: root.outcome !== "" || root.pendingRequestId >= 0
          textFormat: Text.PlainText
          text: root.pendingRequestId >= 0
            ? (root.pendingKind === "eq_status" ? "Reading native EQ…"
              : root.pendingKind === "touch_read" ? "Reading touch controls…"
              : root.pendingKind === "diagnostic_report" ? "Saving diagnostic report…"
              : "Verifying " + BarModel.titleCase(root.pendingMode) + "…") : root.outcome
          color: root.bar.foreground
          font.family: root.bar.fontFamily
          font.pixelSize: Style.font.bodySmall
          wrapMode: Text.Wrap
        }
      }
    }
  }

  FileDialog {
    id: reportFileDialog
    title: "Save compatibility report"
    fileMode: FileDialog.SaveFile
    // The GTK native chooser can abort the in-process Quickshell host while
    // creating its GVFS directory monitor. Keep the chooser inside Qt Quick.
    options: FileDialog.DontUseNativeDialog
    currentFolder: {
      var documents = StandardPaths.writableLocation(StandardPaths.DocumentsLocation)
      return String(documents || "") !== "" ? documents
        : StandardPaths.writableLocation(StandardPaths.HomeLocation)
    }
    defaultSuffix: "txt"
    nameFilters: ["Text reports (*.txt)"]
    onAccepted: root.acceptReportFile(selectedFile)
    onRejected: root.cancelDiagnosticReport()
  }

  IpcHandler {
    target: "oneplus-buds.control"

    function diagPing(): string {
      return root.diagPing()
    }

    function open(): string {
      root.popupOpen = true
      return "ok"
    }

    function diagnostic(payload: string): string {
      return root.diagnostic(payload)
    }

    function status(): string {
      return JSON.stringify({
        service: root.budsService !== null,
        connection: root.connection,
        snapshot: root.snapshot !== null,
        device_status: root.snapshot ? root.snapshot.status : null,
        session_connected: root.snapshot ? root.snapshot.session_connected : false,
        generation: root.snapshot ? root.snapshot.generation : 0,
        lifecycle: root.budsService && root.budsService.lifecycleObservations
          ? root.budsService.lifecycleObservations : [],
        label: root.presentation.label,
        expanded: root.batteryExpanded,
        width: root.width,
        popup_open: root.popupOpen,
        panel_width: popup.contentWidth,
        panel_height: popup.contentHeight,
        two_column: root.useTwoColumnLayout,
        anc_modes: root.ancOptions.map(function(option) { return option.value }),
        current_anc: root.currentAncMode,
        find_state: root.findState,
        pending: root.pendingRequestId >= 0,
        eq: root.eqStatus,
        bass_level: root.snapshot ? root.snapshot.bass_level : null,
        feature_switches: root.snapshot ? root.snapshot.feature_switches : null,
        touch_controls: root.touchControls,
        hold_cycle: root.holdCycle,
        anc_labels: root.snapshot ? root.snapshot.anc_labels : null,
        capabilities: root.snapshot ? root.snapshot.capabilities : null,
        compatibility: root.compatibilityKind,
        compatibility_notice: root.compatibilityNoticeShown,
        report_available: root.reportAvailable,
        report_action: reportAction.visible,
        diagnostic_result: root.diagnosticResult,
        diag_api: 2,
        panel_geometry: JSON.stringify({
          popup_x: root.popupX,
          popup_width: root.popupWidth,
          content_width: root.contentWidth,
          sections_width: root.controlSectionsWidth,
          eq_column_width: root.eqColumnWidth,
          band_flow_width: root.bandFlowWidth,
          scrollbar_width: root.scrollbarWidth,
          scrollbar_visible: root.scrollbarVisible,
          scrollbar_active: root.scrollbarActive,
          view_height: root.viewHeight,
          content_height: root.contentHeight,
          screen_width: root.screenWidth
        }),
        last_response: root.lastResponse ? root.lastResponse : null,
        error: root.budsService ? String(root.budsService.lastError || "") : ""
      })
    }
  }

}
