import QtQuick
import qs.Ui

BarWidget {
  id: root
  moduleName: "oneplus-buds.control"

  readonly property var budsService: bar && bar.shell
    ? bar.shell.serviceFor(moduleName) : null

  // This milestone proves plugin/service loading only. The capability-driven
  // visual widget and control panel intentionally come later.
  visible: false
  implicitWidth: 0
  implicitHeight: barSize
}
