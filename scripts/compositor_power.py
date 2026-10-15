#!/usr/bin/env python3
"""Control monitor power when the shell is not running."""

import argparse
import json
import os
from pathlib import Path
import socket
import sys


def request(path: str, payload: str, newline: bool = False) -> str:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(3)
        connection.connect(path)
        connection.sendall(payload.encode())
        response = bytearray()
        while data := connection.recv(65536):
            response.extend(data)
            if len(response) > 1024 * 1024:
                raise ValueError("Compositor response is too large")
            if newline and b"\n" in response:
                break
        return response.decode().strip()


def selected_compositor() -> str:
    explicit = os.environ.get("NONCHALANT_COMPOSITOR", "")
    if explicit:
        if explicit in ("niri", "hyprland"):
            return explicit
        raise ValueError("NONCHALANT_COMPOSITOR must be niri or hyprland")
    niri = bool(os.environ.get("NIRI_SOCKET"))
    hyprland = bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"))
    if niri and hyprland:
        desktops = os.environ.get("XDG_CURRENT_DESKTOP", "").lower().split(":")
        if "niri" in desktops and "hyprland" not in desktops:
            return "niri"
        if "hyprland" in desktops and "niri" not in desktops:
            return "hyprland"
        raise ValueError("Ambiguous compositor session; set NONCHALANT_COMPOSITOR")
    if niri or hyprland:
        return "niri" if niri else "hyprland"
    raise ValueError("No supported compositor session")


def power(enabled: bool) -> None:
    if selected_compositor() == "niri":
        action = "PowerOnMonitors" if enabled else "PowerOffMonitors"
        reply = json.loads(request(os.environ["NIRI_SOCKET"], json.dumps({"Action": {action: {}}}) + "\n", newline=True))
        if "Err" in reply:
            raise ValueError(reply["Err"])
        if "Ok" not in reply:
            raise ValueError("Invalid Niri response")
        return
    signature = os.environ["HYPRLAND_INSTANCE_SIGNATURE"]
    if "/" in signature or signature in (".", ".."):
        raise ValueError("Invalid Hyprland instance signature")
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
    path = runtime / "hypr" / signature / ".socket.sock"
    if not path.exists():
        path = Path("/tmp/hypr") / signature / ".socket.sock"
    status = request(str(path), "j/status")
    lua = status != "unknown request" and json.loads(status).get("configProvider") == "lua"
    command = ('hl.dsp.dpms({ action = "' + ("enable" if enabled else "disable") + '" })') if lua else ("dpms " + ("on" if enabled else "off"))
    reply = request(str(path), "dispatch " + command)
    if reply != "ok":
        raise ValueError("Monitor power request failed: " + reply)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", choices=("on", "off"))
    args = parser.parse_args()
    try:
        power(args.state == "on")
    except (OSError, ValueError, KeyError) as error:
        print(f"Monitor power: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
