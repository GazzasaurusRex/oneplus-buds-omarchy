import QtQuick
import Quickshell.Io
import "BridgeModel.js" as BridgeModel

Item {
  id: root

  property var shell: null
  property var manifest: null
  property var state: BridgeModel.initialState()
  property int nextRequestId: 1
  property bool stopping: false
  property var lifecycleObservations: []
  // The helper is a child process that can die (driver error, vanished D-Bus
  // object, killed process). Restart it with a backoff instead of staying dead.
  property int restartAttempt: 0
  property int restartDelayMs: 1000
  property var pluginUpdate: ({
    eligible: false, available: false, view_url: "",
    manual_command: "omarchy plugin update oneplus-buds.control", commits_behind: 0
  })

  function observeLifecycle(phase, productId) {
    lifecycleObservations = lifecycleObservations.concat([{
      phase: phase, unix_ms: Date.now(), product_id: productId || null
    }]).slice(-32)
  }

  function scheduleHelperRestart() {
    if (stopping) return
    restartAttempt += 1
    restartDelayMs = Math.min(restartDelayMs * 2, 30000)
    restartTimer.interval = restartDelayMs
    restartTimer.restart()
  }

  readonly property string helperPath: localPath(Qt.resolvedUrl("oneplus-buds-bridge"))
  readonly property string pluginRoot: localPath(Qt.resolvedUrl(".")).replace(/\/$/, "")
  readonly property string updateHelperPath: localPath(
    Qt.resolvedUrl("scripts/check_plugin_update.py"))
  readonly property string connection: String(state.connection || "stopped")
  readonly property var snapshot: state.snapshot || null
  readonly property var lastResponse: state.lastResponse || null
  readonly property string lastError: String(state.lastError || "")

  function localPath(url) {
    var value = String(url || "")
    return value.indexOf("file://") === 0
      ? decodeURIComponent(value.slice(7)) : value
  }

  function startHelper() {
    if (!stopping && helperPath && !helper.running) {
      helper.command = [helperPath]
      helper.running = true
    }
  }

  function startPluginUpdateCheck() {
    if (!stopping && !updateCheck.running && updateHelperPath && pluginRoot) {
      updateCheck.command = [updateHelperPath, pluginRoot]
      updateCheck.running = true
    }
  }

  function handlePluginUpdate(line) {
    try {
      var value = JSON.parse(String(line || ""))
      var url = String(value.view_url || "")
      var command = String(value.manual_command || "")
      var safe = value.available === true
        && command === "omarchy plugin update oneplus-buds.control"
      var safeUrl = url.indexOf("https://github.com/") === 0
        && url.length <= 500
      pluginUpdate = {
        eligible: value.eligible === true,
        available: safe,
        view_url: safe && safeUrl ? url : "",
        manual_command: "omarchy plugin update oneplus-buds.control",
        commits_behind: safe ? Math.max(1, Math.min(9999, Number(value.commits_behind) || 1)) : 0
      }
    } catch (_error) {
      pluginUpdate = {
        eligible: false, available: false, view_url: "",
        manual_command: "omarchy plugin update oneplus-buds.control", commits_behind: 0
      }
    }
  }

  function handleLine(line) {
    var parsed = BridgeModel.parseLine(line)
    if (!parsed.ok) {
      state = {
        connection: state.connection,
        snapshot: state.snapshot,
        lastResponse: state.lastResponse,
        lastError: parsed.error
      }
      return
    }
    var previous = state
    state = BridgeModel.applyMessage(state, parsed.message)
    if (state.connection !== previous.connection)
      observeLifecycle("frontend_" + state.connection, null)
    // A working connection resets the restart backoff.
    if (state.connection === "connected" && previous.connection !== "connected") {
      restartAttempt = 0
      restartDelayMs = 1000
    }
    var status = state.snapshot && state.snapshot.status
    var oldStatus = previous.snapshot && previous.snapshot.status
    if (status && state.snapshot.session_connected
        && (!oldStatus || !previous.snapshot.session_connected
            || oldStatus.product_id !== status.product_id))
      observeLifecycle("frontend_first_usable", status.product_id)
  }

  function request(command, parameters) {
    if (!helper.running) return null
    var requestId = nextRequestId++
    helper.write(JSON.stringify({
      request_id: requestId,
      command: command,
      parameters: parameters === undefined ? {} : parameters
    }) + "\n")
    return requestId
  }

  function refresh() {
    return request("refresh", {})
  }

  function setAnc(mode) {
    return request("set_anc", { mode: String(mode || "") })
  }

  function eqStatus() {
    return request("eq_status", {})
  }

  function setEq(preset) {
    return request("set_eq", { preset: String(preset || "") })
  }

  function setCustomEq(entryId, gains, deviceId) {
    var params = { entry_id: Number(entryId), gains_db: gains }
    if (deviceId) params.device_id = String(deviceId)
    return request("set_custom_eq", params)
  }

  function createCustomEq(name, deviceId) {
    var params = { name: String(name || "") }
    if (deviceId) params.device_id = String(deviceId)
    return request("create_custom_eq", params)
  }

  function renameCustomEq(entryId, name, deviceId) {
    var params = { entry_id: Number(entryId), name: String(name || "") }
    if (deviceId) params.device_id = String(deviceId)
    return request("rename_custom_eq", params)
  }

  function deleteCustomEq(entryId, deviceId) {
    var params = { entry_id: Number(entryId) }
    if (deviceId) params.device_id = String(deviceId)
    return request("delete_custom_eq", params)
  }

  function saveDiagnosticReport(path) {
    return request("save_diagnostic_report", { path: String(path || "") })
  }

  function setTouchControl(side, action, value) {
    return request("set_touch_control", {
      side: Number(side), action: Number(action), function: Number(value)
    })
  }

  function setHoldCycle(modes) {
    return request("set_hold_cycle", { modes: modes })
  }

  function setFeatureSwitch(feature, enabled) {
    return request("set_feature_switch", {
      feature: String(feature || ""), enabled: enabled === true
    })
  }

  function setBassLevel(level) {
    return request("set_bass_level", { level: Number(level) })
  }

  function findEarbuds(ringing, deviceId) {
    var parameters = { ringing: ringing !== false }
    var target = deviceId || (snapshot && snapshot.find_device_id)
    if (target) parameters.device_id = String(target)
    return request("find_earbuds", parameters)
  }

  onHelperPathChanged: startHelper()

  Component.onCompleted: {
    startHelper()
    updateCheckDelay.start()
  }

  Component.onDestruction: {
    stopping = true
    restartTimer.stop()
    updateCheckDelay.stop()
    updateCheck.running = false
    helper.running = false
  }


  Timer {
    id: restartTimer
    interval: 2000
    repeat: false
    onTriggered: {
      if (!root.stopping) {
        root.observeLifecycle("frontend_helper_restart", null)
        root.startHelper()
      }
    }
  }
  Timer {
    id: updateCheckDelay
    interval: 2500
    repeat: false
    onTriggered: root.startPluginUpdateCheck()
  }
  Process {
    id: updateCheck
    command: []
    stdout: SplitParser {
      onRead: function(line) { root.handlePluginUpdate(line) }
    }
  }
  Process {
    id: helper
    stdinEnabled: true
    command: []

    stdout: SplitParser {
      onRead: function(line) { root.handleLine(line) }
    }

    stderr: SplitParser {
      onRead: function(_line) {
        root.state = {
          connection: root.state.connection,
          snapshot: root.state.snapshot,
          lastResponse: root.state.lastResponse,
          lastError: "Backend process reported an error"
        }
      }
    }

    onExited: function(_exitCode) {
      if (!root.stopping) {
        root.state = {
          connection: "stopped",
          snapshot: root.state.snapshot,
          lastResponse: root.state.lastResponse,
          lastError: root.state.lastError || "Backend process stopped"
        }
        root.scheduleHelperRestart()
      }
    }
  }
}
