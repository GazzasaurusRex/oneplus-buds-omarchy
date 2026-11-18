import QtQuick
Item {
 property var bar
 property real value: 0
 property real minimum: 0
 property real maximum: 1
 property real step: 1
 property bool integer: false
 implicitHeight: 24
 signal moved(real value)
 signal released(real value)
}
