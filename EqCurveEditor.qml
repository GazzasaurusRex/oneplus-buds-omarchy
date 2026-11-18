import QtQuick
import QtQuick.Shapes
import qs.Commons
import qs.Commons as Commons
import "EqCurve.js" as Curve

Item {
  id: editor
  property var entry: null
  property string contextKey: ""
  property real step: 1
  property color accentColor: Commons.Color.accent
  property color foreground: Commons.Color.foreground
  property color background: Commons.Color.background
  property string fontFamily: ""
  readonly property real minimum: entry ? entry.min_gain_db : -6
  readonly property real maximum: entry ? entry.max_gain_db : 6
  readonly property var bands: entry && entry.bands ? entry.bands : []
  property var gains: []
  property bool dirty: false
  property int activeIndex: -1
  property string loadedKey: ""
  property string gestureKey: ""
  property var gestureGains: []
  readonly property real leftInset: Style.space(42)
  readonly property real rightInset: Style.space(16)
  readonly property real topInset: Style.space(34)
  readonly property real bottomInset: Style.space(30)
  readonly property var curvePoints: Curve.points(gains, plot.width, plot.height, minimum, maximum)
  readonly property string curvePath: Curve.linePath(curvePoints)
  implicitHeight: Style.space(250)
  signal editingStarted()
  signal released(int entryId, var values, string deviceKey)

  function key() {
    return entry ? contextKey + ":" + entry.eq_id + ":" + minimum + ":" + maximum
      + ":" + bands.map(function(b) { return b.frequency_hz }).join(",") : ""
  }
  function syncEntry(force) {
    var nextKey = key()
    if (nextKey !== loadedKey) {
      cancelEdit()
      loadedKey = nextKey
      dirty = false
      force = true
    }
    if (force || (activeIndex < 0 && !dirty))
      gains = bands.map(function(b) { return b.gain_db })
  }
  function settle() {
    cancelEdit()
    dirty = false
    syncEntry(true)
  }
  function beginEdit(index) {
    if (!enabled || !visible || index < 0 || index >= gains.length) return
    if (activeIndex >= 0) return
    gestureKey = key()
    gestureGains = gains.slice()
    activeIndex = index
    editingStarted()
  }
  function setActiveGain(value) {
    if (activeIndex < 0 || gestureKey !== key()) return
    var next = gains.slice()
    next[activeIndex] = Curve.clampGain(value, minimum, maximum, step)
    gains = next
  }
  function moveEdit(y) {
    setActiveGain(maximum - y * (maximum - minimum) / Math.max(1, plot.height))
  }
  function finishEdit() {
    if (activeIndex < 0) return
    if (!enabled || !visible || gestureKey !== key()) { cancelEdit(); return }
    var changed = JSON.stringify(gains) !== JSON.stringify(gestureGains)
    activeIndex = -1
    dirty = changed
    if (changed) released(entry.eq_id, gains.slice(), contextKey)
    else syncEntry(false)
  }
  function cancelEdit() {
    if (activeIndex < 0) return
    activeIndex = -1
    gains = gestureGains.slice()
  }
  onEntryChanged: syncEntry(false)
  onBandsChanged: syncEntry(false)
  onContextKeyChanged: syncEntry(false)
  onEnabledChanged: if (!enabled) cancelEdit()
  onVisibleChanged: if (!visible) cancelEdit()
  Component.onCompleted: syncEntry(true)

  Item {
    id: plot
    x: editor.leftInset; y: editor.topInset
    width: Math.max(1, editor.width - editor.leftInset - editor.rightInset)
    height: Math.max(1, editor.height - editor.topInset - editor.bottomInset)

    Repeater {
      model: [editor.maximum, 0, editor.minimum]
      delegate: Item {
        required property real modelData
        y: (editor.maximum - modelData) * plot.height / Math.max(1, editor.maximum - editor.minimum)
        width: plot.width
        Rectangle {
          width: parent.width; height: 1
          color: editor.foreground
          opacity: modelData === 0 ? 0.24 : 0.08
        }
        Text {
          x: -editor.leftInset; width: editor.leftInset - Style.space(7)
          anchors.verticalCenter: parent.top
          text: (modelData > 0 ? "+" : "") + modelData + " dB"
          color: editor.foreground; opacity: 0.6
          font.family: editor.fontFamily; font.pixelSize: Style.font.bodySmall - 1
          horizontalAlignment: Text.AlignRight
        }
      }
    }

    Shape {
      anchors.fill: parent
      antialiasing: true
      ShapePath {
        strokeWidth: -1
        fillGradient: LinearGradient {
          x1: 0; y1: 0; x2: 0; y2: plot.height
          GradientStop { position: 0; color: Qt.rgba(editor.accentColor.r, editor.accentColor.g, editor.accentColor.b, 0.48) }
          GradientStop { position: 1; color: Qt.rgba(editor.accentColor.r, editor.accentColor.g, editor.accentColor.b, 0) }
        }
        PathSvg {
          path: editor.curvePath === "" ? "" : editor.curvePath
            + " L " + editor.curvePoints[editor.curvePoints.length - 1].x + " " + plot.height
            + " L " + editor.curvePoints[0].x + " " + plot.height + " Z"
        }
      }
      ShapePath {
        objectName: "eqCurveStroke"
        strokeColor: editor.accentColor
        strokeWidth: Style.space(2)
        capStyle: ShapePath.RoundCap
        joinStyle: ShapePath.RoundJoin
        fillColor: "transparent"
        PathSvg { path: editor.curvePath }
      }
    }

    Repeater {
      model: editor.bands
      delegate: Item {
        id: band
        required property var modelData
        required property int index
        x: editor.curvePoints.length > index ? editor.curvePoints[index].x : 0
        height: plot.height
        readonly property real pointY: editor.curvePoints.length > index ? editor.curvePoints[index].y : 0

        Rectangle {
          width: 1; height: plot.height
          color: editor.foreground; opacity: 0.1
        }
        Text {
          y: -editor.topInset + Style.space(4)
          anchors.horizontalCenter: parent.left
          text: (editor.gains[index] > 0 ? "+" : "") + editor.gains[index]
          color: editor.accentColor
          font.family: editor.fontFamily; font.pixelSize: Style.font.bodySmall
        }
        Text {
          y: plot.height + Style.space(8)
          anchors.horizontalCenter: parent.left
          text: modelData.frequency_hz >= 1000 ? modelData.frequency_hz / 1000 + "k" : modelData.frequency_hz
          color: editor.foreground; opacity: 0.72
          font.family: editor.fontFamily; font.pixelSize: Style.font.bodySmall
        }
        Rectangle {
          objectName: "eqPoint_" + modelData.frequency_hz
          anchors.horizontalCenter: parent.left
          y: band.pointY - height / 2
          width: Style.space(11); height: width; radius: width / 2
          color: editor.foreground
          border.color: editor.accentColor; border.width: Style.space(2)
        }
        MouseArea {
          id: handle
          objectName: "eqHandle_" + modelData.frequency_hz
          anchors.horizontalCenter: parent.left
          y: band.pointY - height / 2
          width: Style.space(30); height: width
          hoverEnabled: true
          preventStealing: true
          cursorShape: Qt.SizeVerCursor
          activeFocusOnTab: true
          onPressed: { forceActiveFocus(); editor.beginEdit(band.index) }
          onPositionChanged: function(mouse) {
            if (pressed) editor.moveEdit(mapToItem(plot, mouse.x, mouse.y).y)
          }
          onReleased: function(mouse) {
            editor.moveEdit(mapToItem(plot, mouse.x, mouse.y).y)
            editor.finishEdit()
          }
          onCanceled: editor.cancelEdit()
          onEnabledChanged: if (!enabled) focus = false
          onVisibleChanged: if (!visible) focus = false
          onActiveFocusChanged: if (!activeFocus && editor.activeIndex === band.index) editor.cancelEdit()
          Keys.onPressed: function(event) {
            if (event.key !== Qt.Key_Up && event.key !== Qt.Key_Down) return
            editor.beginEdit(band.index)
            editor.setActiveGain(editor.gains[band.index] + (event.key === Qt.Key_Up ? editor.step : -editor.step))
            event.accepted = true
          }
          Keys.onReleased: function(event) {
            if (event.key !== Qt.Key_Up && event.key !== Qt.Key_Down) return
            if (!event.isAutoRepeat) editor.finishEdit()
            event.accepted = true
          }
          Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: "transparent"
            border.color: editor.accentColor
            visible: handle.activeFocus || handle.containsMouse
            opacity: 0.45
          }
        }
      }
    }
  }
}
