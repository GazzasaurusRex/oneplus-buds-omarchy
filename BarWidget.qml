import QtQuick
import QtQuick.Controls as Controls
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
  readonly property var selectedCustom: customEqEntries.length > 0
    ? customEqEntries[Math.max(0, Math.min(customSlotIndex, customEqEntries.length - 1))] : null

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
  onEqStatusChanged: {
    if (!eqStatus || !customEqEntries.length) return
    for (var i = 0; i < customEqEntries.length; i++) {
      if (customEqEntries[i].eq_id === eqStatus.current_id) {
        customSlotIndex = i
        return
      }
    }
    customSlotIndex = 0
  }
  property bool hoverExpanded: false
  readonly property bool batteryExpanded: !vertical && presentation.label !== ""
    && (hoverExpanded || popupOpen)

  onPopupOpenChanged: {
    if (popupOpen) {
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

  onLastResponseChanged: {
    var response = lastResponse
    if (!response || Number(response.request_id) !== pendingRequestId) return
    pendingRequestId = -1
    pendingMode = ""
    var completedKind = pendingKind
    pendingKind = ""
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
    contentWidth: popup.fittedContentWidth(Style.space(320))
    contentHeight: popup.fittedContentHeight(Math.max(Style.space(380), panelContent.implicitHeight))

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

        Repeater {
          model: BarModel.ancGroups(root.snapshot)

          delegate: Column {
            id: section
            required property var modelData
            width: panelContent.width
            spacing: Style.space(6)

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
                height: Math.max(implicitHeight, Style.space(36))
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


        Column {
          width: parent.width
          spacing: Style.space(6)
          visible: !!(root.snapshot && root.snapshot.capabilities
            && root.snapshot.capabilities.indexOf("eq") !== -1)

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
          }

          Repeater {
            model: root.eqPresets
            delegate: Button {
              required property var modelData
              width: parent.width
              height: Math.max(implicitHeight, Style.space(36))
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

          Controls.ComboBox {
            width: parent.width
            visible: root.customEqEntries.length > 0
            model: root.customEqEntries.map(function(entry) { return entry.name })
            currentIndex: root.customSlotIndex
            enabled: root.pendingRequestId < 0
            onActivated: function(index) { root.customSlotIndex = index }
          }

          Repeater {
            id: bandRepeater
            model: root.selectedCustom ? root.selectedCustom.bands : []
            delegate: Row {
              required property var modelData
              property alias gainValue: gainBox.value
              width: parent.width
              spacing: Style.space(8)

              Text {
                width: parent.width - gainBox.width - parent.spacing
                anchors.verticalCenter: parent.verticalCenter
                text: modelData.frequency_hz >= 1000
                  ? (modelData.frequency_hz / 1000) + " kHz" : modelData.frequency_hz + " Hz"
                color: root.bar.foreground
                font.family: root.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
              }
              Controls.SpinBox {
                id: gainBox
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

          Button {
            width: parent.width
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

        Text {
          width: parent.width
          visible: root.outcome !== "" || root.pendingRequestId >= 0
          textFormat: Text.PlainText
          text: root.pendingRequestId >= 0
            ? (root.pendingKind === "eq_status" ? "Reading native EQ…"
              : "Verifying " + BarModel.titleCase(root.pendingMode) + "…") : root.outcome
          color: root.bar.foreground
          font.family: root.bar.fontFamily
          font.pixelSize: Style.font.bodySmall
          wrapMode: Text.Wrap
        }
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
        anc_modes: root.ancOptions.map(function(option) { return option.value }),
        current_anc: root.currentAncMode,
        pending: root.pendingRequestId >= 0,
        eq: root.eqStatus,
        error: root.budsService ? String(root.budsService.lastError || "") : ""
      })
    }
  }

}
