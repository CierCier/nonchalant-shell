import QtQuick

QtObject {
    property string id: ""
    property string name: ""
    property bool focused: false
    property real width: 0
    property real height: 0
    property real refreshRate: 0
    property real scale: 1
    property real x: 0
    property real y: 0
    property string activeWorkspaceId: ""
    property CompositorWorkspace activeWorkspace: null
}
