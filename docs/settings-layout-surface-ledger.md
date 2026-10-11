# Settings layout coverage

Settings uses the available pane width and opens directly to editable tabs, without a repeated page heading or an Overview menu.

Hard constraints: preserve the concurrent media edits; edit tracked sources; allow automatic hot reload without restarting Quickshell or Niri; retain theme tokens, typed properties, and existing navigation transitions; do not commit or push.

| Surface | Applies | Evidence and verification |
|---|---|---|
| Settings window, shortcuts, search, and settings requests | Yes | All enter `SettingsTab`; its loader binds each panel's width limit to the available width. Existing navigation runtime checks pass. |
| Network, Bluetooth, Mixer, AI | Yes | Runtime visits all four pages at 1600, 900, and 680 pixels. Functional panel actions and status remain. |
| Shell: Bar, Sidebar, Lockscreen, System | Yes | Every tab is visited at all three widths. Duplicate menu and title/back row removed. Bar is the default. |
| Theme: General, Shadows, Colors | Yes | Every tab is visited at all three widths. Duplicate menu and title/back row removed. General is the default. |
| System: Weather, Performance, Resources | Yes | Every tab is visited at all three widths. Duplicate menu and title/back row removed. Weather is the default. |
| Nested theme variant selector, gradient editor, stops, and color picker | Yes | They inherit the full content width. Runtime opens and closes the picker, resizes it, and confirms return to Colors. |
| Back, forward, tab memory, and scrolling | Yes | Existing history checks pass; revisiting Theme retains Colors. Panel scroll resets remain in the shared host. |
| Compact panel dimensions | Yes | Direct ThemePanel instantiation retains the existing 480-pixel cap. Settings alone overrides the cap. |
| Compositor overview | No | Separate window-management behavior, unrelated to the removed settings Overview tabs. |
| Providers, persistence schema, connection modes, and media widgets | No | This change only affects settings layout and navigation; no service or schema changes. |
| Runtime and syntax checks | Yes | `tests/e2e/test_settings_lyrics_runtime.py` exercises real QML loading. Focused syntax validation passes. |

The live settings window was inspected after hot reload. Offscreen runtime checks exercise every page and tab; individual hardware actions and every nested control were not clicked on the live desktop.
