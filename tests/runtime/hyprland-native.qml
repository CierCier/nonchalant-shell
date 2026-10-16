import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland

ShellRoot {
    IpcHandler {
        target: "hyprland-native"
        function state(): string {
            return JSON.stringify({
                requestSocket: Hyprland.requestSocketPath,
                eventSocket: Hyprland.eventSocketPath,
                usingLua: Hyprland.usingLua,
                monitors: Hyprland.monitors.values.map(monitor => monitor.lastIpcObject),
                workspaces: Hyprland.workspaces.values.map(workspace => workspace.lastIpcObject),
                toplevels: Hyprland.toplevels.values.map(toplevel => toplevel.lastIpcObject)
            });
        }
    }
}
