import QtQuick
Item {
 property bool checked: false
 property bool busy: false
 property bool interactive: true
 implicitHeight: 24
 signal toggled()
}
