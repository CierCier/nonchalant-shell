"""Exercise CLI delivery through private FIFOs and the real listener command."""

import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CliIpcTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="nonchalant-cli-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.runtime = self.root / "runtime ' $test"
        self.runtime.mkdir()
        self.env = {
            **os.environ, "HOME": str(self.root / "home"),
            "XDG_CONFIG_HOME": str(self.root / "config"),
            "XDG_CACHE_HOME": str(self.root / "cache"),
            "XDG_RUNTIME_DIR": str(self.runtime), "WAYLAND_DISPLAY": "test-display",
        }

    def invoke(self, command, expected):
        with (self.root / "cli.log").open("w+") as log:
            process = subprocess.Popen(
                ["bash", str(ROOT / "cli.sh"), "run", command], env=self.env,
                stdout=log, stderr=log, start_new_session=True, cwd=self.root)
            try:
                status = process.wait(timeout=5)
                log.seek(0)
                output = log.read()
                self.assertEqual(status, expected, output)
                return output
            finally:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                process.wait()

    def test_stale_fifo_fails_instead_of_reporting_delivery(self):
        os.mkfifo(self.runtime / "nonchalant_ipc.pipe")
        output = self.invoke("bar-pin", 1)
        self.assertIn("not accepting commands", output)

    def test_command_is_delivered_literally_before_success(self):
        pipe = self.runtime / "nonchalant_ipc.pipe"
        os.mkfifo(pipe)
        reader = os.open(pipe, os.O_RDONLY | os.O_NONBLOCK)
        self.addCleanup(os.close, reader)
        command = 'literal $(touch should-not-exist) "quoted"'
        self.invoke(command, 0)
        self.assertEqual(os.read(reader, 4096).decode(), command + "\n")
        self.assertFalse((self.root / "should-not-exist").exists())

    def listener_path(self, env):
        shortcuts = (ROOT / "modules/services/GlobalShortcuts.qml").read_text()
        expression = re.search(r"readonly property string ipcPipe: (.*?)\n\n", shortcuts, re.S)[1]
        script = "const env = JSON.parse(process.argv[1]); const Quickshell = {env: k => env[k] || ''};"
        script += "console.log((() => " + expression + ")());"
        paths = {key: env.get(key, "") for key in
                 ("XDG_RUNTIME_DIR", "XDG_CACHE_HOME", "HOME", "WAYLAND_DISPLAY")}
        return Path(subprocess.check_output(["node", "-e", script, json.dumps(paths)], text=True).strip())

    def test_fallback_separates_homes_even_with_the_same_display(self):
        paths = []
        for user in ("user-one", "user-two"):
            env = {**self.env, "HOME": str(self.root / user),
                   "WAYLAND_DISPLAY": "/private/session/display-2"}
            env.pop("XDG_RUNTIME_DIR")
            env.pop("XDG_CACHE_HOME")
            path = self.listener_path(env)
            self.assertEqual(path, self.root / user / ".cache/nonchalant/ipc/display-2.pipe")
            paths.append(path)
        self.assertNotEqual(paths[0], paths[1])

    def test_fallback_listener_and_cli_agree_on_a_private_user_path(self):
        self.env.pop("XDG_RUNTIME_DIR")
        shortcuts = (ROOT / "modules/services/GlobalShortcuts.qml").read_text()
        pipe = self.listener_path(self.env)
        self.assertTrue(pipe.is_relative_to(self.root / "cache"), pipe)
        listener = re.search(r'command: \["bash", "-c", ("(?:[^"\\]|\\.)*"), "nonchalant-ipc-listener"', shortcuts)[1]
        # Create the FIFO with the real listener, then deliver through the CLI.
        process = subprocess.Popen(
            ["bash", "-c", json.loads(listener), "nonchalant-ipc-listener", str(pipe)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        try:
            deadline = time.monotonic() + 3
            while not pipe.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(pipe.is_fifo())
            self.assertEqual(pipe.stat().st_mode & 0o777, 0o600)
            self.invoke("bar-pin", 0)
            self.assertTrue(select.select([process.stdout], [], [], 3)[0])
            self.assertEqual(process.stdout.readline(), b"bar-pin\n")
        finally:
            os.killpg(process.pid, signal.SIGTERM)
            process.communicate(timeout=3)


if __name__ == "__main__":
    unittest.main()
