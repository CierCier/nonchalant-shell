import QtQuick

Item {
    id: root

    property CompositorState state: null
    property string lastSnapshot: ""
    property bool ready: false
    property bool supportsOverview: false

    signal actionFailed(string action, string targetId, string message)

    function publish(snapshot) {
        const serialized = JSON.stringify(snapshot);
        if (serialized === lastSnapshot)
            return;
        lastSnapshot = serialized;
        const next = stateComponent.createObject(root);
        next.workspaces = snapshot.workspaces.map(data => workspaceComponent.createObject(next, data));
        next.windows = snapshot.windows.map(data => {
            const properties = Object.assign({}, data);
            const geometry = properties.geometry;
            properties.geometry = Qt.rect(geometry[0], geometry[1], geometry[2], geometry[3]);
            return windowComponent.createObject(next, properties);
        });
        next.outputs = snapshot.outputs.map(data => {
            const properties = Object.assign({}, data);
            properties.activeWorkspace = next.workspaces.find(workspace => workspace.id === data.activeWorkspaceId) ?? null;
            return outputComponent.createObject(next, properties);
        });
        next.fullscreenOutputs = snapshot.fullscreenOutputs ?? [];
        next.overviewOpen = snapshot.overviewOpen ?? false;
        const previous = root.state;
        root.state = next;
        if (previous)
            Qt.callLater(() => previous.destroy());
    }

    function clear() {
        root.ready = false;
        publish({ windows: [], workspaces: [], outputs: [] });
    }

    Component { id: stateComponent; CompositorState {} }
    Component { id: windowComponent; CompositorWindow {} }
    Component { id: workspaceComponent; CompositorWorkspace {} }
    Component { id: outputComponent; CompositorOutput {} }
}
