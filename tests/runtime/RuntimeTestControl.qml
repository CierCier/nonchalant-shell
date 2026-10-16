import QtQuick
import Quickshell
import Quickshell.Io
import qs.modules.services
import qs.modules.globals

Item {
    IpcHandler {
        target: "shell-test"
        function state(): string {
            const island = Visibilities.getIslandForActive();
            const outputName = Quickshell.screens[0]?.name ?? "";
            return JSON.stringify({
                activeModule: Visibilities.currentActiveModule,
                activeScreen: Visibilities.getForActive()?.screenName ?? "",
                activeLauncher: Visibilities.getForActive()?.launcher ?? false,
                screenLaunchers: Object.keys(Visibilities.screens).map(name => ({
                    name: name, launcher: Visibilities.screens[name].launcher
                })),
                launcherOpen: GlobalStates.launcherOpen,
                dashboardOpen: GlobalStates.dashboardOpen,
                popupOpen: Visibilities.activeBarPopup?.isOpen ?? false,
                systemMonitorOpen: GlobalStates.systemMonitorOpen,
                controlMenu: Visibilities.activeBarPopup?.menuMode ?? "",
                powerOpen: Visibilities.powerMenuButtons[outputName]?.popupOpen ?? false,
                hasActiveGrab: FocusGrabManager.hasActiveGrab,
                settingsVisible: GlobalStates.settingsWindowVisible,
                island: island ? {
                    mode: island.currentMode,
                    expanded: island.isExpanded,
                    retracting: island.retractingToHidden,
                    geometry: [island.x, island.y, island.width, island.height]
                } : null
            });
        }
    }
}
