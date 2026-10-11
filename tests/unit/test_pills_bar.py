#!/usr/bin/env python3
"""
test_pills_bar.py
Unit test suite for the new floating Pills Bar layout (PillsBar.qml).
Validates contracts, separate floating pills, fluid animations, and surface integrations.
"""

import os
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class TestPillsBarLayout(unittest.TestCase):
    """Verifies that PillsBar.qml implements all requirements and adheres to fleet standards."""

    @classmethod
    def setUpClass(cls):
        cls.pills_bar_path = ROOT_DIR / "modules/bar/layouts/PillsBar.qml"
        cls.bar_content_path = ROOT_DIR / "modules/bar/BarContent.qml"
        cls.visibilities_path = ROOT_DIR / "modules/services/Visibilities.qml"
        cls.shell_panel_path = ROOT_DIR / "modules/widgets/dashboard/controls/ShellPanel.qml"
        cls.reservation_path = ROOT_DIR / "modules/shell/ReservationWindows.qml"

        with open(cls.pills_bar_path, "r", encoding="utf-8") as f:
            cls.pills_content = f.read()

        with open(cls.bar_content_path, "r", encoding="utf-8") as f:
            cls.bar_content = f.read()

        with open(cls.visibilities_path, "r", encoding="utf-8") as f:
            cls.visibilities_content = f.read()

        with open(cls.shell_panel_path, "r", encoding="utf-8") as f:
            cls.shell_panel_content = f.read()

        with open(cls.reservation_path, "r", encoding="utf-8") as f:
            cls.reservation_content = f.read()

    def test_file_exists(self):
        """PillsBar.qml exists in modules/bar/layouts/."""
        self.assertTrue(self.pills_bar_path.exists())

    def test_registered_in_bar_content(self):
        """BarContent.qml loads PillsBar for pills style and provides correct contracts."""
        self.assertIn('barStyle === "pills"', self.bar_content)
        self.assertIn("isPills: barStyle === \"pills\"", self.bar_content)
        self.assertIn("PillsBar {", self.bar_content)
        self.assertIn("pillsComponent", self.bar_content)

    def test_visibilities_registration_lifecycle(self):
        """PillsBar registers and unregisters with Visibilities service."""
        self.assertIn("Visibilities.registerIsland(root.screen.name, root)", self.pills_content)
        self.assertIn("Visibilities.unregisterIsland(root.screen.name, root)", self.pills_content)

    def test_bar_content_contract_properties(self):
        """PillsBar satisfies all BarContent and UnifiedShellPanel contract properties."""
        self.assertIn("property int barTargetHeight", self.pills_content)
        self.assertIn("property int baseOuterMargin", self.pills_content)
        self.assertIn("property int totalBarHeight", self.pills_content)
        self.assertIn("property bool timerInputActive", self.pills_content)
        self.assertIn("property bool dashboardInputActive", self.pills_content)
        self.assertIn("property alias barHitbox", self.pills_content)
        self.assertIn("property Item dashboardHitbox", self.pills_content)
        self.assertIn("property Item dropHitbox", self.pills_content)
        self.assertIn("property bool islandActive", self.pills_content)

    def test_floating_geometry_constants(self):
        """PillsBar defines floating geometry (top margin and fully rounded pills)."""
        self.assertIn("readonly property int pillHeight: 36", self.pills_content)
        self.assertIn("readonly property int topMargin: 8", self.pills_content)
        self.assertIn("readonly property real pillRadius: pillHeight / 2", self.pills_content)
        self.assertIn("readonly property real panelRadius: Styling.radius(4)", self.pills_content)

    def test_state_machine_methods(self):
        """PillsBar implements expand, collapse, and retraction methods."""
        self.assertIn("function expand(mode: string)", self.pills_content)
        self.assertIn("function collapse()", self.pills_content)
        self.assertIn("function finishRetraction()", self.pills_content)
        self.assertIn("FocusGrabManager.clearTopGrab()", self.pills_content)
        self.assertIn("Visibilities.closeActiveBarPopup()", self.pills_content)

    def test_separate_floating_pills_in_collapsed_state(self):
        """PillsBar renders distinct separate pills in the collapsed state."""
        # Workspaces Pill
        self.assertIn("id: workspacesPill", self.pills_content)
        self.assertIn("NonchalantTaskbar", self.pills_content)
        self.assertIn("showBackground: false", self.pills_content)
        self.assertIn('root.expand("apps")', self.pills_content)

        # Context / Title Pill
        self.assertIn("id: contextPill", self.pills_content)
        self.assertIn("FluidTextProgress", self.pills_content)
        self.assertIn("root.contextLabel", self.pills_content)
        self.assertIn('root.expand("media")', self.pills_content)

        # Clock & Date Pill
        self.assertIn("id: clockPill", self.pills_content)
        self.assertIn("root.formattedTime", self.pills_content)
        self.assertIn("root.formattedDate", self.pills_content)
        self.assertIn('root.expand("dashboard")', self.pills_content)
        self.assertIn('root.expand("calendar")', self.pills_content)

        # Status & Indicators Pill
        self.assertIn("id: statusPill", self.pills_content)
        self.assertIn("AudioFormatBadge", self.pills_content)
        self.assertIn("IslandStatusIcons", self.pills_content)
        self.assertIn("NetworkService", self.pills_content)
        self.assertIn("BluetoothService", self.pills_content)
        self.assertIn("Config.bar.pinned", self.pills_content)

    def test_fluid_spring_animations(self):
        """Morphing container uses organic spring overshoot for expand and monotonic for collapse."""
        self.assertIn("Motion.expandDuration", self.pills_content)
        self.assertIn("Motion.collapseDuration", self.pills_content)
        self.assertIn("Motion.overshoot", self.pills_content)
        self.assertIn("Easing.OutBack", self.pills_content)
        self.assertIn("Easing.OutCubic", self.pills_content)
        self.assertIn("Behavior on width", self.pills_content)
        self.assertIn("Behavior on height", self.pills_content)

    def test_animation_guards_follow_fleet_standards(self):
        """Guards must not use flawed barNormallyVisible check."""
        self.assertNotIn("enabled: root.barNormallyVisible", self.pills_content)
        self.assertIn("(root.shouldBeRevealed || root.isExpanded) && !root.retractingToHidden", self.pills_content)

    def test_all_expanded_panels_ported(self):
        """PillsBar includes all 16 expanded panels from dynamic island."""
        panels = [
            "IslandOsdBanner",
            "IslandNotificationBanner",
            "IslandDashboard",
            "IslandPowerPanel",
            "IslandSoundPanel",
            "IslandMicPanel",
            "IslandWifiPanel",
            "IslandBluetoothPanel",
            "IslandStatsPanel",
            "IslandAlertsPanel",
            "IslandWallpaperPanel",
            "IslandBatteryPanel",
            "IslandWeatherPanel",
            "IslandMediaCenterPanel",
            "IslandCalendarPanel",
            "LauncherView",
        ]
        for panel in panels:
            self.assertIn(panel, self.pills_content, f"Missing panel: {panel}")

    def test_tactile_feedback_on_interactive_elements(self):
        """Interactive pills and buttons implement cohesive tactile scaling with PressBehavior."""
        self.assertIn("PressBehavior on scale", self.pills_content)
        self.assertIn("scale: contextMouse.pressed ? 0.94 : 1.0", self.pills_content)
        self.assertIn("scale: clockMouse.pressed ? 0.94 : 1.0", self.pills_content)

    def test_visibilities_and_ipc_integration(self):
        """Visibilities recognizes pills as an island-like style for seamless IPC."""
        self.assertIn('s === "island" || s === "pills"', self.visibilities_content)

    def test_reservation_windows_integration(self):
        """ReservationWindows does not reserve space for pills unless pinned."""
        self.assertIn('Config.bar?.style ?? "default") === "pills"', self.reservation_content)

    def test_settings_style_selector_option(self):
        """ShellPanel Settings includes Pills in the Style selector."""
        self.assertIn('label: "Pills"', self.shell_panel_content)
        self.assertIn('value: "pills"', self.shell_panel_content)


if __name__ == "__main__":
    unittest.main()
