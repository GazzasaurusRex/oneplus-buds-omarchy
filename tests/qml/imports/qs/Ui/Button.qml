import QtQuick
Item {
 property string text
 property bool selected
 property bool bordered
 property bool leftAlign
 property color foreground
 property color background
 property color accent
 property string fontFamily
 property bool focusable
 implicitHeight: 32
 signal clicked()
}
