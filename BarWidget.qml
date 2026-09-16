import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Dialogs
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
  readonly property bool experimentalDevice: compatibilityKind === "experimental"
  readonly property bool communityTestedDevice: compatibilityKind === "community_tested"
  readonly property bool compatibilityNoticeShown: experimentalDevice || communityTestedDevice
  readonly property bool reportAvailable: connection === "connected"
    && snapshot !== null && snapshot.status !== null
  readonly property bool reportActionShown: reportAvailable && !reportDetailsOpen
  readonly property var selectedCustom: customEqEntries.length > 0
    ? customEqEntries[Math.max(0, Math.min(customSlotIndex, customEqEntries.length - 1))] : null
  readonly property bool eqAvailable: !!(snapshot && snapshot.capabilities
    && snapshot.capabilities.indexOf("eq") !== -1)
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

  property bool popupOpen: false
  property int pendingRequestId: -1
  property string pendingMode: ""
  property string outcome: ""
  property string pendingKind: ""
  property int customSlotIndex: 0
  property bool customSelectionDirty: false
  property bool reportDetailsOpen: false
  property bool reportSaved: false

  onCompatibilityKindChanged: {
    reportDetailsOpen = false
    reportSaved = false
  }

  function syncCustomSlotFromEq() {
    if (!eqStatus || !customEqEntries.length) return
    for (var i = 0; i < customEqEntries.length; i++) {
      if (customEqEntries[i].eq_id === eqStatus.current_id) {
        customSlotIndex = i
        return
      }
    }
    customSlotIndex = 0
  }

  function selectCustomSlot(index) {
    if (index < 0 || index >= customEqEntries.length) return
    customSlotIndex = index
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
      customSelectionDirty = false
      syncCustomSlotFromEq()
      collapseTimer.stop()
      if (bar) bar.hideTooltip(root)
      if (budsService && connection === "connected" && snapshot
          && snapshot.capabilities && snapshot.capabilities.indexOf("eq") !== -1
          && pendingRequestId < 0) {
        var requestId = budsService.eqStatus()
        if (requestId !== null) {
          pendingRequestId = requestId
          pendingKind = "eq_status"
        }
      }
    } else if (!hitArea.containsMouse) {
      collapseTimer.restart()
    }
  }

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

  function applyCustomEq() {
    if (!selectedCustom || !budsService || pendingRequestId >= 0) return
    var gains = []
    for (var i = 0; i < bandRepeater.count; i++)
      gains.push(Number(bandRepeater.itemAt(i).gainValue))
    var requestId = budsService.setCustomEq(selectedCustom.eq_id, gains)
    if (requestId === null) { outcome = "Could not start request"; return }
    pendingRequestId = requestId
    pendingKind = "custom_eq"
    pendingMode = selectedCustom.name
    outcome = ""
  }

  function saveDiagnosticReport(fileUrl) {
    if (!budsService || pendingRequestId >= 0) return
    var requestId = budsService.saveDiagnosticReport(String(fileUrl || ""))
    if (requestId === null) { outcome = "Could not start report"; return }
    pendingRequestId = requestId
    pendingKind = "diagnostic_report"
    pendingMode = ""
    outcome = ""
    reportSaved = false
  }

  onLastResponseChanged: {
    var response = lastResponse
    if (!response || Number(response.request_id) !== pendingRequestId) return
    pendingRequestId = -1
    pendingMode = ""
    var completedKind = pendingKind
    pendingKind = ""
    if (completedKind === "diagnostic_report") {
      if (response.ok === true) {
        reportSaved = true
        outcome = "Diagnostic report saved"
      } else {
        outcome = response.error && response.error.message
          ? String(response.error.message) : "Diagnostic report could not be saved"
      }
      return
    }
    if (response.ok === true && (completedKind === "eq_status"
        || completedKind === "eq" || completedKind === "custom_eq")) {
      customSelectionDirty = false
      syncCustomSlotFromEq()
    }
    if (response.ok === true && response.result && response.result.verified === true) {
      outcome = "Verified on earbuds"
    } else if (response.ok === true && completedKind === "eq_status") {
      outcome = ""
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

  PopupCard {
    id: popup
    anchorItem: root
    bar: root.bar
    owner: root
    open: root.popupOpen
    contentWidth: popup.fittedContentWidth(root.useTwoColumnLayout
      ? Style.space(600) : Style.space(320))
    contentHeight: popup.fittedContentHeight(panelContent.implicitHeight)

    Flickable {
      id: panelScroll
      anchors.fill: parent
      contentWidth: width
      contentHeight: panelContent.implicitHeight
      clip: true
      boundsBehavior: Flickable.StopAtBounds
      flickableDirection: Flickable.VerticalFlick
      Controls.ScrollBar.vertical: Controls.ScrollBar {}

      function reveal(item) {
        var top = item.mapToItem(panelContent, 0, 0).y
        if (top < contentY) contentY = top
        else if (top + item.height > contentY + height)
          contentY = top + item.height - height
      }

      Column {
        id: panelContent
        width: panelScroll.width
        spacing: Style.space(12)

        Text {
          width: parent.width
          textFormat: Text.PlainText
          text: root.snapshot && root.snapshot.status && root.snapshot.status.model
            ? String(root.snapshot.status.model) : "OnePlus earbuds"
          color: root.bar.foreground
          font.family: root.bar.fontFamily
          font.pixelSize: Style.font.subtitle
          font.bold: true
          wrapMode: Text.Wrap
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
            : noiseColumn.implicitHeight
              + (eqColumn.visible ? Style.space(14) + eqColumn.implicitHeight : 0)

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

            Text {
              width: parent.width
              text: "Earbud EQ"
              textFormat: Text.PlainText
              color: root.bar.foreground
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
            }

            Text {
              width: parent.width
              text: root.eqStatus ? "Current: " + root.eqStatus.current_name : "Loading native EQ…"
              textFormat: Text.PlainText
              color: root.bar.foreground
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.bodySmall
              wrapMode: Text.Wrap
            }

            Flow {
              id: eqPresetFlow
              width: parent.width
              spacing: Style.space(5)

              Repeater {
                model: root.eqPresets
                delegate: Button {
                  required property var modelData
                  width: modelData.name.length > 22 ? eqPresetFlow.width
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

            Text {
              width: parent.width
              visible: root.customEqEntries.length > 0
              text: "Custom EQ"
              textFormat: Text.PlainText
              color: root.bar.foreground
              font.family: root.bar.fontFamily
              font.pixelSize: Style.font.bodySmall
              font.bold: true
              topPadding: Style.space(3)
            }

            Controls.ComboBox {
              width: parent.width
              visible: root.customEqEntries.length > 0
              model: root.customEqEntries.map(function(entry) { return entry.name })
              currentIndex: root.customSlotIndex
              enabled: root.pendingRequestId < 0
              onActivated: function(index) { root.selectCustomSlot(index) }
            }

            Flow {
              id: customBandFlow
              width: parent.width
              spacing: Style.space(5)

              Repeater {
                id: bandRepeater
                model: root.selectedCustom ? root.selectedCustom.bands : []
                delegate: Column {
                  required property var modelData
                  property alias gainValue: gainBox.value
                  width: (customBandFlow.width - customBandFlow.spacing) / 2
                  spacing: Style.space(2)

                  Text {
                    width: parent.width
                    text: modelData.frequency_hz >= 1000
                      ? (modelData.frequency_hz / 1000) + " kHz" : modelData.frequency_hz + " Hz"
                    color: root.bar.foreground
                    font.family: root.bar.fontFamily
                    font.pixelSize: Style.font.bodySmall
                  }
                  Controls.SpinBox {
                    id: gainBox
                    width: parent.width
                    from: root.selectedCustom ? root.selectedCustom.min_gain_db : -6
                    to: root.selectedCustom ? root.selectedCustom.max_gain_db : 6
                    stepSize: root.eqStatus && root.eqStatus.gain_step_db
                      ? root.eqStatus.gain_step_db : 1
                    value: modelData.gain_db
                    editable: true
                    enabled: root.snapshot && root.snapshot.custom_eq_write_verified === true
                      && root.pendingRequestId < 0
                    textFromValue: function(value) { return (value > 0 ? "+" : "") + value + " dB" }
                    valueFromText: function(text) { return parseInt(text) || 0 }
                  }
                }
              }
            }

            Button {
              width: parent.width
              height: Math.max(implicitHeight, Style.space(32))
              visible: root.selectedCustom !== null
              text: "Apply " + (root.selectedCustom ? root.selectedCustom.name : "custom EQ")
              bordered: true
              leftAlign: true
              enabled: root.snapshot && root.snapshot.custom_eq_write_verified === true
                && root.pendingRequestId < 0
              opacity: enabled ? 1.0 : 0.5
              foreground: root.bar.foreground
              background: root.bar.background
              accent: Color.accent
              fontFamily: root.bar.fontFamily
              onClicked: root.applyCustomEq()
            }
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
                onClicked: reportFileDialog.open()
              }
            }

            Text {
              id: openIssueAction
              objectName: "openCompatibilityIssueAction"
              visible: root.reportSaved
              text: "Open GitHub issue"
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
                onClicked: Qt.openUrlExternally(
                  "https://github.com/GazzasaurusRex/oneplus-buds-omarchy/issues/new/choose")
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
    defaultSuffix: "json"
    nameFilters: ["JSON reports (*.json)"]
    onAccepted: root.saveDiagnosticReport(selectedFile)
  }

  IpcHandler {
    target: "oneplus-buds.control"

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
        pending: root.pendingRequestId >= 0,
        eq: root.eqStatus,
        compatibility: root.compatibilityKind,
        compatibility_notice: root.compatibilityNoticeShown,
        report_available: root.reportAvailable,
        report_action: reportAction.visible,
        error: root.budsService ? String(root.budsService.lastError || "") : ""
      })
    }
  }

}
