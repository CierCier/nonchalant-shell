#!/usr/bin/env python3
"""Exercise a disposable compositor. Every child receives private session paths."""

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--compositor", choices=("niri", "hyprland"), required=True)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--shell", action="store_true", help="also render the complete shell")
    parser.add_argument("--style", choices=("default", "island", "left"), default="default")
    parser.add_argument("--quickshell", default="qs", help="Quickshell binary, including an older baseline package")
    parser.add_argument("--power-cycle", action="store_true", help="exercise DPMS only on disposable test outputs")
    parser.add_argument("--baseline", action="store_true", help="capture a source without CompositorService")
    parser.add_argument("--inside-session", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args()


def private_environment(root):
    env = dict(os.environ)
    for key in ("WAYLAND_DISPLAY", "WAYLAND_SOCKET", "DISPLAY", "NIRI_SOCKET",
                "HYPRLAND_INSTANCE_SIGNATURE", "DBUS_SESSION_BUS_ADDRESS",
                "DBUS_STARTER_ADDRESS", "DBUS_STARTER_BUS_TYPE", "XAUTHORITY",
                "XDG_ACTIVATION_TOKEN", "DESKTOP_STARTUP_ID", "QT_QPA_PLATFORM",
                "QT_QUICK_BACKEND"):
        env.pop(key, None)
    for key, directory in {
        "HOME": "home", "XDG_CONFIG_HOME": "config",
        "XDG_CACHE_HOME": "cache", "XDG_DATA_HOME": "data", "XDG_STATE_HOME": "state"
    }.items():
        path = root / directory
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        env[key] = str(path)
    runtime = Path(tempfile.mkdtemp(prefix="nc-", dir="/tmp"))
    runtime.chmod(0o700)
    (root / "runtime").symlink_to(runtime, target_is_directory=True)
    env["XDG_RUNTIME_DIR"] = str(runtime)
    env.update(LIBGL_ALWAYS_SOFTWARE="1", GALLIUM_DRIVER="llvmpipe",
               WLR_RENDERER="gles2", QSG_RHI_BACKEND="opengl",
               XDG_SESSION_TYPE="wayland", XDG_CURRENT_DESKTOP="nonchalant-test")
    env.pop("NONCHALANT_COMPOSITOR", None)
    return env


class Session:
    def __init__(self, root, quickshell):
        self.root = root
        self.env = dict(os.environ)
        self.processes = []
        self.logs = []
        self.quickshell = quickshell
        self.state = None

    def start(self, name, command, env=None):
        log = (self.root / f"{name}.log").open("w")
        self.logs.append(log)
        process = subprocess.Popen(command, env=env or self.env, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        self.processes.append(process)
        return process

    def run(self, command):
        result = subprocess.run(command, env=self.env, capture_output=True,
                                text=True, timeout=15)
        if result.returncode:
            raise RuntimeError(f"{command!r}: {result.stderr or result.stdout}")
        return result.stdout.strip()

    def wait(self, description, predicate, timeout=20):
        deadline = time.monotonic() + timeout
        last_error = None
        while time.monotonic() < deadline:
            try:
                value = predicate()
                if value:
                    return value
            except (RuntimeError, ValueError) as error:
                last_error = error
            time.sleep(0.1)
        raise RuntimeError(f"Timed out waiting for {description}: {last_error}")

    def ipc(self, process, target, method, *args):
        if process not in self.processes:
            raise RuntimeError("IPC target is not owned by this test session")
        return self.run([self.quickshell, "ipc", "--pid", str(process.pid), "call", target,
                         method, *(str(argument) for argument in args)])

    def stop(self):
        for process in reversed(self.processes):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
        for log in self.logs:
            log.close()


def start_compositor(session, compositor):
    runtime = Path(session.env["XDG_RUNTIME_DIR"])
    weston_config = session.root / "weston.ini"
    weston_config.write_text("[core]\nidle-time=0\n[shell]\npanel-position=none\n")
    compositor_env = dict(session.env)
    if compositor == "hyprland":
        compositor_env.pop("LIBGL_ALWAYS_SOFTWARE", None)
        compositor_env.pop("GALLIUM_DRIVER", None)
    session.start("weston", ["weston", "--backend=headless", "--renderer=gl",
        "--width=1280", "--height=720", "--socket=test-parent",
        f"--config={weston_config}"], compositor_env)
    session.wait("private Weston socket", lambda: (runtime / "test-parent").exists())
    if compositor == "niri":
        config = session.root / "niri.kdl"
        config.write_text('output "winit" {\n mode "1280x720"\n}\n'
                          'workspace "test-one"\nworkspace "test-two"\n'
                          'prefer-no-csd\nscreenshot-path null\n'
                          'hotkey-overlay {\n skip-at-startup\n}\n')
        session.run(["niri", "validate", "--config", str(config)])
        env = dict(session.env, WAYLAND_DISPLAY="test-parent", WINIT_UNIX_BACKEND="wayland")
        session.start("niri", ["niri", "--config", str(config)], env)
        socket = session.wait("private Niri IPC socket",
            lambda: next(iter(runtime.glob("niri.*.sock")), None))
        session.env["NIRI_SOCKET"] = str(socket)
    else:
        config = session.root / "hyprland.conf"
        config.write_text('monitor = ,1280x720@60,0x0,1\n'
            'workspace = 1, default:true\nworkspace = 2, persistent:true\n'
            'workspace = name:test-named, monitor:TEST-1, persistent:true\n'
            'misc {\n disable_hyprland_logo = true\n disable_splash_rendering = true\n'
            ' force_default_wallpaper = 0\n}\n'
            'animations {\n enabled = false\n}\n'
            'debug {\n disable_logs = false\n enable_stdout_logs = true\n}\n')
        env = dict(compositor_env, WAYLAND_DISPLAY="test-parent", HYPRLAND_NO_SD_VARS="1",
                   HYPRLAND_NO_SD_NOTIFY="1", XDG_CURRENT_DESKTOP="Hyprland")
        session.start("hyprland", ["Hyprland", "--config", str(config)], env)
        socket = session.wait("private Hyprland IPC socket",
            lambda: next(iter(runtime.glob("hypr/*/.socket.sock")), None))
        session.env["HYPRLAND_INSTANCE_SIGNATURE"] = socket.parent.name
        session.run(["hyprctl", "output", "create", "headless", "TEST-1"])
        session.wait("private Hyprland headless monitor",
            lambda: json.loads(session.run(["hyprctl", "-j", "monitors"])))
        session.run(["hyprctl", "dismissnotify", "-1"])
    display = session.wait("private compositor Wayland socket",
        lambda: next((path for path in runtime.glob("wayland-*")
                      if path.is_socket()), None))
    session.env["WAYLAND_DISPLAY"] = display.name
    session.env["QT_QPA_PLATFORM"] = "wayland"


def exercise(session, source, args, passed):
    private_source = session.root / "source"
    shutil.copytree(source, private_source, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    fixture = Path(__file__).parent
    shutil.copy2(fixture / "probe.qml", private_source / "compositor-probe.qml")
    shutil.copy2(fixture / "client.qml", private_source / "compositor-client.qml")
    shutil.copy2(fixture / "RuntimeTestControl.qml", private_source / "RuntimeTestControl.qml")
    if args.compositor == "hyprland":
        native_file = private_source / "hyprland-native.qml"
        shutil.copy2(fixture / "hyprland-native.qml", native_file)
        native_probe = session.start("hyprland-native", [session.quickshell, "-p", str(native_file)])
        session.native_state = lambda: session.ipc(native_probe, "hyprland-native", "state")
        native_state = session.wait("native Quickshell Hyprland IPC", lambda:
            session.ipc(native_probe, "hyprland-native", "state"))
        (session.root / "quickshell-native-state.json").write_text(native_state)
    colors = Path(session.env["HOME"]) / ".cache/nonchalant"
    colors.mkdir(parents=True)
    shutil.copy2(private_source / "assets/colors/Catppuccin/dark.json", colors / "colors.json")
    shell_source = private_source / "shell.qml"
    shell_text = shell_source.read_text()
    final_brace = shell_text.rfind("}")
    shell_source.write_text(shell_text[:final_brace] + "    RuntimeTestControl {}\n" + shell_text[final_brace:])
    if args.baseline:
        shortcuts = private_source / "modules/services/GlobalShortcuts.qml"
        shortcuts.write_text(shortcuts.read_text().replace(
            'readonly property string ipcPipe: "/tmp/nonchalant_ipc.pipe"',
            'readonly property string ipcPipe: Quickshell.env("XDG_RUNTIME_DIR") + "/nonchalant_ipc.pipe"'))
    config = Path(session.env["XDG_CONFIG_HOME"]) / "nonchalant/config"
    config.mkdir(parents=True)
    (config / "bar.json").write_text(json.dumps({"style": args.style}))
    (config / "ai.json").write_text(json.dumps({"enabled": False}))
    if args.baseline:
        if not args.shell:
            raise RuntimeError("--baseline requires --shell")
    else:
        probe = session.start("probe", [session.quickshell, "-p", str(private_source / "compositor-probe.qml")])

        def state():
            return json.loads(session.ipc(probe, "compositor-test", "state"))

        session.state = state
        session.diagnostic = lambda: json.loads(session.ipc(probe, "compositor-test", "diagnostic"))

        session.wait("ready compositor service", lambda: state()["ready"])
    shell = None
    if args.shell:
        shell = session.start("shell", [session.quickshell, "-p", str(private_source)])
        session.wait("shell IPC", lambda: session.ipc(shell, "nonchalant", "run", "test-noop") or True)
        time.sleep(2)
        session.run(["grim", str(session.root / "empty-shell.png")])
        def shell_state():
            return json.loads(session.ipc(shell, "shell-test", "state"))
        session.shell_state = shell_state
        for command, field, island_mode in (("launcher", "launcherOpen", "apps"),
                ("dashboard", "dashboardOpen", "dashboard"), ("power", "powerOpen", "power")):
            session.ipc(shell, "nonchalant", "run", command)
            session.wait(f"{command} opens", lambda: (
                shell_state()["island"]["mode"] == island_mode
                if args.style == "island" else shell_state()[field]))
            time.sleep(0.7)
            session.run(["grim", str(session.root / f"{command}.png")])
            (session.root / f"{command}-state.json").write_text(json.dumps(shell_state(), indent=2))
            session.ipc(shell, "nonchalant", "run", command)
            session.wait(f"{command} dismisses", lambda: (
                not shell_state()["island"]["expanded"]
                if args.style == "island" else not shell_state()[field]))
            time.sleep(0.7)
            passed.append(f"{command} opens and reverse toggle dismisses")
    client = session.start("client", [session.quickshell, "-p", str(private_source / "compositor-client.qml")])
    if args.baseline:
        time.sleep(2)
        session.run(["grim", str(session.root / "occupied-shell.png")])
        passed.append("baseline empty and occupied screenshots captured")
        return
    current = session.wait("two mapped clients", lambda: (
        value if len([w for w in value["windows"] if w["title"].startswith("Nonchalant Test ")
                      and w["output"] and w["workspaceId"]]) == 2
        else None) if (value := state()) else None)
    (session.root / "initial-state.json").write_text(json.dumps(current, indent=2))
    first = next(w for w in current["windows"] if w["title"] == "Nonchalant Test A")
    second = next(w for w in current["windows"] if w["title"] == "Nonchalant Test B")
    passed.append("actual clients appear in shared service")
    if shell:
        time.sleep(0.7)
        session.run(["grim", str(session.root / "occupied-shell.png")])
    session.ipc(probe, "compositor-test", "focusWindow", second["id"])
    session.wait("second client focus", lambda: state()["focusedWindow"] == second["id"])
    session.ipc(probe, "compositor-test", "focusWindow", first["id"])
    session.wait("targeted window focus", lambda: state()["focusedWindow"] == first["id"])
    passed.append("focus action reaches compositor")
    session.ipc(probe, "compositor-test", "adjacent", first["output"], 1)
    current = session.wait("adjacent workspace", lambda: (
        value if value["focusedWorkspace"] != first["workspaceId"] else None)
        if (value := state()) else None)
    destination = current["focusedWorkspace"]
    session.ipc(probe, "compositor-test", "focusWorkspace", first["workspaceId"])
    session.wait("original workspace focus", lambda: state()["focusedWorkspace"] == first["workspaceId"])
    session.ipc(probe, "compositor-test", "moveWindow", first["id"], destination)
    session.wait("window move", lambda: any(w["id"] == first["id"] and
        w["workspaceId"] == destination for w in state()["windows"]))
    assert state()["focusedWorkspace"] == first["workspaceId"], "move unexpectedly followed focus"
    passed.append("workspace scroll and targeted move reach compositor")
    session.ipc(probe, "compositor-test", "focusWindow", first["id"])
    session.wait("moved client focus", lambda: state()["focusedWindow"] == first["id"])
    session.ipc(client, "test-client", "fullscreen", "true")
    session.wait("fullscreen output", lambda: first["output"] in state()["fullscreenOutputs"])
    passed.append("fullscreen is reported")
    session.run(["grim", str(session.root / "fullscreen.png")])
    session.ipc(client, "test-client", "fullscreen", "false")
    session.wait("fullscreen exit", lambda: first["output"] not in state()["fullscreenOutputs"])
    passed.append("fullscreen exit is reported")
    session.ipc(probe, "compositor-test", "closeWindow", "invalid-window-id")
    time.sleep(0.4)
    assert any(w["id"] == first["id"] for w in state()["windows"]), "invalid close killed focused client"
    passed.append("invalid close preserves focused client")
    session.ipc(probe, "compositor-test", "closeWindow", second["id"])
    session.wait("targeted close", lambda: not any(w["id"] == second["id"] for w in state()["windows"]))
    assert any(w["id"] == first["id"] for w in state()["windows"])
    passed.append("targeted close preserves other client")
    if shell:
        target_workspace = state()["focusedWorkspace"]
        target_output = state()["focusedMonitor"]
        session.ipc(shell, "nonchalant", "run", "settings")
        settings_window = session.wait("real settings window", lambda: next((w for w in state()["windows"]
            if "settings" in w["title"].lower() or "configuration" in w["title"].lower()), None))
        session.wait("settings placement and focus", lambda: any(w["id"] == settings_window["id"]
            and w["workspaceId"] == target_workspace and w["output"] == target_output
            for w in state()["windows"]) and state()["focusedWindow"] == settings_window["id"])
        time.sleep(1)
        session.run(["grim", str(session.root / "settings.png")])
        passed.append("full shell settings maps on requested workspace/output and receives focus")
    (session.root / "final-state.json").write_text(json.dumps(state(), indent=2))


def main():
    args = arguments()
    if args.inside_session is None:
        root = args.artifacts.resolve() if args.artifacts else Path(tempfile.mkdtemp(prefix="nonchalant-compositor-"))
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        env = private_environment(root)
        bus_config = root / "dbus.conf"
        bus_config.write_text('<busconfig><type>session</type><auth>EXTERNAL</auth>'
            f'<listen>unix:path={Path(env["XDG_RUNTIME_DIR"]) / "bus"}</listen>'
            '<policy context="default"><allow send_destination="*"/>'
            '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        command = ["dbus-run-session", f"--config-file={bus_config}", "--", sys.executable, str(Path(__file__).resolve()),
                   "--inside-session", str(root), "--source", str(args.source.resolve()),
                   "--compositor", args.compositor, "--style", args.style,
                   "--quickshell", args.quickshell]
        command.extend(flag for flag, enabled in (("--shell", args.shell),
            ("--baseline", args.baseline), ("--power-cycle", args.power_cycle)) if enabled)
        runtime = Path(env["XDG_RUNTIME_DIR"])
        try:
            result = subprocess.run(command, env=env)
        finally:
            try:
                (root / "runtime").unlink()
                shutil.copytree(runtime, root / "runtime", ignore=lambda directory, names: [
                    name for name in names if (Path(directory) / name).is_socket()
                    or (Path(directory) / name).is_fifo()])
            finally:
                shutil.rmtree(runtime, ignore_errors=True)
        print(f"Artifacts: {root}")
        return result.returncode
    session = Session(args.inside_session, args.quickshell)
    result = {"compositor": args.compositor, "style": args.style,
              "source": str(args.source), "passed": []}
    exit_code = 1
    try:
        start_compositor(session, args.compositor)
        session.env["NONCHALANT_COMPOSITOR"] = args.compositor
        if args.compositor == "hyprland":
            session.env["QT_LOGGING_RULES"] = "quickshell.hyprland.ipc.debug=true;quickshell.io.socket.debug=true"
        result["quickshellVersion"] = session.run([session.quickshell, "--version"])
        if args.power_cycle:
            session.power_script = args.source / "scripts/compositor_power.py"
            session.run([sys.executable, str(session.power_script), "off"])
            session.run([sys.executable, str(session.power_script), "on"])
            result["passed"].append("standalone monitor power off/on reaches disposable compositor")
        exercise(session, args.source, args, result["passed"])
        print(json.dumps(result, indent=2))
        exit_code = 0
    except (RuntimeError, AssertionError, subprocess.TimeoutExpired) as error:
        result["error"] = str(error)
        print(json.dumps(result, indent=2), file=sys.stderr)
        exit_code = 1
    except BaseException as error:
        result["error"] = f"{type(error).__name__}: {error}".rstrip(": ")
        raise
    finally:
        if hasattr(session, "power_script"):
            try:
                session.run([sys.executable, str(session.power_script), "on"])
            except RuntimeError as error:
                result["powerRestoreError"] = str(error)
        if hasattr(session, "native_state"):
            try:
                (session.root / "quickshell-native-final-state.json").write_text(session.native_state())
            except RuntimeError:
                pass
        if hasattr(session, "diagnostic"):
            try:
                (session.root / "backend-diagnostic.json").write_text(json.dumps(session.diagnostic(), indent=2))
            except (RuntimeError, ValueError):
                pass
        if session.state is not None:
            try:
                (session.root / "last-state.json").write_text(json.dumps(session.state(), indent=2))
            except (RuntimeError, ValueError):
                pass
        if hasattr(session, "shell_state"):
            try:
                (session.root / "last-shell-state.json").write_text(json.dumps(session.shell_state(), indent=2))
            except (RuntimeError, ValueError):
                pass
            try:
                session.run(["grim", str(session.root / "final-screen.png")])
            except RuntimeError:
                pass
        if args.compositor == "niri" and "NIRI_SOCKET" in session.env:
            try:
                (session.root / "native-focused-window.json").write_text(session.run(["niri", "msg", "--json", "focused-window"]))
            except RuntimeError:
                pass
        if args.compositor == "hyprland" and "HYPRLAND_INSTANCE_SIGNATURE" in session.env:
            for query in ("monitors", "clients", "workspaces"):
                try:
                    (session.root / f"native-{query}.json").write_text(session.run(["hyprctl", "-j", query]))
                except RuntimeError:
                    pass
        session.stop()
        result["runtimeDiagnosticCounts"] = {}
        for path in session.root.glob("*.log"):
            lines = path.read_text(errors="replace").splitlines()
            result["runtimeDiagnosticCounts"][path.name] = {
                "qmlErrors": sum("ERROR: qs:" in line for line in lines),
                "bindingOrTypeWarnings": sum(any(marker in line for marker in
                    ("Binding loop", "TypeError:", "ReferenceError:")) for line in lines),
                "missingTools": sum("Process failed to start" in line for line in lines)
            }
        broken = sum(counts["qmlErrors"] + counts["bindingOrTypeWarnings"]
                     for counts in result["runtimeDiagnosticCounts"].values())
        if broken:
            result["error"] = result.get("error") or (
                f"{broken} QML errors or binding failures in runtime logs")
            exit_code = 1
        (session.root / "result.json").write_text(json.dumps(result, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
