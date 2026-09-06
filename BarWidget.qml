import QtQuick
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

  property bool popupOpen: false
  property int pendingRequestId: -1
  property string pendingMode: ""
  property string outcome: ""

  function close() { popupOpen = false }

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
    outcome = ""
  }

  onLastResponseChanged: {
    var response = lastResponse
    if (!response || Number(response.request_id) !== pendingRequestId) return
    pendingRequestId = -1
    pendingMode = ""
    if (response.ok === true && response.result && response.result.verified === true) {
      outcome = "Verified on earbuds"
    } else {
      var detail = response.error && response.error.message
        ? String(response.error.message) : "Change could not be verified"
      outcome = detail
    }
  }

  visible: true
  implicitWidth: content.implicitWidth + Style.space(14)
  implicitHeight: barSize

  Row {
    id: content
    anchors.centerIn: parent
    spacing: Style.space(5)

    Text {
      anchors.verticalCenter: parent.verticalCenter
      textFormat: Text.PlainText
      text: root.presentation.icon
      color: root.presentation.connected
        ? root.bar.barForeground : Qt.darker(root.bar.barForeground, 1.5)
      font.family: root.bar.fontFamily
      font.pixelSize: Style.font.body
    }

    Text {
      anchors.verticalCenter: parent.verticalCenter
      visible: text !== ""
      textFormat: Text.PlainText
      text: root.presentation.label
      color: root.bar.barForeground
      font.family: root.bar.fontFamily
      font.pixelSize: Style.font.bodySmall
    }
  }

  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    acceptedButtons: Qt.LeftButton
    cursorShape: root.ancOptions.length ? Qt.PointingHandCursor : Qt.ArrowCursor
    onClicked: if (root.ancOptions.length) root.popupOpen = !root.popupOpen
    onEntered: if (root.bar) root.bar.showTooltip(root, root.presentation.tooltip)
    onExited: if (root.bar) root.bar.hideTooltip(root)
  }

  PopupCard {
    id: popup
    anchorItem: root
    bar: root.bar
    owner: root
    open: root.popupOpen
    contentWidth: popup.fittedContentWidth(Style.space(440))
    contentHeight: popup.fittedContentHeight(panelContent.implicitHeight)

    Column {
      id: panelContent
      anchors.fill: parent
      spacing: Style.space(10)

      Text {
        width: parent.width
        textFormat: Text.PlainText
        text: root.snapshot && root.snapshot.status && root.snapshot.status.model
          ? String(root.snapshot.status.model) : "OnePlus earbuds"
        color: root.bar.foreground
        font.family: root.bar.fontFamily
        font.pixelSize: Style.font.subtitle
        font.bold: true
        elide: Text.ElideRight
      }

      Text {
        width: parent.width
        textFormat: Text.PlainText
        text: root.pendingRequestId >= 0
          ? "Verifying " + root.pendingMode + "…"
          : (root.outcome || "Noise control")
        color: root.bar.foreground
        font.family: root.bar.fontFamily
        font.pixelSize: Style.font.bodySmall
      }

      ButtonGroup {
        options: root.ancOptions
        value: root.currentAncMode
        enabled: root.connection === "connected" && root.pendingRequestId < 0
        opacity: enabled ? 1.0 : 0.5
        foreground: root.bar.foreground
        background: root.bar.background
        accent: Color.accent
        fontFamily: root.bar.fontFamily
        focusable: true
        onChanged: function(mode) { root.selectAnc(mode) }
      }
    }
  }

  IpcHandler {
    target: "oneplus-buds.control"

    function status(): string {
      return JSON.stringify({
        service: root.budsService !== null,
        connection: root.connection,
        snapshot: root.snapshot !== null,
        label: root.presentation.label,
        anc_modes: root.ancOptions.map(function(option) { return option.value }),
        current_anc: root.currentAncMode,
        pending: root.pendingRequestId >= 0,
        error: root.budsService ? String(root.budsService.lastError || "") : ""
      })
    }
  }

}
