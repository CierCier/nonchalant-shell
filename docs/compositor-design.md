# Compositor service design

## Problem

The shell needs Niri and Hyprland window/workspace state without making its UI understand either IPC protocol. Niri ordering, tile geometry, overview dismissal, and the existing island transitions must survive extraction. Quickshell's generic workspace protocol does not supply all those facts.

## Usage

```qml
readonly property list<CompositorWorkspace> visibleWorkspaces:
    CompositorService.workspacesForOutput(bar.screen.name)
onClicked: CompositorService.focusWindow(windowData.id)

readonly property bool hasWindowTouchingTop:
    CompositorService.hasWindowAtTop(screen.name, islandHeight + 8)

CompositorService.moveWindowToWorkspace(window.id, workspace.id, false)
```

Callers store IDs for delayed operations. IDs are opaque strings; names and ordering indices are separate. Actions return whether the service accepted submission. Completion is established by observing compositor state, not the return value.

## Shape

`CompositorService.qml` selects exactly one backend, validates targets, exposes typed lists/focused records, filters ordinary workspaces, and owns the shared top-edge query. URL loading isolates the optional Hyprland module from Niri installations. `NONCHALANT_COMPOSITOR=niri|hyprland` overrides selection; otherwise socket environment and desktop identity select the session. Ambiguous or unsupported sessions remain unready.

`CompositorBackend.qml` constructs a complete typed snapshot before publication. Unchanged snapshots retain object identity. Replaced records belong to the retired snapshot, which is destroyed on the next QML turn after consumers have switched. It handles domain object ownership without adding a command registry.

| Record | Important fields |
| --- | --- |
| `CompositorWorkspace` | String ID, display name, index, output, active/focused/urgent/special, active window ID, window count |
| `CompositorWindow` | String ID, process ID, app ID, title, workspace ID, output, focused/floating/fullscreen, output-local logical rectangle |
| `CompositorOutput` | Output name, global logical origin and dimensions, scale, active workspace |
| `CompositorState` | Typed lists, fullscreen output names, overview state |

`NiriBackend.qml` retains the event reducer and output/overview queries. Actions use native JSON socket requests, including workspace references by ID and targeted close. This avoids focus-then-close races and ambiguous workspace indices. The normalizer preserves scroll ordering, floating geometry fallbacks, and tile-only fullscreen inference. A stale active-window reference cannot hide an output after the window moves elsewhere.

`hyprland/HyprlandBackend.qml` consumes native Quickshell monitor, workspace, and toplevel models. Its codec translates logical coordinates and builds Lua-dispatcher actions (legacy string dispatch is not supported). Special workspaces remain available for visibility/fullscreen checks and are excluded from ordinary taskbar scrolling. The backend refreshes geometry because movement/resizing does not always emit an IPC event. An auxiliary event socket detects disconnects that the native models do not expose.

Settings placement matches the shell process ID and title, revalidates the captured workspace, and waits for observed movement/focus. Both logout entry points call the service. CLI monitor power and output listing use compositor IPC. Backlight discovery uses DRM connector names independently of the compositor. FIFO IPC uses the session runtime directory so isolated shells do not share a global pipe.

## Synthesis decision

Two design candidates compared backend-owned typed snapshots with shared-service snapshot ownership. Backend ownership won because it keeps the reducer and state generation together. The service still owns shared queries and target validation. The second candidate supplied the power-menu execution audit, independent backlight discovery, and complete CLI migration.

The design hides protocol payloads, selectors, lifecycle, and coordinate translation behind a small set of desktop actions. The UI retains presentation and dismissal policy. No service changes island modes directly.

## Tradeoffs and alternatives

- Typed immutable snapshots require allocation and retirement; unchanged snapshots are skipped to avoid recreating delegates during polling.
- Native Hyprland dispatch has no completion/error callback. Upstream logs and observed state remain the execution evidence.
- Native Hyprland models refresh asynchronously and lack a generation-completed signal. Reconnect readiness and stale-data recovery need separate runtime evidence; publication alone cannot prove fresh server state.
- The generic workspace/foreign-toplevel protocol alternative lost because missing geometry, membership, overview, and desktop actions would leak compositor decisions back into callers.
- A raw JSON dispatch compatibility shim lost because it would restore the multi-compositor syntax coupling removed by commit `ee3abab2`.

## History constraints

Source history explicitly records the Niri bootstrap in `06520d21`, dispatch-shim removal in `ee3abab2`, floating geometry/focus preservation in `229ab24d`, and fixed-size fullscreen handling in `a64b462d`. These informed preservation requirements. External issue, chat, and telemetry evidence was unavailable; no broader historical motivation is asserted.

## Verification

Use `nix develop path:.#compositor-test` for the codec and disposable compositor tests. The runtime runner creates private config, cache, data, state, runtime sockets and D-Bus paths. It scrubs inherited displays and compositor sockets, renders on Mesa software OpenGL, and addresses only owned process IDs. It never replaces the user's desktop session.

See the support guide and runtime result artifacts for the executed version matrix and any untested behavior. The Python simulation suite remains useful for UI invariants but is not proof of live compositor behavior.
