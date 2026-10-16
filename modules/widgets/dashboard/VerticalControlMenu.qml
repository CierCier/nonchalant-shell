pragma ComponentBehavior: Bound

import QtQuick
import qs.modules.bar.island

Item {
    id: root

    property string mode: "wifi"
    signal backRequested()
    signal closeRequested()
    implicitWidth: mode === "media" ? 480 : 400
    implicitHeight: panelLoader.item?.implicitHeight ?? 340

    function focusCurrentTab(): void {
        root.forceActiveFocus();
    }

    Keys.onEscapePressed: root.closeRequested()

    Loader {
        id: panelLoader
        anchors.fill: parent
        sourceComponent: {
            switch (root.mode) {
            case "sound": return soundPanel;
            case "mic": return micPanel;
            case "bluetooth": return bluetoothPanel;
            case "battery": return batteryPanel;
            case "media": return mediaPanel;
            case "stats": return statsPanel;
            default: return wifiPanel;
            }
        }
    }

    Component { id: soundPanel; IslandSoundPanel { onBackRequested: root.backRequested() } }
    Component { id: micPanel; IslandMicPanel { onBackRequested: root.backRequested() } }
    Component { id: wifiPanel; IslandWifiPanel { onBackRequested: root.backRequested() } }
    Component { id: bluetoothPanel; IslandBluetoothPanel { onBackRequested: root.backRequested() } }
    Component { id: batteryPanel; IslandBatteryPanel { onBackRequested: root.backRequested() } }
    Component { id: statsPanel; IslandStatsPanel { onBackRequested: root.backRequested() } }
    Component { id: mediaPanel; IslandMediaCenterPanel { onBackRequested: root.backRequested() } }
}
