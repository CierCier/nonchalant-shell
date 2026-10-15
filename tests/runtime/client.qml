import QtQuick
import QtQuick.Window
import Quickshell
import Quickshell.Io

ShellRoot {
    Window {
        id: first
        visible: true
        title: "Nonchalant Test A"
        width: 640
        height: 480
        color: "#243447"
        Text { anchors.centerIn: parent; text: first.title; color: "white" }
    }
    Window {
        id: second
        visible: true
        title: "Nonchalant Test B"
        width: 480
        height: 320
        color: "#472e24"
        Text { anchors.centerIn: parent; text: second.title; color: "white" }
    }
    IpcHandler {
        target: "test-client"
        function fullscreen(enabled: bool): void {
            first.visibility = enabled ? Window.FullScreen : Window.Windowed;
        }
    }
}
