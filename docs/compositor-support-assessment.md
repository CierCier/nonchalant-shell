# Niri and Hyprland support assessment

Baseline assessed 2026-10-14, before implementation. See [the current design](compositor-design.md). This is the original implementation proposal based on source inspection and current upstream documentation. Runtime code and dependencies have not been changed.

Hyprland support is feasible with a shared compositor service and two backends. The current shell requires Niri for meaningful window/workspace state and several desktop actions. Updating Quickshell alone will not remove that requirement.

## Current dependency map

`modules/services/NiriService.qml` owns the JSON event stream, output queries, overview state, normalized clients/workspaces/monitors, fullscreen detection, and compositor actions. Its event stream starts unconditionally and retries every second after exit. On a Hyprland session it would continue attempting to run Niri.

There are 12 other QML files referencing `NiriService`:

| Consumer | Dependency |
| --- | --- |
| `shell.qml` | Eager service initialization |
| `modules/bar/workspaces/NonchalantTaskbar.qml` | Per-output workspace filtering, window lists, focus actions, raw Niri workspace-up/down actions |
| `modules/bar/layouts/IslandBar.qml` | Active workspace/client, window count and geometry, overview hiding |
| `modules/bar/layouts/DefaultBar.qml` | Fullscreen and overview hiding |
| `modules/bar/island/IslandDashboard.qml` | Focused output selection |
| `modules/bar/island/IslandWallpaperPanel.qml` | Wallpaper target output |
| `modules/widgets/dashboard/wallpapers/WallpapersTab.qml` | Wallpaper target output |
| `modules/widgets/config/SettingsWindow.qml` | Target output/workspace, settings-window discovery, move and focus |
| `modules/services/Visibilities.qml` | Overlay routing, monitor focus changes, dismissal on overview/fullscreen |
| `modules/services/GlobalShortcuts.qml` | Settings placement and output lookup |
| `modules/services/Brightness.qml` | Focused monitor for brightness control |
| `modules/globals/GlobalStates.qml` | Assistant placement |

Additional direct command dependencies exist in both power menus, `cli.sh` monitor power and output listing, and `scripts/brightness_list.sh` internal-output discovery. These must migrate too.

The reusable UI, audio, media, notifications, launcher search, wallpaper rendering, layer-shell windows, input masks, focus-grab coordination, and session-lock protocol are largely independent of Niri. Their behavior still needs verification on Hyprland, especially keyboard focus, stacking, reservations, and multi-monitor locking.

## Quickshell API status

The installed binary reports Quickshell 0.3.1, revision `5d5d49873fe8cf1f99ddfd5006ceb2057c5c9b13`. Nix packaging selects `pkgs.quickshell` through the locked nixpkgs input. The installed binary is not proof of the version produced by that package expression.

Upstream documents [0.3.2](https://quickshell.org/changelog/), including support for Hyprland's new workspace address format and fixes for session locks, monitor attachment, asynchronous loader teardown, and socket reconnects. Use it as the candidate baseline, then verify the actual package version and compiled modules before choosing a supported minimum. Avoid updating all of nixpkgs solely to upgrade Quickshell unless necessary.

The current [Hyprland API](https://quickshell.org/docs/v0.3.2/types/Quickshell.Hyprland/Hyprland/) provides monitors, workspaces, typed toplevels, focus state, dispatch, and refresh operations. It also exposes `usingLua`; dispatcher syntax differs in Lua mode. An adapter must translate actions for the supported Hyprland versions and wait for module initialization before deciding the mode.

[HyprlandToplevel](https://quickshell.org/docs/v0.3.2/types/Quickshell.Hyprland/HyprlandToplevel/) exposes typed workspace/monitor relationships. Extra geometry/state in `lastIpcObject` is a snapshot and requires explicit refresh when it changes. Treat JSON snapshots as data, not signal-producing QML objects.

[Quickshell.WindowManager](https://quickshell.org/docs/v0.3.2/types/Quickshell.WindowManager/) currently supports only `ext-workspace-v1`. Its workspace abstraction does not replace this shell's window membership, geometry, compositor overview, session exit, or monitor-power requirements. Protocol support on each target compositor must be checked. Do not make this API the sole backend in the initial migration.

[ToplevelManager](https://quickshell.org/docs/v0.3.2/types/Quickshell.Wayland/ToplevelManager/) uses `zwlr-foreign-toplevel-management-v1`. That requires advertised protocol support and does not supply the complete existing Niri contract. Keep Niri IPC for Niri; no Niri-specific module is listed in the reviewed Quickshell module catalog.

The shell already uses modern `qs.*` imports, `WlrLayershell`, `Variants`, `JsonAdapter`, and `Quickshell.execDetached`. There is no evidence that these need wholesale replacement. Keep unrelated service API migrations separate.

## Proposed ownership and contracts

Introduce `CompositorService` as the only UI entry point. Move transport and compositor-specific normalization into Niri and Hyprland backends. Load only the selected backend, including isolating the Hyprland import so a Niri installation can run without that optional module.

Select the active session from compositor environment/socket evidence, not whether an executable happens to be installed. Expose readiness and disconnection state. If session detection is ambiguous, require an explicit selection instead of silently selecting the wrong compositor. Add defaults alongside any new persistent config key.

Use concrete QML record types for windows, workspaces, and outputs. Keep opaque string identifiers distinct from display names and workspace ordering. Convert to native Niri numbers or Hyprland selectors only in the backend. Migrate `GlobalStates.settingsTargetWorkspaceId`, numeric comparisons in `IslandBar`, and settings placement with the contract. Use an explicit missing-workspace value rather than truthiness checks.

The shared contract needs window/workspace/output lists; focused records; per-output active workspace; window membership; logical output-local geometry; fullscreen outputs; overview state and availability; and actions for focus, close, move, adjacent workspace, logout, and monitor power. Do not expose `runNiriAction()` or raw Hyprland dispatch strings to UI callers. Preserve existing Niri ordering and workspace filtering.

For CLI callers, route actions through shell IPC where the shell is running, or use a small explicit session-selected command path if operation without the shell is required. Keep internal-output discovery independent of a required Niri executable.

## Regression risks requiring evidence

- `IslandBar.isWindowTouchingTop()` returns true for every tiled window because of Niri layout semantics. Hyprland layouts can place tiled windows below the top edge. Define this policy deliberately; normalize monitor origin and scale before evaluating floating-window geometry.
- Niri fullscreen is inferred from tile size matching logical output size. Preserve that behavior during extraction. Hyprland distinguishes internal fullscreen state from the state reported to the client; use the compositor state relevant to covering the shell. See [Hyprland fullscreen dispatchers](https://wiki.hypr.land/configuring/core/dispatchers/).
- Named and special Hyprland workspaces need explicit filtering, ordering, visibility, and focus rules. Niri per-output indices cannot be copied into global Hyprland workspace semantics. Define scroll behavior on the current output and both boundaries.
- Niri overview dismissal must remain intact. Do not claim parity with a Hyprland overview plugin until that integration is implemented and tested. Represent unsupported overview behavior explicitly.
- Existing `NiriService.closeWindow()` runs `close-window` after the focus process exits without checking success. A failed focus can close the current window. Repair this action contract before exposing it through both backends, preferably using a verified targeted close operation.
- Settings placement discovers its window by title and retries for two seconds. Test mapping delays, duplicate titles, output changes, and moving without following focus.
- Preserve `expand()`/`collapse()` transitions, focus-grab clearing, input-mask routing, asymmetric animation curves, and exclusive zones. Backend work must not bypass these mechanisms.

## Migration order and acceptance gates

1. Capture Niri runtime behavior on both bar styles. Upgrade Quickshell independently, verify actual package/module versions, then repeat those checks. Keep a reproducible prior package for rollback.
2. Extract the shared service with Niri behavior preserved. Migrate all 12 consumers and direct command callers. Add tests that exercise the actual normalizer and action generation with recorded events, including disconnect/reconnect, malformed data, hotplug, urgency, and failed commands.
3. Add the Hyprland backend through Quickshell's native APIs. Cover named/special workspaces, address identity, Lua dispatch, geometry refresh, fullscreen transitions, and output migration. Document a tested compositor/version matrix.
4. Run the same real-session acceptance checklist on Niri and Hyprland before enabling automatic selection by default. Update the root and services `AGENTS.md` Niri-only rules, README, package requirements, and keybind examples with the implemented scope.

The runtime checklist must cover both bar styles; pinned/unpinned states; empty/occupied workspaces; taskbar buttons and scrolling; nested popups, Escape and click-outside; launcher launch and dismissal; settings placement; all island panels and reverse transitions; wallpaper/brightness targeting; assistant placement; notifications and OSD; fullscreen/maximized transitions; overview on Niri; monitor hotplug and mixed scaling; lock/unlock and suspend/resume; and safe logout/monitor-power checks in a disposable session. Compare screenshots and animations against a Niri baseline and inspect QML/runtime logs. Never restart the user's shell or compositor manually.

## Verification performed

`./tests/run_tests.sh --all` passed 177 Python tests and 12 schema assertions. The syntax script scanned 31 QML files without detecting its selected syntax-error patterns. The runner reports 195 passes because it counts syntax validation as six tests regardless of scanned file count.

The syntax wrapper ignores nonzero lint exits unless output matches selected syntax-error strings. This is not full import, type, or binding validation. The tests named integration/e2e use Python simulations, not the live QML shell. The adversarial simulation file is not included by the master runner.

`qs list --all` found no running instances, and `niri` is absent from PATH. No compositor session behavior, rendered UI, Hyprland dispatch, locking, or packaged Quickshell upgrade was tested. Zero UI/feature regression is therefore an acceptance target, not an established result.
