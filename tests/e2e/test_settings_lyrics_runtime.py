"""Verify the independent settings and lyrics runtime with isolated user state."""

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
import qs.modules.globals
import qs.modules.services
import qs.modules.components
import qs.modules.widgets.dashboard.controls

ShellRoot {
    FloatingWindow {
        visible: true
        implicitWidth: 1000
        implicitHeight: 800
        SettingsTab { id: settings; anchors.fill: parent }
        LyricsView { id: lyrics; width: 200; height: 22 }
        TestCase {
            name: "SettingsLyricsRuntime"
            when: Config.initialLoadComplete
            function test_independent_settings_and_lyrics() {
                verify(Config.desktop === undefined)
                settings.go("shell", "bar")
                tryCompare(settings, "loadedPageId", "shell", 5000)
                compare(settings.currentTabId, "bar")
                settings.go("audio", "")
                tryCompare(settings, "loadedPageId", "audio", 5000)
                settings.back()
                compare(settings.currentPageId, "shell")
                compare(settings.currentTabId, "bar")
                settings.forward()
                compare(settings.currentPageId, "audio")
                GlobalStates.openSettings("theme", "colors")
                tryCompare(settings, "loadedPageId", "theme", 5000)
                compare(settings.currentTabId, "colors")
                settings.searchQuery = "lyrics"
                verify(settings.searchResults.some(result => result.tabId === "bar"))
                verify(settings.searchResults.some(result => result.tabId === "lockscreen"))
                verify(!settings.sidebarRows.some(row => row.pageId === "desktop"))
                compare(LyricsService.watchers, 0)
                lyrics.active = true
                tryCompare(LyricsService, "watchers", 1, 1000)
                Config.bar.lyricsEnabled = false
                tryCompare(LyricsService, "watchers", 0, 1000)
                Config.bar.lyricsEnabled = true
                tryCompare(LyricsService, "watchers", 1, 1000)
                lyrics.visible = false
                tryCompare(LyricsService, "watchers", 0, 1000)
                verify(!LyricsService.queryActive)
                console.log("SETTINGS_LYRICS_RUNTIME_PASSED")
                Qt.quit()
            }
        }
    }
    Timer {
        interval: 15000
        running: true
        onTriggered: { console.error("SETTINGS_LYRICS_RUNTIME_TIMEOUT"); Qt.quit() }
    }
}
'''


@unittest.skipUnless(shutil.which("qs"), "Quickshell is required for runtime checks")
class SettingsLyricsRuntimeTests(unittest.TestCase):
    def test_settings_navigation_and_lyrics_demand(self):
        with tempfile.TemporaryDirectory(prefix="nonchalant-settings-lyrics-") as directory:
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
                "NIRI_SOCKET": str(fixture / "no-compositor.sock"),
            }
            env.pop("WAYLAND_DISPLAY", None)
            result = subprocess.run(
                ["qs", "-p", str(fixture), "--no-duplicate", "--no-color"],
                env=env, capture_output=True, text=True, timeout=25,
            )
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("SETTINGS_LYRICS_RUNTIME_PASSED", output, output)
            self.assertNotIn("SETTINGS_LYRICS_RUNTIME_TIMEOUT", output, output)
            self.assertNotIn("FAIL!", output, output)


if __name__ == "__main__":
    unittest.main()
