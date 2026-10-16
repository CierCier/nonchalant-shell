import QtQuick

QtObject {
    property string id: ""
    property int pid: 0
    property string appId: ""
    property string title: ""
    property string workspaceId: ""
    property string output: ""
    property bool floating: false
    property bool fullscreen: false
    property bool is_focused: false
    property bool urgent: false
    property bool tiledAtTop: false
    property bool geometryKnown: false
    property rect geometry: Qt.rect(0, 0, 0, 0)
}
