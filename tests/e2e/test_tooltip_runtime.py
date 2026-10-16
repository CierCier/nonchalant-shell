"""Exercise hover and owner lifecycle changes in the shared tooltip."""

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
import qs.config
import qs.modules.components

ShellRoot {
    FloatingWindow {
        id: window
        visible: true
        implicitWidth: 600
        implicitHeight: 400
        Item {
            id: page
            anchors.fill: parent
            Item {
                id: owner
                x: 50; y: 50; width: 100; height: 40
                StyledToolTip {
                    id: tip
                    delay: 10
                    show: false
                    tooltipText: "Pin Island"
                }
            }
        }
        StyledSlider {
            id: slider
            x: 50; y: 200; width: 120; height: 20
            resizeParent: false
            value: 0.5
        }
        TestCase {
            name: "TooltipLifecycle"
            when: Config.initialLoadComplete

            function hover() {
                mouseMove(owner, 20, 20)
                tip.show = true
                tryCompare(tip, "visible", true, 2000)
            }

            function test_latched_hover_and_owner_lifecycle() {
                hover()
                // A stale caller flag must not keep the popup visible after pointer exit.
                mouseMove(window.contentItem, 500, 300)
                tryCompare(tip, "visible", false, 1000)
                hover()
                page.enabled = false
                tryCompare(tip, "visible", false, 1000)
                page.enabled = true
                mouseMove(owner, 20, 20)
                tryCompare(tip, "visible", true, 2000)
                page.visible = false
                tryCompare(tip, "visible", false, 1000)
                mouseMove(window.contentItem, 500, 300)
                page.visible = true
                wait(100)
                compare(tip.visible, false, "Reopening away from the pointer must not revive the tooltip")
                hover()
                page.opacity = 0
                tryCompare(tip, "visible", false, 1000)
                page.opacity = 1
                mouseMove(owner, 20, 20)
                tryCompare(tip, "visible", true, 2000)
                owner.x = 250
                mouseMove(window.contentItem, 70, 70)
                tryCompare(tip, "visible", false, 1000)
                owner.x = 50
                hover()
                tip.show = false
                tryCompare(tip, "visible", false, 1000)
                hover()
                tip.tooltipText = ""
                tryCompare(tip, "visible", false, 1000)
                console.log("TOOLTIP_LIFECYCLE_PASSED")
            }

            function tooltips(item) {
                let found = []
                for (const child of item.children ?? []) {
                    for (const object of child.data ?? []) {
                        if (String(object).startsWith("StyledToolTip")) found.push(object)
                    }
                    found = found.concat(tooltips(child))
                }
                return found
            }

            function test_slider_drag_data() {
                return [{tag: "horizontal", vertical: false}, {tag: "vertical", vertical: true}]
            }

            function test_slider_drag(data) {
                slider.vertical = data.vertical
                slider.width = data.vertical ? 20 : 120
                slider.height = data.vertical ? 120 : 20
                const tips = tooltips(slider)
                compare(tips.length, 2)
                for (const tooltip of tips) tooltip.delay = 10
                const tooltip = tips[data.vertical ? 1 : 0]
                mousePress(slider, slider.width / 2, slider.height / 2)
                tryCompare(slider, "isDragging", true)
                tryCompare(tooltip, "visible", true, 2000)
                mouseMove(window.contentItem, 500, 350)
                compare(tooltip.visible, true, "Drag tips must follow the grab outside the slider")
                mouseRelease(window.contentItem, 500, 350)
                tryCompare(slider, "isDragging", false)
                tryCompare(tooltip, "visible", false)
                console.log("TOOLTIP_SLIDER_PASSED_" + data.tag)
            }

            function cleanupTestCase() {
                Qt.quit()
            }
        }
        Timer {
            interval: 15000
            running: true
            onTriggered: { console.error("TOOLTIP_RUNTIME_TIMEOUT"); Qt.quit() }
        }
    }
}
'''


@unittest.skipUnless(shutil.which("qs"), "Quickshell is required for runtime checks")
class TooltipRuntimeTests(unittest.TestCase):
    def test_hover_exit_and_hidden_owners_close_tooltips(self):
        with tempfile.TemporaryDirectory(prefix="nonchalant-tooltip-") as directory:
            fixture = Path(directory)
            for name in ("modules", "config", "assets", "scripts", "version"):
                (fixture / name).symlink_to(ROOT / name, target_is_directory=(ROOT / name).is_dir())
            (fixture / "shell.qml").write_text(QML)
            home = fixture / "home"
            home.mkdir()
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
            }
            env.pop("WAYLAND_DISPLAY", None)
            result = subprocess.run(
                ["qs", "-p", str(fixture), "--no-duplicate", "--no-color"],
                env=env, capture_output=True, text=True, timeout=20,
            )
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("TOOLTIP_LIFECYCLE_PASSED", output, output)
            for direction in ("horizontal", "vertical"):
                self.assertIn("TOOLTIP_SLIDER_PASSED_" + direction, output, output)
            self.assertNotIn("TOOLTIP_RUNTIME_TIMEOUT", output, output)
            self.assertNotIn("Binding loop", output, output)


if __name__ == "__main__":
    unittest.main()
