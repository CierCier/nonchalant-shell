"""Exercise media progress and seeking in Quickshell on a private session bus."""

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
QML = r'''
import QtQuick
import QtTest
import Quickshell
import Quickshell.Io
import qs.config
import qs.modules.services
import qs.modules.components
import qs.modules.bar.island
import qs.modules.widgets.dashboard.widgets

ShellRoot {
    FloatingWindow {
        visible: true
        implicitWidth: 1000
        implicitHeight: 900
        IslandWaveformBar { id: waveform; width: 400; height: 38 }
        PositionSlider { id: slider; player: MprisController.activePlayer; width: 400; height: 30; y: 50 }
        FullPlayer { id: full; width: 400; height: 400; y: 100 }
        LockPlayer { id: lock; width: 400; height: 150; y: 550 }
        IslandMediaCenterPanel { id: center; width: 420; height: implicitHeight; x: 500 }
        IslandMediaCard { id: card; width: 420; height: implicitHeight; x: 500; y: 500 }
        Process { id: control }
        TestCase {
            name: "MprisDurationRuntime"
            when: Config.initialLoadComplete && MprisController.activePlayer !== null
            function update(method, argument) {
                control.command = ["gdbus", "call", "--session", "--dest",
                    "org.mpris.MediaPlayer2.nonchalant_test", "--object-path",
                    "/org/mpris/MediaPlayer2", "--method", "org.nonchalant.Test." + method,
                    String(argument)]
                control.running = true
                tryVerify(() => !control.running, 2000)
            }
            function controlOfType(item, type) {
                if (String(item).startsWith(type)) return item
                for (const child of item.children ?? []) {
                    const found = controlOfType(child, type)
                    if (found) return found
                }
                return null
            }
            function verifyProgress(expected) {
                const circle = controlOfType(full, "CircularSeekBar")
                const lockSlider = controlOfType(lock, "PositionSlider")
                verify(circle !== null)
                verify(lockSlider !== null)
                tryVerify(() => Math.abs(circle.value - expected) < 0.001, 1000,
                    "Full player progress must follow position and duration while paused")
                tryVerify(() => Math.abs(lockSlider.value - expected) < 0.001, 1000,
                    "Lock player progress must follow position and duration while paused")
                verify(Math.abs(waveform.progress - expected) < 0.001)
            }
            function test_unknown_and_late_duration() {
                const player = MprisController.activePlayer
                compare(LyricsService.youtubeTrack, true)
                compare(player.lengthSupported, false)
                compare(MprisController.length, 0)
                compare(waveform.progress, 0)
                compare(slider.length, 0)
                verify(!slider.children[0].enabled)
                const track = LyricsService.track
                update("MovePosition", 96)
                tryCompare(MprisController, "position", 96, 2000)
                compare(LyricsService.track, track, "Position changes must not restart lyrics lookup")
                update("SetDuration", 421)
                tryCompare(MprisController, "length", 421, 2000)
                tryCompare(waveform, "length", 421, 2000)
                tryCompare(slider, "length", 421, 2000)
                verifyProgress(96 / 421)
                verify(LyricsService.track !== track, "Late duration should refine the recording once")
                update("MovePosition", 120)
                tryCompare(MprisController, "position", 120, 2000)
                verifyProgress(120 / 421)
                update("SetDuration", 0)
                tryCompare(player, "lengthSupported", false, 2000)
                compare(MprisController.length, 421, "A missing update must retain the verified duration for this track")
                compare(slider.length, 421)
                verifyProgress(120 / 421)

                update("SetDuration", 421)
                const seekCount = player.metadata["nonchalant:seekCount"]
                mousePress(slider, 200, 15)
                verify(slider.isDragging)
                update("MovePosition", 130)
                tryCompare(MprisController, "position", 130, 2000)
                compare(player.metadata["nonchalant:seekCount"], seekCount,
                    "Incoming playback updates must not seek while dragging")
                mouseMove(slider, 300, 15)
                mouseRelease(slider, 300, 15)
                tryVerify(() => player.metadata["nonchalant:seekCount"] === seekCount + 1, 2000)
                tryVerify(() => Math.abs(MprisController.position - 0.75 * 421) < 0.1, 2000)
                update("MovePosition", 140)
                tryCompare(MprisController, "position", 140, 2000)
                tryVerify(() => Math.abs(slider.value - 140 / 421) < 0.001, 1000,
                    "After seeking the slider must keep following playback")
                verifyProgress(140 / 421)

                update("SetPlayback", "Playing")
                tryCompare(MprisController, "isPlaying", true, 2000)
                const start = MprisController.position
                tryVerify(() => MprisController.position > start + 0.5, 2000,
                    "Progress must advance without Seeked signals during playback")
                verifyProgress(MprisController.progress)
                update("SetPlayback", "Paused")
                tryCompare(MprisController, "isPlaying", false, 2000)
                wait(200)
                const paused = MprisController.position
                wait(350)
                compare(MprisController.position, paused, "Paused progress must stay still")
                update("SetTrack", 209)
                tryCompare(MprisController, "trackTitle", "Dracula", 2000)
                tryCompare(MprisController, "position", 0, 2000)
                tryCompare(MprisController, "length", 209, 2000)
                verifyProgress(0)
                update("SetDuration", 0)
                compare(MprisController.length, 209)
                update("SetSource", "slowtrack01")
                tryCompare(MediaDuration, "busy", true, 2000)
                compare(MprisController.length, 0, "A new video must not inherit the previous duration")
                wait(250)
                update("SetSource", "fasttrack01")
                tryCompare(MprisController, "length", 333, 5000)
                compare(slider.length, 333)
                update("SetDuration", 999)
                compare(MprisController.length, 333, "YouTube's verified recording must override stale browser duration")
                update("SetDuration", 0)
                verify(slider.children[0].enabled, "Recovered duration must enable fractional seeking")
                update("MovePosition", 99)
                tryCompare(MprisController, "position", 99, 2000)
                verifyProgress(99 / 333)
                wait(1200)
                compare(MprisController.length, 333, "Canceled lookup must not overwrite the current track")
                compare(MediaDuration.busy, false)
                update("SetSource", "livestream1")
                tryCompare(MediaDuration, "live", true, 5000)
                compare(MprisController.length, 0, "A live stream must not use a fabricated finite duration")
                LyricsService.readFor = LyricsService.track
                LyricsService.status = "missing"
                center.lyricsActive = true
                card.lyricsActive = true
                tryCompare(LyricsService, "watchers", 2, 1000,
                    "An initially empty panel must still request lyrics")
                const emptyHeight = center.implicitHeight
                const emptyCardHeight = card.implicitHeight
                const centerLyrics = controlOfType(center, "LyricsView")
                verify(!centerLyrics.visible)
                LyricsService.readFor = LyricsService.track
                LyricsService.status = "timed"
                LyricsService.synced = true
                LyricsService.lines = [{time: 0, text: "A fixture lyric"}]
                center.lyricsActive = true
                card.lyricsActive = true
                tryVerify(() => centerLyrics.visible, 1000)
                tryVerify(() => center.implicitHeight > emptyHeight + 100, 1000)
                tryVerify(() => card.implicitHeight > emptyCardHeight + 20, 1000)
                compare(LyricsService.watchers, 2)
                LyricsService.lines = []
                LyricsService.status = "missing"
                tryVerify(() => !centerLyrics.visible, 1000)
                tryCompare(center, "implicitHeight", emptyHeight, 1000)
                tryCompare(card, "implicitHeight", emptyCardHeight, 1000)
                compare(LyricsService.watchers, 2, "Collapsed lyrics must stay subscribed while the panel is open")
                center.lyricsActive = false
                card.lyricsActive = false
                tryCompare(LyricsService, "watchers", 0, 1000)
                console.log("MPRIS_DURATION_RUNTIME_PASSED")
                Qt.quit()
            }
        }
    }
    Timer {
        interval: 15000
        running: true
        onTriggered: { console.error("MPRIS_DURATION_RUNTIME_TIMEOUT"); Qt.quit() }
    }
}
'''


def exercise(fixture, video_id="invalid"):
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib

    DBusGMainLoop(set_as_default=True)
    interface = "org.mpris.MediaPlayer2.Player"

    class Player(dbus.service.Object):
        position = 94
        duration = 0
        playback = "Paused"
        rate = 0.0
        timestamp = time.monotonic()
        track = 1
        seek_count = 0
        source = video_id

        def current_position(self):
            elapsed = time.monotonic() - self.timestamp if self.playback == "Playing" else 0
            return self.position + elapsed * self.rate

        def move_position(self, seconds):
            self.position = seconds
            self.timestamp = time.monotonic()

        def metadata(self):
            data = {
                "mpris:trackid": dbus.ObjectPath(f"/org/mpris/MediaPlayer2/Track/{self.track}"),
                "xesam:title": "Ella Langley - Choosin' Texas (Official Video)" if self.track == 1 else "Dracula",
                "nonchalant:seekCount": dbus.Int64(self.seek_count),
                "xesam:artist": dbus.Array(["EllaLangleyVEVO"], signature="s"),
                "xesam:url": f"https://www.youtube.com/watch?v={self.source}",
            }
            if self.duration > 0:
                data["mpris:length"] = dbus.Int64(self.duration * 1_000_000)
            return dbus.Dictionary(data, signature="sv")

        @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="s", out_signature="a{sv}")
        def GetAll(self, requested):
            if requested == interface:
                return {
                    "Metadata": self.metadata(), "PlaybackStatus": self.playback,
                    "Position": dbus.Int64(self.current_position() * 1_000_000), "Rate": dbus.Double(self.rate),
                    "MinimumRate": dbus.Double(1), "MaximumRate": dbus.Double(1),
                    "CanControl": True, "CanSeek": True, "CanPlay": True, "CanPause": True,
                    "CanGoNext": False, "CanGoPrevious": False,
                }
            return {"Identity": "Nonchalant test player", "CanQuit": False, "CanRaise": False,
                    "HasTrackList": False, "SupportedUriSchemes": dbus.Array([], signature="s"),
                    "SupportedMimeTypes": dbus.Array([], signature="s")}

        @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ss", out_signature="v")
        def Get(self, requested, key):
            return self.GetAll(requested)[key]

        @dbus.service.signal("org.freedesktop.DBus.Properties", signature="sa{sv}as")
        def PropertiesChanged(self, requested, changed, invalidated):
            pass

        @dbus.service.signal(interface, signature="x")
        def Seeked(self, position):
            pass

        @dbus.service.method("org.nonchalant.Test", in_signature="x")
        def MovePosition(self, seconds):
            self.move_position(int(seconds))
            self.Seeked(dbus.Int64(self.position * 1_000_000))

        @dbus.service.method("org.nonchalant.Test", in_signature="x")
        def SetDuration(self, seconds):
            self.duration = int(seconds)
            self.PropertiesChanged(interface, {"Metadata": self.metadata()}, [])

        @dbus.service.method(interface, in_signature="ox")
        def SetPosition(self, track, microseconds):
            if str(track) != f"/org/mpris/MediaPlayer2/Track/{self.track}":
                return
            self.seek_count += 1
            self.move_position(int(microseconds) / 1_000_000)
            self.Seeked(dbus.Int64(microseconds))
            self.PropertiesChanged(interface, {"Metadata": self.metadata()}, [])

        @dbus.service.method("org.nonchalant.Test", in_signature="s")
        def SetPlayback(self, state):
            self.move_position(self.current_position())
            self.playback = str(state)
            self.rate = 1.0 if self.playback == "Playing" else 0.0
            self.PropertiesChanged(interface, {
                "PlaybackStatus": self.playback, "Rate": dbus.Double(self.rate)}, [])

        @dbus.service.method("org.nonchalant.Test", in_signature="x")
        def SetTrack(self, seconds):
            self.track += 1
            self.move_position(0)
            self.duration = int(seconds)
            self.PropertiesChanged(interface, {"Metadata": self.metadata()}, [])

        @dbus.service.method("org.nonchalant.Test", in_signature="s")
        def SetSource(self, video_id):
            self.source = str(video_id)
            self.PropertiesChanged(interface, {"Metadata": self.metadata()}, [])

    bus = dbus.SessionBus()
    name = dbus.service.BusName("org.mpris.MediaPlayer2.nonchalant_test", bus=bus)
    player = Player(name, "/org/mpris/MediaPlayer2")
    loop = GLib.MainLoop()
    thread = threading.Thread(target=loop.run, daemon=True)
    thread.start()
    try:
        result = subprocess.run(
            ["qs", "-p", str(fixture), "--no-duplicate", "--no-color"],
            capture_output=True, text=True, timeout=25 if video_id == "invalid" else 50,
        )
        output = result.stdout + result.stderr
        print(output)
        return 0 if result.returncode == 0 and "MPRIS_DURATION_RUNTIME_PASSED" in output else 1
    finally:
        loop.quit()
        thread.join(timeout=2)
        player.remove_from_connection()


@unittest.skipUnless(
    all(shutil.which(tool) for tool in ("qs", "dbus-run-session", "gdbus"))
    and all(importlib.util.find_spec(module) for module in ("dbus", "gi")),
    "Quickshell, DBus, and Python GLib bindings are required",
)
class MprisRuntimeTests(unittest.TestCase):
    def test_missing_duration_does_not_fake_progress_or_restart_lyrics(self):
        with tempfile.TemporaryDirectory(prefix="nonchalant-mpris-test-") as directory:
            fixture = Path(directory)
            for entry in ("modules", "config", "assets", "scripts", "version"):
                (fixture / entry).symlink_to(ROOT / entry, target_is_directory=(ROOT / entry).is_dir())
            (fixture / "shell.qml").write_text(QML)
            home = fixture / "home"
            home.mkdir()
            runtime = fixture / "runtime"
            runtime.mkdir(mode=0o700)
            fake_bin = fixture / "bin"
            fake_bin.mkdir()
            extractor = fake_bin / "yt-dlp"
            extractor.write_text("""#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
video_id = sys.argv[-1].split('v=')[-1]
if video_id == 'slowtrack01':
    Path(os.environ['XDG_STATE_HOME']).mkdir(parents=True, exist_ok=True)
    Path(os.environ['XDG_STATE_HOME'], 'slow-extractor.pid').write_text(str(os.getpid()))
    time.sleep(30)
print(json.dumps({'id': video_id, 'duration': 444 if video_id == 'slowtrack01' else 333,
                  'is_live': video_id == 'livestream1'}))
""")
            extractor.chmod(0o755)
            env = {
                **os.environ, "PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", ""), "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"),
                "XDG_STATE_HOME": str(home / ".local/state"), "XDG_DATA_HOME": str(home / ".local/share"),
                "XDG_CACHE_HOME": str(home / ".cache"), "XDG_RUNTIME_DIR": str(runtime),
                "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
                "NIRI_SOCKET": str(fixture / "no-compositor.sock"),
            }
            env.pop("WAYLAND_DISPLAY", None)
            env.pop("DBUS_SESSION_BUS_ADDRESS", None)
            result = subprocess.run(
                ["dbus-run-session", "--", sys.executable, __file__, "--exercise", str(fixture)],
                env=env, capture_output=True, text=True, timeout=30,
            )
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("MPRIS_DURATION_RUNTIME_PASSED", output, output)
            self.assertNotIn("MPRIS_DURATION_RUNTIME_TIMEOUT", output, output)
            canceled_pid = home / ".local/state/slow-extractor.pid"
            self.assertTrue(canceled_pid.exists(), "The slow extractor must have started before cancellation")
            pid = int(canceled_pid.read_text())
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                pass
            else:
                status = Path(f"/proc/{pid}/status").read_text().splitlines()[:3]
                os.kill(pid, 15)
                self.fail(f"Canceled extractor remains: {pid} {status}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--exercise":
        sys.exit(exercise(Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "invalid"))
    unittest.main()
