"""Run the production lyrics helper and QML views against private MPRIS players."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tests.e2e import test_mpris_runtime as mpris_runtime


ROOT = Path(__file__).resolve().parents[2]
QML = r'''
import QtQuick
import QtTest
import Quickshell
import Quickshell.Io
import qs.config
import qs.modules.components
import qs.modules.services
import qs.modules.globals
import qs.modules.widgets.dashboard.widgets

ShellRoot {
    FloatingWindow {
        visible: true
        implicitWidth: 800
        implicitHeight: 500
        LyricsView { id: compact; width: 350; height: 22 }
        LyricsView { id: detail; width: 350; height: 140; y: 40; mode: "detail" }
        LockPlayer { id: lock; width: 350; y: 220 }
        Process { id: control }
        TestCase {
            name: "CiderLyricsRuntime"
            when: Config.initialLoadComplete && MprisController.filteredPlayers.length === 2

            function update(method, argument) {
                control.command = ["gdbus", "call", "--session", "--dest",
                    "org.mpris.MediaPlayer2.cider", "--object-path", "/org/mpris/MediaPlayer2",
                    "--method", "org.nonchalant.Test." + method, String(argument)]
                control.running = true
                tryCompare(control, "running", false, 2000)
                wait(30)
            }

            function controlOfType(item, type) {
                if (String(item).startsWith(type))
                    return item
                for (const child of item.children ?? []) {
                    const found = controlOfType(child, type)
                    if (found)
                        return found
                }
                return null
            }

            function test_cider_words_follow_playback_and_provider_switches() {
                MprisController.trackedPlayer = MprisController.filteredPlayers.find(
                    player => player.dbusName === "org.mpris.MediaPlayer2.cider")
                compare(LyricsService.ciderPlayer, true)
                compare(LyricsService.ciderTrackId, "1")
                update("MovePosition", 0)
                compact.active = true
                detail.active = true
                tryCompare(LyricsService, "status", "timed", 5000)
                compare(LyricsService.source, "cider")
                compare(LyricsService.lead, 0)
                compare(LyricsService.lines[0].words.length, 2)
                compare(LyricsService.current, 0)
                const text = compact.children.find(child => child.text !== undefined && child.visible)
                verify(text !== undefined)
                tryVerify(() => text.text.includes("<u>One</u>"))
                update("MovePosition", 1)
                tryVerify(() => text.text.includes("<u>&lt;two&gt;</u>"))
                verify(!text.text.includes("<u>One</u>"))
                const pausedText = text.text
                wait(180)
                compare(text.text, pausedText, "Paused playback must not advance words")
                compact.width = 40
                tryVerify(() => text.width > compact.width && text.x < 0, 1000)
                verify(!text.truncated, "Long word-timed lines must follow the current word")
                compact.width = 350
                verify(LyricsService.seekTo(0))
                tryVerify(() => text.text.includes("<u>One</u>"))
                update("SetPlayback", "Playing")
                tryVerify(() => text.text.includes("<u>&lt;two&gt;</u>"), 2000)
                update("SetPlayback", "Paused")
                update("MovePosition", 3)
                tryCompare(LyricsService, "current", -1)
                compare(compact.compactText, "♪", "An interlude must not retain an ended lyric")
                update("MovePosition", 4)
                tryCompare(LyricsService, "current", 1)
                tryCompare(text, "text", "Last line")
                verify(LyricsService.seekTo(0))
                tryVerify(() => text.text.includes("<u>One</u>"))
                const lines = detail.children.find(child => child.currentIndex !== undefined)
                tryCompare(lines, "currentIndex", 0)
                const detailText = lines.currentItem.children.find(child => child.text !== undefined)
                tryVerify(() => detailText.text.includes("<u>One</u>"))
                Config.lockscreen.lyricsEnabled = true
                GlobalStates.lockscreenVisible = true
                tryCompare(LyricsService, "watchers", 3)
                const lockLyrics = controlOfType(lock, "LyricsView")
                compare(lockLyrics.mode, "compact")
                const lockText = lockLyrics.children.find(child => child.text !== undefined && child.visible)
                tryVerify(() => lockText.text.includes("<u>One</u>"))
                verify(!lockText.truncated)
                update("SetTrack", 100)
                tryVerify(() => LyricsService.readFor === LyricsService.track && LyricsService.source === "lrclib", 5000)
                compare(LyricsService.lines[0].text, "Fallback")
                compare(LyricsService.lines[0].words.length, 0)
                MprisController.trackedPlayer = MprisController.filteredPlayers.find(
                    player => player.dbusName === "org.mpris.MediaPlayer2.nonchalant_test")
                compare(LyricsService.ciderPlayer, false)
                compare(LyricsService.ciderTrackId, "")
                tryVerify(() => LyricsService.readFor === LyricsService.track && LyricsService.source === "lrclib", 5000)
                compare(LyricsService.lines[0].text, "Fallback")
                verify(!text.text.includes("<font"), "Cider word highlighting must not leak into another player")
                compact.active = false
                detail.active = false
                GlobalStates.lockscreenVisible = false
                tryCompare(LyricsService, "watchers", 0)
                tryCompare(LyricsService, "queryActive", false)
                console.log("CIDER_LYRICS_RUNTIME_PASSED")
                Qt.quit()
            }
        }
    }
    Timer { interval: 15000; running: true; onTriggered: { console.error("CIDER_TIMEOUT"); Qt.quit() } }
}
'''

BACKEND = r'''
import json, sys
from pathlib import Path
root = Path(sys.argv.pop(1))
sys.path.insert(0, str(root / "scripts"))
import cider_lyrics

def request(url, headers):
    if url.endswith("/now-playing"):
        return {"info": {"name": "Ella Langley - Choosin' Texas (Official Video)",
                         "artistName": "EllaLangleyVEVO", "playParams": {"id": "1"}}}
    if url.endswith("/tokens"):
        return {"data": {"developerToken": "fixture", "userToken": "fixture", "storefront": "us"}}
    return {"data": [{"attributes": {"ttml": '<tt xmlns="http://www.w3.org/ns/ttml"><body><p begin="0" end="2"><span begin="0" end="1">One</span> <span begin="1" end="2">&lt;two&gt;</span></p><p begin="4" end="5">Last line</p></body></tt>'}}]}

cider_lyrics.request_json = request
import lyrics
lyrics.lookup = lambda *args, **kwargs: {"syncedLyrics": "[00:00]Fallback"}
args = sys.argv[1:]
print(json.dumps(lyrics.report(args[0], args[1], args[2], float(args[3]), args[4],
                              args[5] if len(args) > 5 else None)))
'''


@unittest.skipIf(getattr(mpris_runtime.MprisRuntimeTests, "__unittest_skip__", False), "MPRIS runtime dependencies required")
class CiderLyricsRuntimeTests(unittest.TestCase):
    def test_word_highlighting_seek_pause_interludes_and_player_switch(self):
        with tempfile.TemporaryDirectory(prefix="nonchalant-cider-runtime-") as directory:
            fixture = Path(directory)
            for name in ("modules", "config", "assets", "version"):
                (fixture / name).symlink_to(ROOT / name, target_is_directory=(ROOT / name).is_dir())
            scripts = fixture / "scripts"
            scripts.mkdir()
            # Production QML invokes this thin helper with the usual metadata arguments.
            (scripts / "lyrics.py").write_text(
                BACKEND.replace('root = Path(sys.argv.pop(1))', f'root = Path({str(ROOT)!r})'))
            (fixture / "shell.qml").write_text(QML)
            home = fixture / "home"
            home.mkdir()
            runtime = fixture / "runtime"
            runtime.mkdir(mode=0o700)
            env = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"),
                   "XDG_STATE_HOME": str(home / "state"), "XDG_DATA_HOME": str(home / "data"),
                   "XDG_CACHE_HOME": str(home / "cache"), "XDG_RUNTIME_DIR": str(runtime),
                   "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
                   "NIRI_SOCKET": str(fixture / "no-compositor.sock"), "PYTHONPATH": str(ROOT)}
            env.pop("WAYLAND_DISPLAY", None)
            env.pop("DBUS_SESSION_BUS_ADDRESS", None)
            env.pop("CIDER_API_TOKEN_FILE", None)
            result = subprocess.run(
                ["dbus-run-session", "--", sys.executable, "-m", "tests.e2e.test_cider_lyrics_runtime",
                 "--exercise", str(fixture)], env=env, capture_output=True, text=True, timeout=25)
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("CIDER_LYRICS_RUNTIME_PASSED", output, output)
            self.assertNotIn("Binding loop", output, output)
            self.assertNotIn("TypeError", output, output)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--exercise":
        sys.exit(mpris_runtime.exercise(Path(sys.argv[2]), player_name="cider", success_marker="CIDER_LYRICS_RUNTIME_PASSED"))
    unittest.main()
