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
        ThemePanel { id: compactTheme; width: 1000; visible: false }
        LyricsView { id: lyrics; width: 200; height: 22 }
        CustomColorPicker { id: picker; parent: settings }
        TestCase {
            name: "SettingsLyricsRuntime"
            when: Config.initialLoadComplete

            function initTestCase() {
                // Construct pages synchronously in QtTest's nested event loop.
                findChild(settings, "settingsPanelLoader").asynchronous = false
            }

            function expectPage(pageId) {
                const loader = findChild(settings, "settingsPanelLoader")
                compare(settings.currentPageId, pageId)
                compare(String(loader.source), settings.pageFor(pageId).component)
                tryCompare(loader, "status", Loader.Ready, 5000)
                tryCompare(settings, "loadedPageId", pageId, 5000)
            }

            function test_search_navigation_follows_display_order() {
                for (const query of ["a", "s", "color", "system", "lyrics"]) {
                    settings.searchQuery = query
                    const rows = settings.sidebarRows.filter(row => !row.heading)
                    compare(rows.length, settings.searchResults.length)
                    for (let index = 0; index < rows.length; index++) {
                        compare(rows[index].resultIndex, index, query + ": keyboard order must match rows")
                        compare(settings.searchResults[index].pageId, rows[index].pageId)
                        compare(settings.searchCursor, index)
                        settings.moveSearchCursor(1)
                    }
                    compare(settings.searchCursor, 0, "Down wraps after the last visible result")
                }
                settings.searchQuery = ""
                console.log("SETTINGS_SEARCH_ORDER_PASSED")
            }

            function test_color_picker_hues_match_selection() {
                function hueSlider(item) {
                    if (item.to === 360 && item.from === 0) return item
                    for (const child of item.children ?? []) {
                        const found = hueSlider(child)
                        if (found) return found
                    }
                    return null
                }
                picker.open()
                picker.saturation = 1
                picker.value = 1
                picker.alpha = 1
                const slider = hueSlider(picker.contentItem)
                verify(slider !== null)
                const stops = slider.background.children[0].gradient.stops
                compare(stops.length, 7)
                for (const stop of stops) {
                    const expected = Qt.hsva(stop.position, 1, 1, 1)
                    verify(Math.abs(stop.color.r - expected.r) < 0.002)
                    verify(Math.abs(stop.color.g - expected.g) < 0.002)
                    verify(Math.abs(stop.color.b - expected.b) < 0.002)
                    picker.hue = stop.position * 360
                    compare(picker.selectedColor, expected)
                }
                picker.close()
                console.log("SETTINGS_COLOR_HUES_PASSED")
            }
            function test_independent_settings_and_lyrics() {
                verify(Config.desktop === undefined)
                settings.go("shell", "bar")
                expectPage("shell")
                compare(settings.currentTabId, "bar")
                settings.go("audio", "")
                expectPage("audio")
                settings.back()
                expectPage("shell")
                compare(settings.currentPageId, "shell")
                compare(settings.currentTabId, "bar")
                settings.forward()
                expectPage("audio")
                compare(settings.currentPageId, "audio")
                GlobalStates.openSettings("theme", "colors")
                expectPage("theme")
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
            }

            function test_settings_use_available_width() {
                const loader = findChild(settings, "settingsPanelLoader")
                verify(loader !== null)
                const pages = ["network", "bluetooth", "audio", "ai", "shell", "theme", "system"]
                for (const pageId of pages) {
                    const page = settings.pageFor(pageId)
                    verify(!page.tabs.some(tab => tab.id === "overview"))
                    if (page.tabs.length > 0) {
                        compare(settings.defaultTab(pageId), page.tabs[0].id)
                    }
                    const tabs = page.tabs.length > 0 ? page.tabs.map(tab => tab.id) : [""]
                    for (const tabId of tabs) {
                        settings.go(pageId, tabId)
                        expectPage(pageId)
                        for (const availableWidth of [1600, 900, 680]) {
                            settings.width = availableWidth
                            tryVerify(() => loader.width > 0 && loader.item.contentWidth === loader.width, 1000)
                            compare(loader.item.sideMargin, 0)
                        }
                    }
                }
                settings.go("theme", "colors")
                expectPage("theme")
                loader.item.openColorPicker(["background", "primary"], "background", "Select Color", () => {})
                compare(loader.item.colorPickerActive, true)
                settings.width = 1600
                tryCompare(loader.item, "contentWidth", loader.width, 1000)
                compare(loader.item.sideMargin, 0)
                loader.item.closeColorPicker()
                compare(loader.item.colorPickerActive, false)
                compare(settings.currentTabId, "colors")
                settings.go("theme", "")
                compare(settings.currentTabId, "colors")
                compare(compactTheme.contentWidth, 480)
                console.log("SETTINGS_LAYOUT_RUNTIME_PASSED")
            }

            function cleanupTestCase() { Qt.quit() }
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
            self.assertIn("SETTINGS_LAYOUT_RUNTIME_PASSED", output, output)
            self.assertIn("SETTINGS_SEARCH_ORDER_PASSED", output, output)
            self.assertIn("SETTINGS_COLOR_HUES_PASSED", output, output)
            self.assertNotIn("SETTINGS_LYRICS_RUNTIME_TIMEOUT", output, output)
            self.assertNotIn("FAIL!", output, output)


if __name__ == "__main__":
    unittest.main()
