"""Exercise the standalone power helper across its real Unix socket boundary."""

import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("compositor_power", ROOT / "scripts/compositor_power.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class PowerSocketTests(unittest.TestCase):
    def serve(self, path, exchanges, keep_open=False):
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(path))
        server.listen()
        received = []

        def run():
            try:
                for response in exchanges:
                    with server.accept()[0] as connection:
                        received.append(connection.recv(65536).decode())
                        connection.sendall(response.encode())
                        if keep_open:
                            connection.recv(1)
            finally:
                server.close()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        self.addCleanup(server.close)
        return received, thread

    def test_niri_power_without_a_shell_process(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as root:
            path = Path(root) / "socket"
            received, thread = self.serve(path, ['{"Ok":"Handled"}\n'], keep_open=True)
            with patch.dict(os.environ, {"NIRI_SOCKET": str(path)}, clear=True):
                helper.power(False)
            thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(json.loads(received[0]), {"Action": {"PowerOffMonitors": {}}})

    def test_hyprland_lua_status_selects_the_power_dispatch(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as root:
            path = Path(root) / "hypr" / "test" / ".socket.sock"
            path.parent.mkdir(parents=True)
            received, thread = self.serve(path, ['{"configProvider":"lua"}', "ok"])
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": root, "HYPRLAND_INSTANCE_SIGNATURE": "test"}, clear=True):
                helper.power(True)
            thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(received, ["j/status", 'dispatch hl.dsp.dpms({ action = "enable" })'])

    def test_rejected_action_is_reported(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as root:
            path = Path(root) / "socket"
            _, thread = self.serve(path, ['{"Err":"output unavailable"}\n'], keep_open=True)
            with patch.dict(os.environ, {"NIRI_SOCKET": str(path)}, clear=True):
                with self.assertRaisesRegex(ValueError, "output unavailable"):
                    helper.power(False)
            thread.join(3)
            self.assertFalse(thread.is_alive())

    def test_ambiguous_session_does_not_send_a_command(self):
        with patch.dict(os.environ, {"NIRI_SOCKET": "/unused", "HYPRLAND_INSTANCE_SIGNATURE": "unused"}, clear=True):
            with self.assertRaisesRegex(ValueError, "Ambiguous compositor"):
                helper.power(False)


if __name__ == "__main__":
    unittest.main()
