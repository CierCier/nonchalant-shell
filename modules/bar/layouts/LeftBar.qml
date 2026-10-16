pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Services.SystemTray
import qs.config
import qs.modules.bar.clock
import qs.modules.bar.systray
import qs.modules.components
import qs.modules.services
import qs.modules.services.compositor
import qs.modules.theme
import ".."

Item {
    id: root

    required property ShellScreen screen

    readonly property bool fullscreenOnScreen: CompositorService.fullscreenOutputs.indexOf(root.screen.name) !== -1
    readonly property bool reveal: !CompositorService.overviewOpen && !fullscreenOnScreen

    readonly property real outerRadius: Styling.radius(-4)
    readonly property int controlSize: Math.max(36, Config.theme.fontSize + 20)
    readonly property int edgeMargin: 4
    readonly property int contentPadding: 8
    readonly property int barWidth: controlSize + contentPadding * 2
    readonly property int barTargetHeight: barWidth
    readonly property int totalBarHeight: barTargetHeight + root.edgeMargin

    // Keep one floating gap at the screen edge and another beside the dock so
    // tiled windows do not touch the pills.
    readonly property int baseOuterMargin: root.edgeMargin * 2
    readonly property bool shadowsEnabled: false

    // Tray drawer; the chevron above the tray toggles it.
    property bool trayExpanded: false

    readonly property string networkIcon: {
        if (NetworkService.ethernet)
            return Icons.ethernet;
        if (!NetworkService.wifiEnabled)
            return Icons.wifiOff;
        if (!NetworkService.wifiConnected)
            return Icons.wifiNone;
        return NetworkService.wifiIconForStrength(NetworkService.networkStrength);
    }
    readonly property string networkTooltip: {
        if (NetworkService.ethernet)
            return "Ethernet";
        if (!NetworkService.wifiEnabled)
            return "Wi-Fi disabled";
        if (!NetworkService.wifiConnected)
            return "Wi-Fi disconnected";
        return NetworkService.activeSsid || "Wi-Fi";
    }

    property alias barHitbox: hitbox
    readonly property alias timerInputActive: clock.timeToolsOpen
    readonly property alias dashboardInputActive: clock.menuOpen
    readonly property alias dashboardHitbox: clock.dashboardHitbox
    readonly property bool islandActive: false

    // One footprint for launcher, workspace and status controls.
    component DockIconButton: Item {
        id: button

        required property string iconText
        required property string tooltipText
        property string description: ""
        property bool selected: false
        property bool muted: false
        property bool textLabel: false
        property bool occupied: false
        property bool urgent: false

        signal scrolled(real delta)
        signal secondaryClicked
        signal clicked

        implicitWidth: root.controlSize
        implicitHeight: root.controlSize
        Layout.alignment: Qt.AlignHCenter
        Accessible.role: Accessible.Button
        Accessible.name: tooltipText
        scale: buttonMouse.pressed ? 0.90 : 1.0

        PressBehavior on scale {
            pressed: buttonMouse.pressed
        }

        StyledRect {
            id: buttonSurface
            anchors.fill: parent
            variant: button.selected ? "focus" : "common"
            backgroundOpacity: button.selected ? 1 : 0
            radius: root.outerRadius
            enableShadow: false

            HoverTint {
                hovered: buttonMouse.containsMouse
                pressed: buttonMouse.pressed
            }
        }

        StyledText {
            anchors.centerIn: parent
            text: button.iconText
            font.family: button.textLabel ? Config.theme.font : Icons.font
            font.pixelSize: button.textLabel ? Config.theme.fontSize : Styling.fontSize(4)
            font.weight: button.selected || button.occupied ? Font.DemiBold : Font.Medium
            color: button.urgent ? Colors.red : (button.selected ? buttonSurface.item : Colors.overBackground)
            opacity: button.muted ? 0.5 : 1
        }

        MouseArea {
            id: buttonMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            onClicked: mouse => {
                if (mouse.button === Qt.RightButton)
                    button.secondaryClicked();
                else
                    button.clicked();
            }
            onWheel: wheel => {
                const delta = wheel.angleDelta.y || wheel.angleDelta.x;
                button.scrolled(delta);
                wheel.accepted = true;
            }
        }

        StyledToolTip {
            x: button.width + root.contentPadding
            y: (button.height - height) / 2
            show: buttonMouse.containsMouse
            tooltipText: button.tooltipText
            description: button.description
        }
    }

    Item {
        id: hitbox
        width: root.reveal ? root.totalBarHeight : 0
        height: root.height

        Item {
            id: bar
            x: root.edgeMargin
            y: root.edgeMargin
            width: root.barTargetHeight
            height: parent.height - root.edgeMargin * 2

            // Hidden for overview and fullscreen: retracts past the left
            // screen edge on a monotonic curve and springs back in with the
            // island's overshoot.
            property real retraction: 0
            transform: Translate {
                x: -bar.retraction * (root.totalBarHeight + root.edgeMargin)
            }

            states: State {
                name: "hidden"
                when: !root.reveal
                PropertyChanges {
                    bar.retraction: 1
                    bar.opacity: 0
                }
            }

            transitions: [
                Transition {
                    from: "hidden"
                    enabled: Motion.enabled
                    ParallelAnimation {
                        NumberAnimation {
                            property: "retraction"
                            duration: Motion.expandDuration
                            easing.type: Easing.OutBack
                            easing.overshoot: Motion.overshoot
                        }
                        NumberAnimation {
                            property: "opacity"
                            duration: Motion.fadeInDuration
                            easing.type: Easing.OutCubic
                        }
                    }
                },
                Transition {
                    to: "hidden"
                    enabled: Motion.enabled
                    NumberAnimation {
                        properties: "retraction,opacity"
                        duration: Motion.collapseDuration
                        easing.type: Easing.InCubic
                    }
                }
            ]

            StyledRect {
                anchors.fill: parent
                variant: "pane"
                radius: Styling.radius(0)
                backgroundOpacity: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: root.contentPadding
                    spacing: 4

                    DockIconButton {
                        iconText: Icons.launch
                        tooltipText: "Run menu"
                        selected: Visibilities.currentActiveModule === "launcher"
                        onClicked: GlobalShortcuts.toggleLauncher()
                    }

                    Separator {
                        Layout.fillWidth: false
                        Layout.preferredWidth: root.controlSize / 2
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: 4
                        Layout.bottomMargin: 4
                    }

                    Flickable {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        contentHeight: workspaceColumn.implicitHeight
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds

                        ColumnLayout {
                            id: workspaceColumn
                            width: parent.width
                            spacing: 4

                            Repeater {
                                model: CompositorService.workspacesForOutput(root.screen.name)

                                DockIconButton {
                                    required property CompositorWorkspace modelData
                                    iconText: String(modelData.idx)
                                    textLabel: true
                                    selected: modelData.active
                                    occupied: modelData.windows > 0
                                    urgent: modelData.is_urgent
                                    tooltipText: modelData.isNamed ? modelData.name : "Workspace " + modelData.idx
                                    description: modelData.windows + (modelData.windows === 1 ? " window" : " windows")
                                    onClicked: CompositorService.focusWorkspace(modelData.id)
                                    onScrolled: delta => {
                                        if (delta !== 0)
                                            CompositorService.focusAdjacentWorkspace(root.screen.name, delta < 0 ? 1 : -1);
                                    }
                                }
                            }
                        }
                    }

                    DockIconButton {
                        visible: SystemTray.items.values.length > 0
                        iconText: root.trayExpanded ? Icons.caretDown : Icons.caretUp
                        tooltipText: root.trayExpanded ? "Hide tray" : "Show tray"
                        selected: root.trayExpanded
                        onClicked: root.trayExpanded = !root.trayExpanded
                    }

                    Flickable {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: root.controlSize
                        Layout.preferredHeight: Math.min(systemTray.implicitHeight, root.height / 4)
                        visible: root.trayExpanded && SystemTray.items.values.length > 0
                        contentHeight: systemTray.implicitHeight
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds

                        SysTray {
                            id: systemTray
                            width: root.controlSize
                            height: implicitHeight
                            vertical: true
                            backgroundOpacity: 0
                            startRadius: root.outerRadius
                            endRadius: root.outerRadius
                        }
                    }

                    DockIconButton {
                        iconText: root.networkIcon
                        tooltipText: root.networkTooltip
                        description: "Open dashboard quick controls"
                        onClicked: clock.toggleCenterMenu()
                    }

                    DockIconButton {
                        visible: Audio.sink !== null
                        iconText: Audio.sink?.audio?.muted ? Icons.speakerSlash : Icons.speakerHigh
                        muted: Audio.sink?.audio?.muted ?? false
                        tooltipText: (muted ? "Muted" : "Volume " + Math.round(Audio.value * 100) + "%")
                        description: "Click to mute · Scroll to adjust"
                        onClicked: Audio.toggleMute()
                        onSecondaryClicked: clock.toggleCenterMenu()
                        onScrolled: delta => {
                            if (delta !== 0)
                                Audio.setVolume(Math.max(0, Math.min(1, Audio.value + (delta > 0 ? 0.05 : -0.05))));
                        }
                    }

                    DockIconButton {
                        visible: Audio.source !== null
                        iconText: Audio.source?.audio?.muted ? Icons.micSlash : Icons.mic
                        muted: Audio.source?.audio?.muted ?? false
                        tooltipText: muted ? "Microphone muted" : "Microphone " + Math.round((Audio.source?.audio?.volume ?? 0) * 100) + "%"
                        description: "Click to mute · Scroll to adjust"
                        onClicked: Audio.toggleMicMute()
                        onSecondaryClicked: clock.toggleCenterMenu()
                        onScrolled: delta => {
                            if (delta !== 0)
                                Audio.setMicVolume(Math.max(0, Math.min(1, (Audio.source?.audio?.volume ?? 0) + (delta > 0 ? 0.05 : -0.05))));
                        }
                    }

                    BatteryIndicator {
                        Layout.alignment: Qt.AlignHCenter
                        flat: true
                        showMeter: false
                        meterSize: root.controlSize
                        bar: root
                    }

                    Separator {
                        Layout.fillWidth: false
                        Layout.preferredWidth: root.controlSize / 2
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: 4
                        Layout.bottomMargin: 4
                    }

                    Clock {
                        id: clock
                        Layout.alignment: Qt.AlignHCenter
                        vertical: true
                        verticalWidth: root.controlSize
                        bar: root
                        layerEnabled: root.shadowsEnabled
                        startRadius: root.outerRadius
                        endRadius: root.outerRadius
                    }
                }
            }
        }
    }
}
