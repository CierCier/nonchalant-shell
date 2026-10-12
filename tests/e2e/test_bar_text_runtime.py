"""Check rendered context labels in both bar layouts without touching the session."""

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
import qs.modules.bar.layouts

ShellRoot {
    FloatingWindow {
        visible: true
        implicitWidth: 1200
        implicitHeight: 900
        Loader { id: bar; anchors.fill: parent }
        Component { id: island; IslandBar { screen: Quickshell.screens[0] } }
        Component { id: pills; PillsBar { screen: Quickshell.screens[0] } }
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

            function test_labels_data() {
                return [{tag: "island", component: island}, {tag: "pills", component: pills}]
            }

            function test_labels(data) {
                Config.bar.pinned = true
                bar.sourceComponent = data.component
                tryVerify(() => bar.item !== null, 2000)
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
        interval: 20000
        running: true
        onTriggered: { console.error("BAR_CONTEXT_TEXT_RUNTIME_TIMEOUT"); Qt.quit() }
    }
}
'''


@unittest.skipUnless(shutil.which("qs"), "Quickshell is required for runtime checks")
class BarTextRuntimeTests(unittest.TestCase):
    def test_context_labels_fit_in_both_layouts(self):
        with tempfile.TemporaryDirectory(prefix="nonchalant-bar-text-") as directory:
            fixture = Path(directory)
            for name in ("modules", "config", "assets", "scripts", "version"):
                (fixture / name).symlink_to(ROOT / name, target_is_directory=(ROOT / name).is_dir())
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
                env=env, capture_output=True, text=True, timeout=25,
            )
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("BAR_CONTEXT_TEXT_RUNTIME_FINISHED", output, output)
            for layout in ("island", "pills"):
                self.assertIn("BAR_CONTEXT_TEXT_PASSED_" + layout, output, output)
            self.assertNotIn("BAR_CONTEXT_TEXT_RUNTIME_TIMEOUT", output, output)
            self.assertNotIn("FAIL!", output, output)
            self.assertNotIn("Binding loop", output, output)


if __name__ == "__main__":
    unittest.main()
