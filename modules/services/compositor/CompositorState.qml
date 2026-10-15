import QtQuick

QtObject {
    property list<CompositorWindow> windows: []
    property list<CompositorWorkspace> workspaces: []
    property list<CompositorOutput> outputs: []
    property list<string> fullscreenOutputs: []
    property bool overviewOpen: false
}
