pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import ".."
import "../HyprlandCodec.js" as HyprlandCodec

CompositorBackend {
    id: root

    readonly property list<HyprlandMonitor> nativeMonitors: Hyprland.monitors.values
    readonly property list<HyprlandWorkspace> nativeWorkspaces: Hyprland.workspaces.values
    readonly property list<HyprlandToplevel> nativeWindows: Hyprland.toplevels.values
    readonly property bool connected: eventSocket.connected
    readonly property bool nativeInitialized: nativeMonitors.length > 0
    property bool shuttingDown: false

    function rebuildState() {
        if (!eventSocket.connected)
            return;
        try {
            const snapshot = HyprlandCodec.normalize(nativeMonitors, nativeWorkspaces, nativeWindows);
            publish(snapshot);
            root.ready = snapshot.outputs.length > 0;
        } catch (error) {
            clear();
            console.error("HyprlandBackend: invalid compositor state:", error);
        }
    }

    function schedulePublish() {
        Qt.callLater(root.rebuildState);
    }

    function refreshState() {
        // Native startup queries can create records; public refresh methods
        // only update existing records. An early public query can occupy the
        // native request slot and suppress its creation-capable startup query.
        if (!eventSocket.connected || !nativeInitialized)
            return;
        Hyprland.refreshMonitors();
        Hyprland.refreshWorkspaces();
        Hyprland.refreshToplevels();
    }

    function workspaceById(id: string): CompositorWorkspace {
        return state?.workspaces.find(workspace => workspace.id === id) ?? null;
    }

    function request(action: string, targetId: string, command: string) {
        if (!root.ready) {
            root.actionFailed(action, targetId, "Compositor is not ready");
            return;
        }
        Hyprland.dispatch(command);
        refreshTimer.start();
    }

    function focusWorkspace(id: string) {
        try { request("focusWorkspace", id, HyprlandCodec.focusWorkspace(workspaceById(id))); }
        catch (error) { root.actionFailed("focusWorkspace", id, String(error)); }
    }

    function focusWindow(id: string) {
        if (!state?.windows.some(window => window.id === id)) {
            root.actionFailed("focusWindow", id, "Window no longer exists");
            return;
        }
        try { request("focusWindow", id, HyprlandCodec.focusWindow(id)); }
        catch (error) { root.actionFailed("focusWindow", id, String(error)); }
    }

    function closeWindow(id: string) {
        if (!state?.windows.some(window => window.id === id)) {
            root.actionFailed("closeWindow", id, "Window no longer exists");
            return;
        }
        try { request("closeWindow", id, HyprlandCodec.closeWindow(id)); }
        catch (error) { root.actionFailed("closeWindow", id, String(error)); }
    }

    function moveWindowToWorkspace(windowId: string, workspaceId: string, followFocus: bool) {
        if (!state?.windows.some(window => window.id === windowId)) {
            root.actionFailed("moveWindowToWorkspace", windowId, "Window no longer exists");
            return;
        }
        try { request("moveWindowToWorkspace", windowId, HyprlandCodec.moveWindowToWorkspace(windowId, workspaceById(workspaceId), followFocus)); }
        catch (error) { root.actionFailed("moveWindowToWorkspace", windowId, String(error)); }
    }

    function focusMonitor(name: string) {
        if (!state?.outputs.some(output => output.name === name)) {
            root.actionFailed("focusMonitor", name, "Output no longer exists");
            return;
        }
        try { request("focusMonitor", name, HyprlandCodec.focusMonitor(name)); }
        catch (error) { root.actionFailed("focusMonitor", name, String(error)); }
    }

    function focusAdjacentWorkspace(output: string, direction: int) {
        try {
            const workspace = HyprlandCodec.adjacentWorkspace(state?.workspaces ?? [], output, direction);
            if (workspace)
                focusWorkspace(workspace.id);
        } catch (error) { root.actionFailed("focusAdjacentWorkspace", output, String(error)); }
    }

    function logout() {
        request("logout", "", HyprlandCodec.logoutCommand());
    }

    function setMonitorPower(enabled: bool) {
request("setMonitorPower", "", HyprlandCodec.powerCommand(enabled));
    }

    onNativeMonitorsChanged: schedulePublish()
    onNativeWorkspacesChanged: schedulePublish()
    onNativeWindowsChanged: schedulePublish()
    onNativeInitializedChanged: {
        if (nativeInitialized)
            Qt.callLater(root.refreshState);
    }

    Connections {
        target: Hyprland
        function onFocusedMonitorChanged() { root.schedulePublish(); }
        function onFocusedWorkspaceChanged() { root.schedulePublish(); }
        function onActiveToplevelChanged() { root.schedulePublish(); }
    }

    Variants {
        model: root.nativeMonitors
        Item {
            required property HyprlandMonitor modelData
            Connections {
                target: modelData
                function onLastIpcObjectChanged() { root.schedulePublish(); }
                function onActiveWorkspaceChanged() { root.schedulePublish(); }
                function onFocusedChanged() { root.schedulePublish(); }
            }
        }
    }

    Variants {
        model: root.nativeWorkspaces
        Item {
            required property HyprlandWorkspace modelData
            Connections {
                target: modelData
                function onLastIpcObjectChanged() { root.schedulePublish(); }
                function onActiveChanged() { root.schedulePublish(); }
                function onFocusedChanged() { root.schedulePublish(); }
                function onUrgentChanged() { root.schedulePublish(); }
                function onMonitorChanged() { root.schedulePublish(); }
            }
        }
    }

    Variants {
        model: root.nativeWindows
        Item {
            required property HyprlandToplevel modelData
            Connections {
                target: modelData
                function onLastIpcObjectChanged() { root.schedulePublish(); }
                function onActivatedChanged() { root.schedulePublish(); }
                function onTitleChanged() { root.schedulePublish(); }
                function onUrgentChanged() { root.schedulePublish(); }
                function onWorkspaceChanged() { root.schedulePublish(); }
                function onMonitorChanged() { root.schedulePublish(); }
            }
        }
    }

    // Native models do not expose disconnection. This socket also drives native
    // refresh after reconnect, when Quickshell's own event socket remains closed.
    Socket {
        id: eventSocket
        path: Hyprland.eventSocketPath
        parser: SplitParser {
            onRead: data => refreshTimer.start()
        }
        onConnectionStateChanged: {
            if (root.shuttingDown)
                return;
            if (connected) {
                reconnectTimer.stop();
                root.refreshState();
            } else {
                root.clear();
                reconnectTimer.start();
            }
        }
        onError: reconnectTimer.start()
    }

    Timer {
        id: reconnectTimer
        interval: 1000
        repeat: true
        onTriggered: {
            if (!eventSocket.connected && eventSocket.path !== "")
                eventSocket.connected = true;
        }
    }

    Timer {
        id: refreshTimer
        interval: 16
        onTriggered: root.refreshState()
    }

    // Window movement/resizing does not always emit an IPC event. Geometry used
    // for bar hiding must eventually follow it even with no focus change.
    Timer {
        interval: 250
        repeat: true
        running: eventSocket.connected && root.nativeInitialized
        onTriggered: Hyprland.refreshToplevels()
    }

    Component.onCompleted: {
        clear();
        eventSocket.connected = true;
        reconnectTimer.start();
    }

    Component.onDestruction: {
        root.shuttingDown = true;
        reconnectTimer.stop();
        refreshTimer.stop();
        eventSocket.connected = false;
    }
}
