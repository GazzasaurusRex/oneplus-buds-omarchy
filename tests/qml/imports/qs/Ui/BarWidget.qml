import QtQuick
Item {
  property QtObject bar: null
  property string moduleName: ""
  readonly property bool vertical: bar ? bar.vertical : false
  readonly property int barSize: bar ? bar.barSize : 26
}
