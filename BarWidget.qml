import QtQuick
import Quickshell
import qs.Ui

BarWidget {
  id: root
  moduleName: "oneplus-buds.control"

  readonly property var budsService: bar && bar.shell
    ? bar.shell.serviceFor(moduleName) : null
  readonly property string connection: budsService
    ? String(budsService.connection || "stopped") : "unavailable"
  readonly property bool hasSnapshot: budsService && budsService.snapshot !== null

  onConnectionChanged: console.log(
    "oneplus-buds.control frontend-state connection=" + connection
      + " snapshot=" + hasSnapshot)
  Component.onCompleted: console.log(
    "oneplus-buds.control frontend-ready service=" + (budsService !== null)
      + " connection=" + connection + " snapshot=" + hasSnapshot)

  IpcHandler {
    target: "oneplus-buds.control"

    function status(): string {
      return JSON.stringify({
        service: root.budsService !== null,
        connection: root.connection,
        snapshot: root.hasSnapshot,
        error: root.budsService ? String(root.budsService.lastError || "") : ""
      })
    }
  }

  // This milestone proves plugin/service loading only. The capability-driven
  // visual widget and control panel intentionally come later.
  visible: false
  implicitWidth: 0
  implicitHeight: barSize
}
