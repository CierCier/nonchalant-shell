Run disposable compositor checks with the Nix test environment:

```bash
nix develop .#compositor-test --command python3 tests/runtime/run_compositor.py --compositor niri --shell --style default
nix develop .#compositor-test --command python3 tests/runtime/run_compositor.py --compositor hyprland --shell --style island
```

The runner starts a private D-Bus session and assigns a private HOME, XDG directories and compositor sockets to its children. Both compositors run inside Weston on a separate headless display. Quickshell uses OpenGL RHI through Mesa llvmpipe so its shader-backed containers render correctly. Niri also uses software rendering. Hyprland requires a GPU render node for its DMA-BUF allocator; its headless parent has no physical display attached. IPC targets only Quickshell PIDs created by the runner; cleanup terminates only its owned process groups.

The test environment applies `nix/headless-aquamarine.patch` to Aquamarine 0.15.1 and loads it only in its Hyprland test wrapper. The patch negotiates the advertised `wl_seat`, `xdg_wm_base` and `wl_compositor` versions. Unpatched Aquamarine requests `wl_compositor` and `xdg_wm_base` version 6 from Weston, which advertises version 5, then disconnects. Production Hyprland packaging remains unchanged.

Each run leaves logs, screenshots, a JSON result, and final normalized state in the printed artifact directory. Supply `--artifacts /absolute/path` for a chosen directory. Use a new directory for each run. `--source /path/to/checkout` selects the shell under test. `--baseline --shell --source /path/to/old/checkout` captures empty and occupied screenshots without requiring the new compositor service. Baseline copies receive the same private FIFO isolation as the changed source. `--quickshell /absolute/path/to/qs` selects a previous Quickshell build for upgrade comparisons. `--style default` and `--style island` select both bar layouts through private configuration files. AI is disabled in the private configuration.

The integration checks exercise actual window mapping, focus, adjacent workspace navigation, moving a specific window without following focus, fullscreen entry and exit, safe failure for an invalid close target, and closing a particular window while preserving another. `--shell` also launches the complete shell, verifies launcher/dashboard/power-menu opening and reverse dismissal, opens settings through its real IPC entry point, and captures screenshots. A read-only test IPC component is added only to the private copy to inspect actual island and overlay state.

Use `--power-cycle` to check the standalone monitor-power fallback before starting Quickshell. Its environment selects only the disposable compositor. The runner restores its test outputs before cleanup. Result JSON includes separate counts for QML errors, binding/type warnings, and unavailable optional helper tools; compare those counts with a baseline run rather than treating every unavailable hardware helper as a compositor regression.

Passing these checks does not prove mixed-scale output behavior, monitor hotplug, every overlay and animation, named/special Hyprland workspace policy, Lua dispatch, PAM authentication, suspend/resume, or hardware brightness. Those require additional acceptance scenarios. Hardware power and brightness actions are deliberately excluded from this runner.
