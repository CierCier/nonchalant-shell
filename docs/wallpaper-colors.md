# Wallpaper colors

Select **Wallpaper** in the wallpaper picker's scheme menu, or run
`nonchalant run wallpaper-colors`. Both clear the active static preset and
regenerate the palette from the current global wallpaper. New wallpaper state
defaults to Wallpaper. Existing Material schemes and presets remain selected.

## Extraction

The extractor samples visible pixels, quantizes them into 64 color clusters,
and ranks clusters using population and perceptual chroma. It selects up to six
hues separated by at least 30 degrees in OKLab, then fills available slots with
distinct shades sampled from the image. Primary, secondary, and tertiary use
the first three samples, with lightness adjusted for readable text.

Every accent comes from the wallpaper, including status and terminal colors.
Legacy names such as `red`, `green`, and `blue` identify palette slots rather
than fixed hue families. A grayscale or single-hue image keeps a limited
accent palette. Missing slots reuse sampled colors.

Backgrounds have a small tint from the main image color. Surfaces have distinct
lightness levels. Accent foregrounds and container foregrounds are selected
for contrast in both modes. OLED overrides remain in `Colors.qml`.

Pillow supplies image extraction and is included in the Arch, Fedora, and Nix
dependencies. Material schemes use Matugen with Wallust as a fallback. Static
presets keep their existing palettes.

Generated palettes must match the complete color contract before an atomic
rename replaces the requested output file. Failed extraction preserves the
previous file. Each Material invocation uses a temporary config and output,
so a stale cache cannot count as success. Generation writes no additional
shared cache when the caller requests another output path.

## Metric roles

The classic resource panel uses `Colors.metricRole()` for data colors:

| Metric | Palette role |
| --- | --- |
| CPU | Primary below 70%, yellow from 70%, red from 90%. |
| Disk | Primary below 75%, yellow from 75%, red from 90%. |
| Memory | Blue. |
| GPU | Yellow, independent of vendor branding. |
| Network | Green. |

Island and Pills use the shared `IslandStatsPanel`: every resource badge and
progress fill uses the configured `primary` StyledRect variant. Icon foregrounds
use `Styling.srItem("primary")` so custom theme edits remain readable. Metric
palette names such as `blue` are colors, not StyledRect variants.

Inline OSD progress uses the primary selection role through `Colors.accentRole()`.
These roles still
resolve through the selected palette. Other widgets retain their existing
color assignments.

## Coverage ledger

| Path | Applicability and verification |
| --- | --- |
| Wallpaper picker and scheme selector | Applies. Wallpaper is an option alongside Material schemes and static presets. |
| Shell command | Applies. The command and shared scheme transition are executed in the focused tests, including preset clearing. |
| Startup and persisted selection | Applies. New state defaults to Wallpaper; saved schemes and presets are preserved. |
| Next/previous, indexed selection, per-screen selection | Applies. The established global wallpaper manager owns palette generation. Secondary instances return without publishing. Multiple physical monitors are not tested. |
| Dark/light switches | Applies. Both use the shared generator; palette contrast is tested in both modes. |
| Images, GIFs, video | Applies. Images and GIF first frames reach Pillow. Video uses the existing thumbnail path. GIF equivalence is tested; live video selection is not tested. |
| Generation failure | Applies. Invalid-image, stale-output, output-isolation, Matugen, and Wallust fallback tests check publication behavior. |
| Island and Pills resource panels | Applies. Their shared panel uses matching primary badges and progress fills. The isolated runtime test covers CPU, RAM, two GPU delegates, disk, network, low/high/low usage, and custom primary background/foreground edits. The live desktop is not driven by tests. |
| Classic resource panel | Applies. Metric colors resolve directly through Colors. Threshold decisions and caller coverage are tested. |
| Niri and Hyprland | The resource panel has no compositor-specific styling. Tests use an isolated offscreen display and private D-Bus/config/cache paths. |
| Shell widgets and application exports | Applies. Output matches the existing palette contract. Individual themed applications are not visually tested. |
| Static presets and OLED | Applies. Existing preset selection and OLED overrides remain. |
| Remote providers, relay, mobile clients and new config keys | Does not apply. Extraction and panel styling are local to this Wayland shell and use existing theme settings. |

Run the focused checks with:

```bash
python3 -m unittest tests.unit.test_wallpaper_palette -v
```

Run the shell checks with:

```bash
python3 tests/run_tests.py --all
```

Runtime tests use isolated user state and offscreen Quickshell processes. They
do not establish how the changes look in the active desktop session.
