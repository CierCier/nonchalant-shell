import QtQuick
import Quickshell
import Quickshell.Io
import qs.modules.services

ShellRoot {
    id: root
    property list<string> actionFailures: []
    Connections {
        target: CompositorService
        function onActionFailed(action: string, targetId: string, message: string) {
            root.actionFailures = root.actionFailures.concat([action + " " + targetId + ": " + message]);
        }
    }
    IpcHandler {
        target: "compositor-test"

        function diagnostic(): string {
            const backend = CompositorService.backend;
            return JSON.stringify({
                connected: backend?.connected ?? null,
                monitors: backend?.nativeMonitors?.map(monitor => ({
                    name: monitor.name, width: monitor.width,
                    height: monitor.height, scale: monitor.scale,
                    focused: monitor.focused,
                    raw: monitor.lastIpcObject
                })) ?? [],
                workspaces: backend?.nativeWorkspaces?.map(workspace => workspace.lastIpcObject) ?? [],
                windows: backend?.nativeWindows?.map(window => window.lastIpcObject) ?? []
            });
        }

        function state(): string {
            const service = CompositorService;
            return JSON.stringify({
                ready: service.ready,
                actionFailures: root.actionFailures,
                compositor: service.compositor,
                focusedMonitor: service.focusedMonitor?.name ?? "",
                focusedWindow: service.focusedClient?.id ?? "",
                focusedWorkspace: service.focusedWorkspace?.id ?? "",
                fullscreenOutputs: service.fullscreenOutputs,
                windows: service.windows.map(window => ({
                    id: window.id, title: window.title,
                    workspaceId: window.workspaceId, output: window.output,
                    fullscreen: window.fullscreen,
                    geometryKnown: window.geometryKnown,
                    geometry: [window.geometry.x, window.geometry.y,
                        window.geometry.width, window.geometry.height]
                })),
                workspaces: service.workspaces.map(workspace => ({
                    id: workspace.id, name: workspace.name,
                    output: workspace.output, active: workspace.active,
                    special: workspace.special
                })),
                monitors: service.monitors.map(monitor => ({
                    name: monitor.name, width: monitor.width,
                    height: monitor.height, scale: monitor.scale
                }))
            });
        }

        function focusWindow(id: string): void {
            CompositorService.focusWindow(id);
        }

        function focusWorkspace(id: string): void {
            CompositorService.focusWorkspace(id);
        }

        function moveWindow(id: string, workspaceId: string): void {
            CompositorService.moveWindowToWorkspace(id, workspaceId, false);
        }

        function closeWindow(id: string): void {
            CompositorService.closeWindow(id);
        }

        function adjacent(output: string, direction: int): void {
            CompositorService.focusAdjacentWorkspace(output, direction);
        }
    }
}
