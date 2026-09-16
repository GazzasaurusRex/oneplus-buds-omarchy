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

  function observeLifecycle(phase, productId) {
    lifecycleObservations = lifecycleObservations.concat([{
      phase: phase, unix_ms: Date.now(), product_id: productId || null
    }]).slice(-32)
  }

  readonly property string helperPath: localPath(Qt.resolvedUrl("oneplus-buds-bridge"))
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

  function setCustomEq(entryId, gains) {
    return request("set_custom_eq", { entry_id: Number(entryId), gains_db: gains })
  }

  function saveDiagnosticReport(path) {
    return request("save_diagnostic_report", { path: String(path || "") })
  }

  onHelperPathChanged: startHelper()

  Component.onCompleted: startHelper()

  Component.onDestruction: {
    stopping = true
    helper.running = false
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
      }
    }
  }
}
