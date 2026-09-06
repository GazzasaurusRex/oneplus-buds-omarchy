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

  readonly property string sourceDir: manifest && manifest.__sourceDir
    ? String(manifest.__sourceDir) : ""
  readonly property string helperPath: sourceDir ? sourceDir + "/oneplus-buds-bridge" : ""
  readonly property string connection: String(state.connection || "stopped")
  readonly property var snapshot: state.snapshot || null
  readonly property var lastResponse: state.lastResponse || null
  readonly property string lastError: String(state.lastError || "")

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
    state = BridgeModel.applyMessage(state, parsed.message)
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

  onHelperPathChanged: startHelper()

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
