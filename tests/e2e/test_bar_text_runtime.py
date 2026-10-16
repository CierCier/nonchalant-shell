"""Check bar rendering and transitions without touching the desktop session."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
QML = r'''
import QtQuick
import QtTest
import Quickshell
import Quickshell.Io
import qs.config
import qs.modules.bar.layouts
import qs.modules.services
import qs.modules.theme

ShellRoot {
    FloatingWindow {
        visible: true
        implicitWidth: 1200
        implicitHeight: 900
        Loader { id: bar; anchors.fill: parent }
        Component { id: island; IslandBar { screen: Quickshell.screens[0] } }
        Component { id: pills; PillsBar { screen: Quickshell.screens[0] } }
        Process {
            id: pinCommand
            command: ["qs", "ipc", "-p", Quickshell.shellDir, "call", "nonchalant", "run", "bar-pin"]
        }
        TestCase {
            name: "BarContextText"
            when: Config.initialLoadComplete

            function findLabel(item) {
                if (String(item).startsWith("FluidTextProgress")) return item
                for (const child of item.children ?? []) {
                    const label = findLabel(child)
                    if (label) return label
                }
                return null
            }

            function verifyNoPinIcon(item) {
                if (item.text !== undefined) {
                    verify(item.text !== Icons.pin && item.text !== Icons.unpin,
                        "Bar must not render a pin toggle")
                }
                for (const child of item.children ?? []) verifyNoPinIcon(child)
            }

            function test_pin_command() {
                verify(GlobalShortcuts.ipcHandler !== null)
                Config.bar.pinned = false
                pinCommand.running = true
                tryCompare(Config.bar, "pinned", true)
                tryCompare(pinCommand, "running", false)
                pinCommand.running = true
                tryCompare(Config.bar, "pinned", false)
                tryCompare(pinCommand, "running", false)
                console.log("BAR_PIN_IPC_PASSED")
            }

            function cleanup() {
                bar.sourceComponent = undefined
                Notifications.dismissAllPopups()
                Notifications.silent = false
                NiriService.workspaces.values = []
                NiriService.clients.values = []
            }

            function test_notifications_data() {
                const rows = []
                for (const layout of [{name: "island", component: island}, {name: "pills", component: pills}]) {
                    for (const pinned of [false, true]) {
                        for (const duration of [0, 100]) {
                            rows.push({tag: layout.name + "-" + pinned + "-" + duration,
                                component: layout.component, pinned: pinned, duration: duration})
                        }
                    }
                }
                return rows
            }

            function test_notifications(data) {
                Config.bar.pinned = data.pinned
                Config.theme.animDuration = data.duration
                NiriService.workspaces.values = [{id: 1, active: true, output: Quickshell.screens[0].name}]
                NiriService.clients.values = [{id: 1, workspace: {id: 1}, floating: false}]
                bar.sourceComponent = data.component
                tryVerify(() => bar.item !== null)
                const panel = bar.item
                compare(panel.hasWindowTouchingTop, true)
                panel.expand("calendar")
                tryCompare(panel, "containerY", 0)
                const notification = Notifications.notifyInternal({appName: "Bar regression",
                    summary: "Network disconnected", body: "The network connection has been disconnected",
                    expireTimeout: 60000})
                tryCompare(panel, "hasNotifications", true)
                compare(panel.currentMode, "calendar")
                panel.collapse()
                tryCompare(panel, "currentMode", "notification")
                tryCompare(panel, "containerY", 0, 1500)
                compare(panel.retractingToHidden, false)
                compare(panel.revealProgress, 1)
                Notifications.timeoutNotification(notification.id)
                tryCompare(panel, "currentMode", "collapsed")
                tryCompare(panel, "retractingToHidden", false)
                tryCompare(panel, "revealProgress", data.pinned ? 1 : 0)

                const background = Notifications.notifyInternal({summary: "Expires behind a panel", expireTimeout: 60000})
                tryCompare(panel, "currentMode", "notification")
                panel.expand("calendar")
                tryCompare(panel, "containerY", 0)
                Notifications.clearPopupById(background.id)
                tryCompare(panel, "hasNotifications", false)
                wait(Motion.collapseDuration + 100)
                compare(panel.currentMode, "calendar", "An expired notification must not close another panel")
                compare(panel.containerY, 0)
                panel.collapse()
                tryCompare(panel, "currentMode", "collapsed")

                Notifications.notifyInternal({summary: "Dismiss through DND", expireTimeout: 60000})
                tryCompare(panel, "currentMode", "notification")
                Notifications.setSilent(true)
                tryCompare(panel, "currentMode", "collapsed")
                tryCompare(panel, "retractingToHidden", false)
                tryCompare(panel, "revealProgress", data.pinned ? 1 : 0)
                console.log("BAR_NOTIFICATION_PASSED_" + data.tag)
            }

            function test_interrupted_retraction_data() {
                return [{tag: "island", component: island}, {tag: "pills", component: pills}]
            }

            function test_interrupted_retraction(data) {
                Config.bar.pinned = false
                Config.theme.animDuration = 100
                NiriService.workspaces.values = [{id: 1, active: true, output: Quickshell.screens[0].name}]
                NiriService.clients.values = [{id: 1, workspace: {id: 1}, floating: false}]
                bar.sourceComponent = data.component
                tryVerify(() => bar.item !== null)
                const panel = bar.item
                compare(panel.hasWindowTouchingTop, true)
                for (const interrupt of ["notification", "panel", "osd", "pin", "workspace"]) {
                    panel.expand(interrupt === "osd" ? "osd" : "calendar")
                    tryCompare(panel, "containerY", 0)
                    panel.collapse()
                    wait(80)
                    compare(panel.retractingToHidden, true)
                    verify(panel.containerY < 0)
                    if (interrupt === "notification") {
                        Notifications.notifyInternal({summary: "Arrived while closing", expireTimeout: 60000})
                    } else if (interrupt === "panel") {
                        panel.expand("sound")
                    } else if (interrupt === "osd") {
                        panel.triggerOsd("mic", 0.5, false)
                    } else if (interrupt === "pin") {
                        Config.bar.pinned = true
                    } else {
                        NiriService.clients.values = []
                    }
                    tryCompare(panel, "containerY", 0, 1500)
                    compare(panel.retractingToHidden, false)
                    wait(Motion.collapseDuration + 100)
                    compare(panel.containerY, 0, "A stale close must not hide " + interrupt)
                    Notifications.dismissAllPopups()
                    panel.collapse()
                    Config.bar.pinned = false
                    NiriService.clients.values = [{id: 1, workspace: {id: 1}, floating: false}]
                    tryCompare(panel, "currentMode", "collapsed")
                    tryCompare(panel, "retractingToHidden", false)
                    tryCompare(panel, "revealProgress", 0)
                }
                console.log("BAR_INTERRUPTED_RETRACTION_PASSED_" + data.tag)
            }

            function test_labels_data() {
                return [{tag: "island", component: island}, {tag: "pills", component: pills}]
            }

            function test_labels(data) {
                Config.bar.pinned = true
                bar.sourceComponent = data.component
                tryVerify(() => bar.item !== null, 2000)
                verifyNoPinIcon(bar.item)
                const label = findLabel(bar.item)
                verify(label !== null)
                const rendered = label.children.find(child => child.truncated !== undefined)
                verify(rendered !== undefined)
                for (const font of ["JetBrains Mono", "Noto Sans"]) {
                    label.fontFamily = font
                    for (const size of [11, 13, 14, 17]) {
                        label.pixelSize = size
                        for (const text of ["Desktop", "Terminal", "Firefox", "Settings", "Café", "डेस्कटॉप"]) {
                            label.text = text
                            tryCompare(rendered, "text", text)
                            tryVerify(() => label.width >= rendered.implicitWidth, 1000,
                                data.tag + ": " + font + " " + size + " " + text
                                + " allocated=" + label.width + " needed=" + rendered.implicitWidth)
                            compare(rendered.truncated, false, "Short labels must be fully visible")
                        }
                    }
                }
                label.pixelSize = 13
                label.fontFamily = "JetBrains Mono"
                label.text = "A long window or media title that should still elide inside the bar"
                tryCompare(rendered, "truncated", true)
                verify(label.implicitWidth > label.width, "The layout must still cap long titles")
                label.text = "Desktop"
                tryCompare(rendered, "truncated", false)
                for (const playing of [true, false]) {
                    label.isPlaying = playing
                    for (const progress of [0, 0.5, 1]) {
                        label.progress = progress
                        tryVerify(() => !rendered.truncated && label.width >= rendered.implicitWidth)
                        tryVerify(() => rendered.height >= rendered.implicitHeight, 1000,
                            "Playback decoration must leave enough height for the label")
                    }
                }
                console.log("BAR_CONTEXT_TEXT_PASSED_" + data.tag)
                bar.sourceComponent = undefined
            }

            function cleanupTestCase() {
                console.log("BAR_CONTEXT_TEXT_RUNTIME_FINISHED")
                Qt.quit()
            }
        }
    }
    Timer {
        interval: 60000
        running: true
        onTriggered: { console.error("BAR_CONTEXT_TEXT_RUNTIME_TIMEOUT"); Qt.quit() }
    }
}
'''


@unittest.skipUnless(shutil.which("qs"), "Quickshell is required for runtime checks")
class BarTextRuntimeTests(unittest.TestCase):
    def test_bar_labels_and_pin_command(self):
        with tempfile.TemporaryDirectory(prefix="nonchalant-bar-text-") as directory:
            fixture = Path(directory)
            for name in ("config", "assets", "scripts", "version"):
                (fixture / name).symlink_to(ROOT / name, target_is_directory=(ROOT / name).is_dir())
            # Isolate the command runner's FIFO from the live desktop session.
            modules = fixture / "modules"
            modules.mkdir()
            for source in (ROOT / "modules").iterdir():
                if source.name != "services":
                    (modules / source.name).symlink_to(source, target_is_directory=source.is_dir())
            services = modules / "services"
            services.mkdir()
            for source in (ROOT / "modules/services").iterdir():
                target = services / source.name
                if source.name == "GlobalShortcuts.qml":
                    target.write_text(source.read_text().replace(
                        '"/tmp/nonchalant_ipc.pipe"', '"' + str(fixture / "ipc.pipe") + '"'))
                else:
                    target.symlink_to(source, target_is_directory=source.is_dir())
            (fixture / "shell.qml").write_text(QML)
            home = fixture / "home"
            home.mkdir()
            # Keep locally installed fonts available inside the isolated home.
            fonts = Path.home() / ".local/share/fonts"
            if fonts.is_dir():
                (home / ".local/share").mkdir(parents=True)
                (home / ".local/share/fonts").symlink_to(fonts, target_is_directory=True)
            runtime = fixture / "runtime"
            runtime.mkdir(mode=0o700)
            env = {
                **os.environ,
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(home / ".config"),
                "XDG_STATE_HOME": str(home / ".local/state"),
                "XDG_DATA_HOME": str(home / ".local/share"),
                "XDG_CACHE_HOME": str(home / ".cache"),
                "XDG_RUNTIME_DIR": str(runtime),
                "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(runtime / "no-session-bus"),
                "QT_QPA_PLATFORM": "offscreen",
                "QT_QUICK_BACKEND": "software",
                "NIRI_SOCKET": str(fixture / "no-compositor.sock"),
            }
            env.pop("WAYLAND_DISPLAY", None)
            result = subprocess.run(
                ["qs", "-p", str(fixture), "--no-duplicate", "--no-color"],
                env=env, capture_output=True, text=True, timeout=65,
            )
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("BAR_CONTEXT_TEXT_RUNTIME_FINISHED", output, output)
            self.assertIn("BAR_PIN_IPC_PASSED", output, output)
            for layout in ("island", "pills"):
                self.assertIn("BAR_CONTEXT_TEXT_PASSED_" + layout, output, output)
                self.assertIn("BAR_INTERRUPTED_RETRACTION_PASSED_" + layout, output, output)
                for pinned in ("false", "true"):
                    for duration in (0, 100):
                        marker = f"BAR_NOTIFICATION_PASSED_{layout}-{pinned}-{duration}"
                        self.assertIn(marker, output, output)
            self.assertNotIn("BAR_CONTEXT_TEXT_RUNTIME_TIMEOUT", output, output)
            self.assertNotIn("FAIL!", output, output)
            self.assertNotIn("Binding loop", output, output)


if __name__ == "__main__":
    unittest.main()
