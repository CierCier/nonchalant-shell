pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Widgets
import qs.config
import qs.modules.bar.clock
import qs.modules.bar.systray
import qs.modules.bar.audioformat
import qs.modules.bar.workspaces
import qs.modules.components
import qs.modules.services
import qs.modules.globals
import qs.modules.theme
import qs.modules.widgets.launcher
import "../island"
import ".."

Item {
    id: root

    anchors.fill: parent
    required property ShellScreen screen
    focus: true

    Component.onCompleted: {
        root.containerY = root.shouldBeRevealed ? 0 : -(root.pillHeight + root.topMargin + 10);
        Visibilities.registerIsland(root.screen.name, root);
    }

    Component.onDestruction: {
        Visibilities.unregisterIsland(root.screen.name, root);
    }

    readonly property int pillHeight: 36
    readonly property int topMargin: 8
    readonly property int triggerHeight: 8
    readonly property real pillRadius: pillHeight / 2
    readonly property real panelRadius: Styling.radius(4)

    // Current morphing state: "collapsed" | "notification" | "osd" | "dashboard" | "power" | "sound" | "mic" | "wifi" | "stats" | "apps" | "projects"
    property string currentMode: "collapsed"
    property string previousMode: "collapsed"
    property bool openedFromHidden: false
    property bool retractingToHidden: false
    property bool snapGeometry: false
    readonly property bool isExpanded: currentMode !== "collapsed" && !retractingToHidden
    readonly property bool islandActive: isExpanded && currentMode !== "notification" && currentMode !== "osd"

    function finishRetraction() {
        if (root.retractingToHidden) {
            slideUpAnim.stop();
            retractFinishTimer.stop();
            barHoverAnim.stop();
            root.openedFromHidden = false;
            root.currentMode = "collapsed";
            root.retractingToHidden = false;
            root.containerY = -(root.pillHeight + root.topMargin + 10);
        }
    }

    function collapse() {
        if (root.currentMode === "collapsed" && !root.retractingToHidden && Visibilities.currentActiveModule === "")
            return;

        islandOsdTimer.stop();
        launcherView.cancelFocusRetry();
        root.debounceActive = false;
        exitDebounceTimer.stop();
        if (slideDownAnim.running)
            slideDownAnim.stop();
        if (barHoverAnim.running)
            barHoverAnim.stop();

        GlobalStates.clearLauncherState();
        GlobalStates.clearProjectPickerState();
        if (Visibilities.currentActiveModule !== "") {
            Visibilities.currentActiveModule = "";
        }
        Visibilities.closeActiveBarPopup();
        FocusGrabManager.clearTopGrab();

        if (root.openedFromHidden && !root.barAlwaysVisible && root.currentMode !== "collapsed") {
            root.retractingToHidden = true;
            root.forceActiveFocus();
            GlobalStates.islandOpen = false;
            GlobalStates.islandLauncherOpen = false;
            GlobalStates.islandStatsOpen = false;
            retractFinishTimer.restart();
            slideUpAnim.stop();
            slideUpAnim.from = root.containerY;
            slideUpAnim.to = -(root.targetHeight + root.topMargin + 10);
            slideUpAnim.start();
            return;
        }

        root.retractingToHidden = false;
        retractFinishTimer.stop();
        slideUpAnim.stop();
        root.openedFromHidden = false;
        root.currentMode = "collapsed";
        root.animateReveal(root.shouldBeRevealed ? 0 : -(root.pillHeight + root.topMargin + 10));
    }

    function expand(mode: string) {
        FocusGrabManager.clearTopGrab();
        Visibilities.closeActiveBarPopup();
        if (root.retractingToHidden) {
            root.retractingToHidden = false;
            retractFinishTimer.stop();
            slideUpAnim.stop();
        }
        if (barHoverAnim.running)
            barHoverAnim.stop();
        if (slideDownAnim.running)
            slideDownAnim.stop();

        const wasHidden = !root.barNormallyVisible && root.currentMode === "collapsed";
        if (root.currentMode === "collapsed") {
            root.openedFromHidden = !root.barNormallyVisible;
        }
        if (root.currentMode !== mode) {
            root.previousMode = root.currentMode;
        }
        root.snapGeometry = wasHidden;
        root.currentMode = mode || "dashboard";
        root.snapGeometry = false;
        if (wasHidden) {
            slideDownAnim.from = -(root.targetHeight + root.topMargin + 10);
            slideDownAnim.to = 0;
            slideDownAnim.start();
        } else {
            root.animateReveal(0);
        }
        if (root.currentMode === "dashboard") {
            NetworkService.update();
            BluetoothService.updateStatus();
        }
    }

    function isWindowTouchingTop(win): bool {
        if (!win)
            return false;
        if (win.floating) {
            const y = (win.at && win.at.length > 1) ? Number(win.at[1]) : 0;
            const h = (win.size && win.size.length > 1) ? Number(win.size[1]) : 0;
            return (y + h > 0) && (y <= (root.pillHeight + root.topMargin + 8));
        }
        return true;
    }

    readonly property var activeWorkspace: {
        const list = NiriService.workspaces.values;
        if (list && list.length > 0) {
            for (let i = 0; i < list.length; i++) {
                const ws = list[i];
                if (ws && (ws.output === root.screen.name || (!ws.output && Quickshell.screens.length <= 1)) && ws.active)
                    return ws;
            }
        }
        if (NiriService.focusedWorkspace && (NiriService.focusedWorkspace.output === root.screen.name || Quickshell.screens.length <= 1))
            return NiriService.focusedWorkspace;
        return null;
    }

    readonly property int activeWorkspaceWindows: {
        if (!activeWorkspace)
            return 0;
        return NiriService.windowsForWorkspace(activeWorkspace.id).length;
    }
    readonly property bool hasActiveWindows: activeWorkspaceWindows > 0
    readonly property bool hasWindowTouchingTop: {
        const ws = root.activeWorkspace;
        if (ws) {
            const windows = NiriService.windowsForWorkspace(ws.id);
            if (windows && windows.length > 0) {
                for (let i = 0; i < windows.length; i++) {
                    if (isWindowTouchingTop(windows[i]))
                        return true;
                }
                return false;
            }
        }
        if (root.screenFocusedClient && isWindowTouchingTop(root.screenFocusedClient))
            return true;
        return false;
    }
    readonly property bool hasNotifications: !Notifications.silent && Notifications.popupList && Notifications.popupList.length > 0

    onHasNotificationsChanged: {
        if (hasNotifications) {
            if (root.currentMode === "collapsed" || root.retractingToHidden) {
                root.expand("notification");
            }
        } else {
            if (root.currentMode === "notification") {
                root.collapse();
            }
        }
    }

    property string formattedTime: ""
    property string formattedDate: ""

    Timer {
        id: clockTimer
        interval: 1000
        running: !SuspendManager.isSuspending
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            const now = new Date();
            const format = Config.bar?.use12hFormat ? "hh:mm ap" : "HH:mm";
            root.formattedTime = Qt.formatTime(now, format);
            root.formattedDate = Qt.formatDate(now, "ddd d MMM");
        }
    }

    readonly property string batteryIcon: {
        let _ = Battery.percentage;
        let __ = Battery.isPluggedIn;
        let ___ = Battery.chargeState;
        return Battery.getBatteryIcon();
    }
    readonly property color batteryColor: {
        let _ = Battery.percentage;
        let __ = Battery.isPluggedIn;
        return Battery.statusColor();
    }

    readonly property bool audioMuted: Audio.sink?.audio?.muted ?? false
    readonly property real audioVolume: Audio.sink?.audio?.volume ?? 0.0

    readonly property int alertsCount: {
        if (Notifications.silent) return 0;
        let count = 0;
        const list = Notifications.appNameList;
        if (!list) return 0;
        for (let i = 0; i < list.length; i++) {
            const grp = Notifications.groupsByAppName[list[i]];
            if (grp?.notifications)
                count += grp.notifications.length;
        }
        return count;
    }

    readonly property var screenFocusedClient: {
        if (NiriService.focusedClient && (NiriService.focusedClient.output === root.screen.name || NiriService.focusedClient.monitor === root.screen.name))
            return NiriService.focusedClient;
        if (root.activeWorkspace && root.activeWorkspace.activeWindowId !== null) {
            const list = NiriService.clients.values;
            if (list) {
                const found = list.find(c => Number(c.id) === Number(root.activeWorkspace.activeWindowId));
                if (found) return found;
            }
        }
        return null;
    }

    readonly property bool isMediaPlaying: MprisController.isPlaying && MprisController.activePlayer !== null
    readonly property string contextLabel: {
        if (root.isMediaPlaying) {
            return MprisController.trackTitle || "Playing";
        }
        return root.screenFocusedClient?.title || "Desktop";
    }

    readonly property bool isHovered: revealHoverHandler.hovered && root.currentMode === "collapsed" && !root.retractingToHidden
    property bool debounceActive: false
    readonly property bool isPinned: Config.bar?.pinned ?? false

    readonly property bool barAlwaysVisible: !NiriService.overviewOpen && (root.isPinned || !hasWindowTouchingTop)
    readonly property bool barNormallyVisible: barAlwaysVisible || isHovered || debounceActive

    readonly property bool shouldBeRevealed: {
        if (root.retractingToHidden)
            return false;
        if (currentMode === "osd")
            return true;
        if (root.isExpanded)
            return true;
        return barNormallyVisible;
    }

    readonly property bool isFullyRetracted: !shouldBeRevealed && root.revealProgress <= 0.01
    readonly property bool hitboxExpanded: root.isExpanded || shouldBeRevealed || !isFullyRetracted

    property real containerY: -(pillHeight + topMargin + 10)

    NumberAnimation {
        id: slideDownAnim
        target: root
        property: "containerY"
        duration: Motion.expandDuration
        easing.type: Easing.OutBack
        easing.overshoot: Motion.overshoot
    }

    NumberAnimation {
        id: slideUpAnim
        target: root
        property: "containerY"
        duration: Motion.collapseDuration
        easing.type: Easing.InCubic
        onFinished: {
            root.finishRetraction();
        }
    }

    NumberAnimation {
        id: barHoverAnim
        target: root
        property: "containerY"
        duration: root.shouldBeRevealed ? Motion.expandDuration : Motion.collapseDuration
        easing.type: root.shouldBeRevealed ? Easing.OutBack : Easing.InCubic
        easing.overshoot: Motion.overshoot
    }

    onShouldBeRevealedChanged: {
        if (root.isExpanded || root.retractingToHidden)
            return;
        root.animateReveal(root.shouldBeRevealed ? 0 : -(root.pillHeight + root.topMargin + 10));
    }

    readonly property real revealProgress: (root.targetHeight + root.topMargin) > 0 ? Math.max(0, 1 + root.containerY / (root.targetHeight + root.topMargin)) : 0
    readonly property real revealClamped: Math.min(1, root.revealProgress)
    readonly property real contentReveal: Math.max(0, Math.min(1, (root.revealProgress - 0.4) / 0.6))

    function animateReveal(target: real) {
        barHoverAnim.stop();
        if (!Motion.enabled || Math.abs(root.containerY - target) < 0.5) {
            root.containerY = target;
            return;
        }
        barHoverAnim.from = root.containerY;
        barHoverAnim.to = target;
        barHoverAnim.start();
    }

    // Shared enter/leave choreography for every surface
    component IslandPage: Item {
        id: page

        required property bool active

        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        width: root.targetWidth
        height: root.targetHeight
        transformOrigin: Item.Top
        z: page.active ? 1 : 0
        visible: page.active || opacity > 0.001
        enabled: page.visible

        MouseArea {
            anchors.fill: parent
            enabled: !page.active || root.retractingToHidden
            z: 999
            hoverEnabled: true
            acceptedButtons: Qt.AllButtons
            onPressed: mouse => mouse.accepted = true
            onWheel: wheel => wheel.accepted = true
        }

        property real drift: page.active ? 0 : -8
        property real scaleFactor: page.active ? 1.0 : 0.94
        transform: [
            Translate {
                y: page.drift
            },
            Scale {
                origin.x: page.width / 2
                origin.y: 0
                xScale: page.scaleFactor
                yScale: page.scaleFactor
            }
        ]

        opacity: page.active ? 1.0 : 0.0

        states: [
            State {
                name: "shown"
                when: page.active && !root.retractingToHidden
                PropertyChanges {
                    target: page
                    opacity: 1.0
                    drift: 0
                    scaleFactor: 1.0
                }
            },
            State {
                name: "hidden"
                when: !page.active || root.retractingToHidden
                PropertyChanges {
                    target: page
                    opacity: 0.0
                    drift: -8
                    scaleFactor: 0.94
                }
            }
        ]

        transitions: [
            Transition {
                to: "shown"
                enabled: Motion.enabled
                SequentialAnimation {
                    PauseAnimation {
                        duration: Motion.contentEnterDelay
                    }
                    ParallelAnimation {
                        NumberAnimation {
                            property: "opacity"
                            duration: Motion.fadeInDuration
                            easing.type: Easing.OutCubic
                        }
                        NumberAnimation {
                            property: "scaleFactor"
                            duration: Motion.fadeInDuration
                            easing.type: Easing.OutBack
                            easing.overshoot: 1.15
                        }
                        NumberAnimation {
                            property: "drift"
                            duration: Motion.fadeInDuration
                            easing.type: Easing.OutCubic
                        }
                    }
                }
            },
            Transition {
                from: "shown"
                enabled: Motion.enabled
                NumberAnimation {
                    properties: "opacity,scaleFactor,drift"
                    duration: Motion.fadeOutDuration
                    easing.type: Easing.OutQuad
                }
            }
        ]
    }

    readonly property int targetWidth: {
        if (root.isExpanded || root.retractingToHidden) {
            if (root.currentMode === "osd") {
                return Math.min(300, root.width - 32);
            }
            if (root.currentMode === "wallpapers") {
                return Math.min(540, root.width - 32);
            }
            return Math.min(420, root.width - 32);
        }
        return Math.min(Math.max(pillsRow.implicitWidth, 200), Math.max(200, root.width - 32));
    }

    readonly property int targetHeight: {
        switch (root.currentMode) {
        case "osd":
            return osdView.implicitHeight;
        case "notification":
            return (notificationView.implicitHeight > 0) ? notificationView.implicitHeight : root.pillHeight;
        case "dashboard":
            return dashboardView.implicitHeight;
        case "power":
            return powerView.implicitHeight;
        case "sound":
            return soundView.implicitHeight;
        case "mic":
            return micView.implicitHeight;
        case "wifi":
            return wifiView.implicitHeight;
        case "bluetooth":
            return bluetoothView.implicitHeight;
        case "stats":
            return statsView.implicitHeight;
        case "alerts":
            return alertsView.implicitHeight;
        case "wallpapers":
            return wallpapersView.implicitHeight;
        case "battery":
            return batteryView.implicitHeight;
        case "weather":
            return weatherView.implicitHeight;
        case "media":
            return mediaCenterView.implicitHeight;
        case "calendar":
            return calendarView.implicitHeight;
        case "apps":
        case "projects":
            return launcherViewWrapper.implicitHeight;
        default:
            return root.pillHeight;
        }
    }

    onCurrentModeChanged: {
        FocusGrabManager.clearTopGrab();
        Visibilities.closeActiveBarPopup();
        GlobalStates.islandOpen = (currentMode !== "collapsed" && currentMode !== "notification" && currentMode !== "osd" && !root.retractingToHidden);
        GlobalStates.islandLauncherOpen = ((currentMode === "apps" || currentMode === "projects") && !root.retractingToHidden);
        GlobalStates.islandStatsOpen = (currentMode === "stats" && !root.retractingToHidden);

        if (root.previousMode === "collapsed" && root.currentMode !== "collapsed") {
            root.openedFromHidden = !root.barAlwaysVisible;
        }
        root.previousMode = root.currentMode;

        if (currentMode === "apps" || currentMode === "projects") {
            GlobalStates.launcherMode = currentMode;
            launcherView.focusSearchInput();
        } else if (currentMode !== "collapsed" && currentMode !== "notification" && currentMode !== "osd") {
            launcherView.cancelFocusRetry();
            Qt.callLater(() => {
                root.forceActiveFocus();
            });
        } else if (currentMode === "collapsed" && root.hasNotifications) {
            Qt.callLater(() => {
                if (root.currentMode === "collapsed" && root.hasNotifications) {
                    root.openedFromHidden = !root.barAlwaysVisible;
                    root.currentMode = "notification";
                }
            });
        }
    }

    Connections {
        target: GlobalStates
        function onLauncherModeChanged() {
            const inLauncher = root.currentMode === "apps" || root.currentMode === "projects";
            if (inLauncher && root.currentMode !== GlobalStates.launcherMode)
                root.expand(GlobalStates.launcherMode);
        }
    }

    Connections {
        target: Notifications
        function onSilentChanged() {
            if (Notifications.silent && root.currentMode === "notification") {
                root.collapse();
            }
        }
    }

    // OSD Morphing State & Connections
    property string osdIndicator: "volume"
    property real osdValue: 0.0
    property bool osdMuted: false

    Timer {
        id: islandOsdTimer
        interval: 2200
        repeat: false
        onTriggered: {
            if (root.currentMode === "osd") {
                root.collapse();
            }
        }
    }

    Timer {
        id: retractFinishTimer
        interval: Motion.collapseDuration + 60
        repeat: false
        onTriggered: {
            root.finishRetraction();
        }
    }

    function triggerOsd(indicator: string, value: real, muted: bool) {
        root.osdIndicator = indicator;
        root.osdValue = value;
        root.osdMuted = muted;
        if (root.currentMode === "collapsed" || root.currentMode === "osd") {
            if (root.currentMode === "collapsed") {
                root.expand("osd");
            } else if (root.retractingToHidden) {
                root.retractingToHidden = false;
                retractFinishTimer.stop();
                slideUpAnim.stop();
                root.animateReveal(0);
            }
            islandOsdTimer.restart();
        }
    }

    Connections {
        target: Audio
        function onVolumeChanged(volume, muted, node) {
            root.triggerOsd("volume", volume, muted);
        }
        function onMicVolumeChanged(volume, muted, node) {
            root.triggerOsd("mic", volume, muted);
        }
    }

    Connections {
        target: Brightness
        function onBrightnessChanged(value, screen) {
            if (!screen || !root.screen || screen.name === root.screen.name || Brightness.syncBrightness) {
                root.triggerOsd("brightness", value, false);
            }
        }
    }

    // Contract properties for BarContent & UnifiedShellPanel
    readonly property int barTargetHeight: pillHeight
    readonly property int baseOuterMargin: topMargin
    readonly property int totalBarHeight: pillHeight + topMargin
    readonly property bool timerInputActive: false
    readonly property bool dashboardInputActive: islandActive && currentMode === "dashboard"

    property alias barHitbox: activeBarHitbox
    readonly property Item dropHitbox: null

    Item {
        id: dummyDashboardHitbox
        width: 0
        height: 0
        visible: false
    }
    readonly property Item dashboardHitbox: dummyDashboardHitbox

    Timer {
        id: exitDebounceTimer
        interval: 200
        repeat: false
        onTriggered: {
            root.debounceActive = false;
        }
    }

    onIsHoveredChanged: {
        if (isHovered) {
            exitDebounceTimer.stop();
            root.debounceActive = false;
        } else if (root.hasWindowTouchingTop && !root.isExpanded && !root.isPinned && !root.retractingToHidden) {
            root.debounceActive = true;
            exitDebounceTimer.restart();
        }
    }

    // Keyboard handling when expanded
    Keys.onPressed: event => {
        if (root.retractingToHidden) {
            event.accepted = true;
            return;
        }
        if (root.currentMode === "power") {
            if (event.key === Qt.Key_Left) {
                powerView.moveSelection(-1);
                event.accepted = true;
            } else if (event.key === Qt.Key_Right) {
                powerView.moveSelection(1);
                event.accepted = true;
            } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                powerView.activateSelected();
                event.accepted = true;
            } else if (event.key === Qt.Key_Escape) {
                root.expand("dashboard");
                event.accepted = true;
            }
        } else if (event.key === Qt.Key_Escape) {
            if (Visibilities.activeBarPopup && Visibilities.activeBarPopup.isOpen) {
                Visibilities.closeActiveBarPopup();
                event.accepted = true;
                return;
            }
            if (root.currentMode === "apps" || root.currentMode === "projects") {
                root.collapse();
            } else if (root.currentMode === "notification") {
                notificationView.dismissCurrent();
            } else if (root.currentMode !== "dashboard" && root.currentMode !== "collapsed") {
                root.expand("dashboard");
            } else {
                root.collapse();
            }
            event.accepted = true;
        }
    }

    // Wayland input mask hitbox
    Item {
        id: activeBarHitbox
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.topMargin + Math.max(0, root.containerY)
        width: pillsContainer.width
        height: root.isExpanded ? pillsContainer.height : (root.hitboxExpanded ? pillsContainer.height : root.triggerHeight)
    }

    // ═════════════════════════════════════════════════════════════════
    // FLOATING MASTER CONTAINER (Fluid Morphing Geometry)
    // ═════════════════════════════════════════════════════════════════
    Item {
        id: pillsContainer
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.topMargin + root.containerY
        width: root.targetWidth
        height: root.targetHeight
        visible: root.revealProgress > 0.001

        Behavior on width {
            enabled: Motion.enabled && (root.shouldBeRevealed || root.isExpanded) && !root.retractingToHidden && !root.snapGeometry
            NumberAnimation {
                duration: root.isExpanded ? Motion.expandDuration : Motion.collapseDuration
                easing.type: root.isExpanded ? Easing.OutBack : Easing.OutCubic
                easing.overshoot: Motion.overshoot
            }
        }

        Behavior on height {
            enabled: Motion.enabled && (root.shouldBeRevealed || root.isExpanded) && !root.retractingToHidden && !root.snapGeometry
            NumberAnimation {
                duration: root.isExpanded ? Motion.expandDuration : Motion.collapseDuration
                easing.type: root.isExpanded ? Easing.OutBack : Easing.OutCubic
                easing.overshoot: Motion.overshoot
            }
        }

        // ═════════════════════════════════════════════════════════════
        // COLLAPSED BAR STATE: SEPARATE FLOATING PILLS
        // ═════════════════════════════════════════════════════════════
        Item {
            id: collapsedPillsLayer
            anchors.centerIn: parent
            width: pillsRow.implicitWidth
            height: root.pillHeight
            visible: opacity > 0.001
            opacity: root.isExpanded ? 0.0 : root.contentReveal

            Behavior on opacity {
                enabled: Motion.enabled
                NumberAnimation {
                    duration: root.isExpanded ? Motion.fadeOutDuration : Motion.fadeInDuration
                    easing.type: Easing.OutCubic
                }
            }

            RowLayout {
                id: pillsRow
                anchors.centerIn: parent
                spacing: 8

                // ── PILL 1: WORKSPACES & APP LAUNCHER PILL ──
                StyledRect {
                    id: workspacesPill
                    implicitHeight: root.pillHeight
                    implicitWidth: workspacesRow.implicitWidth + 12
                    variant: "pane"
                    radius: root.pillRadius
                    enableBorder: true
                    enableShadow: true
                    backgroundOpacity: 1.0

                    RowLayout {
                        id: workspacesRow
                        anchors.centerIn: parent
                        spacing: 4

                        // App Launcher trigger button
                        Item {
                            implicitWidth: 26
                            implicitHeight: 26
                            Layout.alignment: Qt.AlignVCenter
                            scale: launcherMouse.pressed ? 0.92 : 1.0

                            PressBehavior on scale {
                                pressed: launcherMouse.pressed
                            }

                            StyledRect {
                                anchors.fill: parent
                                radius: 13
                                variant: launcherMouse.containsMouse ? "focus" : "transparent"

                                Text {
                                    anchors.centerIn: parent
                                    text: Icons.gear
                                    font.family: Icons.font
                                    font.pixelSize: 14
                                    color: launcherMouse.containsMouse ? Colors.primary : Colors.overBackground
                                    renderType: Text.NativeRendering
                                }
                            }

                            MouseArea {
                                id: launcherMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.expand("apps")
                            }

                            StyledToolTip {
                                show: launcherMouse.containsMouse
                                tooltipText: "Applications"
                                description: "Click to launch apps and switch projects"
                            }
                        }

                        // Workspaces switcher
                        NonchalantTaskbar {
                            Layout.alignment: Qt.AlignVCenter
                            bar: root
                            showBackground: false
                        }
                    }
                }

                // ── PILL 2: CONTEXT / WINDOW TITLE / MEDIA PILL ──
                StyledRect {
                    id: contextPill
                    implicitHeight: root.pillHeight
                    implicitWidth: Math.min(contextContentRow.implicitWidth + 24, 260)
                    variant: "pane"
                    radius: root.pillRadius
                    enableBorder: true
                    enableShadow: true
                    backgroundOpacity: 1.0
                    scale: contextMouse.pressed ? 0.94 : 1.0

                    PressBehavior on scale {
                        pressed: contextMouse.pressed
                    }

                    RowLayout {
                        id: contextContentRow
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        spacing: 6

                        Text {
                            visible: root.isMediaPlaying
                            text: Icons.player
                            font.family: Icons.font
                            font.pixelSize: 13
                            color: Colors.primary
                            renderType: Text.NativeRendering
                            Layout.alignment: Qt.AlignVCenter
                        }

                        FluidTextProgress {
                            id: fluidContextText
                            Layout.fillWidth: true
                            implicitHeight: 20
                            Layout.alignment: Qt.AlignVCenter
                            text: root.contextLabel
                            fontFamily: Config.theme.font
                            pixelSize: Styling.fontSize(-1)
                            bold: true
                            elide: Text.ElideRight
                            verticalAlignment: Text.AlignVCenter
                            progress: (root.isMediaPlaying && MprisController.length > 0) ? MprisController.progress : 0.0
                            isPlaying: root.isMediaPlaying
                            baseColor: Colors.overBackground
                            fillColor: Colors.primary
                            highlightColor: Colors.primaryFixed ?? Colors.primary
                        }
                    }

                    MouseArea {
                        id: contextMouse
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        hoverEnabled: true
                        onClicked: {
                            if (root.isMediaPlaying)
                                root.expand("media");
                            else
                                root.expand("apps");
                        }
                    }

                    StyledToolTip {
                        show: contextMouse.containsMouse
                        tooltipText: root.isMediaPlaying ? "Now Playing: " + root.contextLabel : (root.screenFocusedClient?.title || "Active Window")
                        description: root.isMediaPlaying ? "Click to open Media Center" : "Click to search applications"
                    }
                }

                // ── PILL 3: CLOCK & DATE PILL ──
                StyledRect {
                    id: clockPill
                    implicitHeight: root.pillHeight
                    implicitWidth: clockContentRow.implicitWidth + 24
                    variant: "pane"
                    radius: root.pillRadius
                    enableBorder: true
                    enableShadow: true
                    backgroundOpacity: 1.0
                    scale: clockMouse.pressed ? 0.94 : 1.0

                    PressBehavior on scale {
                        pressed: clockMouse.pressed
                    }

                    RowLayout {
                        id: clockContentRow
                        anchors.centerIn: parent
                        spacing: 8

                        Text {
                            text: root.formattedTime
                            font.family: Config.theme.monoFont
                            font.pixelSize: Styling.fontSize(-1)
                            font.bold: true
                            color: clockMouse.containsMouse ? Colors.primary : Colors.overBackground
                            renderType: Text.NativeRendering
                        }

                        Text {
                            text: root.formattedDate
                            font.family: Config.theme.font
                            font.pixelSize: Styling.fontSize(-1)
                            color: Colors.overSurfaceVariant
                            renderType: Text.NativeRendering
                        }
                    }

                    MouseArea {
                        id: clockMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        cursorShape: Qt.PointingHandCursor
                        onClicked: mouse => {
                            if (mouse.button === Qt.RightButton) {
                                root.expand("calendar");
                            } else {
                                root.expand("dashboard");
                            }
                        }
                    }

                    StyledToolTip {
                        show: clockMouse.containsMouse
                        tooltipText: "Left-click: Dashboard • Right-click: Calendar"
                    }
                }

                // ── PILL 4: STATUS & INDICATORS PILL ──
                StyledRect {
                    id: statusPill
                    implicitHeight: root.pillHeight
                    implicitWidth: statusPillRow.implicitWidth + 14
                    variant: "pane"
                    radius: root.pillRadius
                    enableBorder: true
                    enableShadow: true
                    backgroundOpacity: 1.0

                    RowLayout {
                        id: statusPillRow
                        anchors.centerIn: parent
                        spacing: 4

                        // Audio format badge (bt / usb / wired headphones)
                        AudioFormatBadge {
                            enableShadow: false
                            startRadius: root.pillRadius
                            endRadius: root.pillRadius
                        }

                        // Dynamic Status Icons (Brightness, Volume, Battery)
                        IslandStatusIcons {
                            bar: root
                        }

                        // Wi-Fi / Network indicator button
                        Item {
                            implicitWidth: 24
                            implicitHeight: 24
                            Layout.alignment: Qt.AlignVCenter
                            scale: wifiMouse.pressed ? 0.92 : 1.0

                            PressBehavior on scale {
                                pressed: wifiMouse.pressed
                            }

                            StyledRect {
                                anchors.fill: parent
                                radius: 12
                                variant: wifiMouse.containsMouse ? "focus" : "transparent"

                                Text {
                                    anchors.centerIn: parent
                                    text: NetworkService.wifiEnabled
                                        ? (NetworkService.wifiConnected ? Icons.wifiHigh : Icons.wifiLow)
                                        : Icons.ethernet
                                    font.family: Icons.font
                                    font.pixelSize: 13
                                    color: NetworkService.wifiConnected
                                        ? (wifiMouse.containsMouse ? Colors.primary : Colors.overBackground)
                                        : Colors.overSurfaceVariant
                                    renderType: Text.NativeRendering
                                }
                            }

                            MouseArea {
                                id: wifiMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.expand("wifi")
                            }

                            StyledToolTip {
                                show: wifiMouse.containsMouse
                                tooltipText: NetworkService.wifiConnected
                                    ? ("Wi-Fi: " + (NetworkService.activeSsid || "Connected"))
                                    : "Wi-Fi Networks"
                            }
                        }

                        // Bluetooth indicator button
                        Item {
                            implicitWidth: 24
                            implicitHeight: 24
                            Layout.alignment: Qt.AlignVCenter
                            scale: btMouse.pressed ? 0.92 : 1.0

                            PressBehavior on scale {
                                pressed: btMouse.pressed
                            }

                            StyledRect {
                                anchors.fill: parent
                                radius: 12
                                variant: btMouse.containsMouse ? "focus" : "transparent"

                                Text {
                                    anchors.centerIn: parent
                                    text: BluetoothService.connected
                                        ? Icons.bluetoothConnected
                                        : (BluetoothService.enabled ? Icons.bluetooth : Icons.bluetoothOff)
                                    font.family: Icons.font
                                    font.pixelSize: 13
                                    color: BluetoothService.enabled
                                        ? (btMouse.containsMouse ? Colors.primary : Colors.overBackground)
                                        : Colors.overSurfaceVariant
                                    renderType: Text.NativeRendering
                                }
                            }

                            MouseArea {
                                id: btMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.expand("bluetooth")
                            }

                            StyledToolTip {
                                show: btMouse.containsMouse
                                tooltipText: BluetoothService.connected ? "Bluetooth: Connected" : (BluetoothService.enabled ? "Bluetooth: On" : "Bluetooth: Off")
                            }
                        }

                        // Alerts bell icon (if notifications active)
                        Item {
                            visible: !Notifications.silent && (root.alertsCount > 0 || root.hasNotifications)
                            implicitWidth: 24
                            implicitHeight: 24
                            Layout.alignment: Qt.AlignVCenter
                            scale: alertsMouse.pressed ? 0.92 : 1.0

                            PressBehavior on scale {
                                pressed: alertsMouse.pressed
                            }

                            StyledRect {
                                anchors.fill: parent
                                radius: 12
                                variant: alertsMouse.containsMouse ? "focus" : "transparent"

                                RowLayout {
                                    anchors.centerIn: parent
                                    spacing: 2

                                    Text {
                                        text: Icons.bell
                                        font.family: Icons.font
                                        font.pixelSize: 12
                                        color: Colors.primary
                                        renderType: Text.NativeRendering
                                    }

                                    Text {
                                        text: String(root.alertsCount)
                                        font.family: Config.theme.monoFont
                                        font.pixelSize: Styling.fontSize(-3)
                                        font.bold: true
                                        color: Colors.primary
                                        renderType: Text.NativeRendering
                                    }
                                }
                            }

                            MouseArea {
                                id: alertsMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.expand("alerts")
                            }

                            StyledToolTip {
                                show: alertsMouse.containsMouse
                                tooltipText: root.alertsCount + " notification" + (root.alertsCount === 1 ? "" : "s")
                            }
                        }

                        // Pin toggle button
                        Item {
                            implicitWidth: 22
                            implicitHeight: 22
                            Layout.alignment: Qt.AlignVCenter

                            StyledRect {
                                anchors.fill: parent
                                radius: 11
                                variant: pinMouse.containsMouse ? "focus" : "transparent"
                                scale: pinMouse.pressed ? 0.92 : 1.0

                                PressBehavior on scale {
                                    pressed: pinMouse.pressed
                                }

                                Text {
                                    anchors.centerIn: parent
                                    text: root.isPinned ? Icons.pin : Icons.unpin
                                    font.family: Icons.font
                                    font.pixelSize: 13
                                    color: root.isPinned ? Colors.primary : (pinMouse.containsMouse ? Colors.primary : Colors.overBackground)
                                    opacity: root.isPinned ? 1.0 : (pinMouse.containsMouse ? 1.0 : 0.7)
                                    renderType: Text.NativeRendering
                                }
                            }

                            MouseArea {
                                id: pinMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (Config.bar) {
                                        Config.bar.pinned = !root.isPinned;
                                    }
                                }
                            }

                            StyledToolTip {
                                show: pinMouse.containsMouse
                                tooltipText: root.isPinned ? "Unpin Bar" : "Pin Bar"
                                description: root.isPinned ? "Autohide disabled (reserves window space)" : "Keep floating bar visible and reserve window space"
                            }
                        }
                    }
                }
            }
        }

        // ═════════════════════════════════════════════════════════════
        // EXPANDED STATE: UNIFIED FLOATING CARD
        // ═════════════════════════════════════════════════════════════
        StyledRect {
            id: expandedCard
            anchors.fill: parent
            variant: "pane"
            radius: root.panelRadius
            enableBorder: true
            enableShadow: true
            backgroundOpacity: 1.0
            clip: true
            visible: opacity > 0.001
            opacity: root.isExpanded ? root.contentReveal : 0.0

            Behavior on opacity {
                enabled: Motion.enabled
                NumberAnimation {
                    duration: root.isExpanded ? Motion.fadeInDuration : Motion.fadeOutDuration
                    easing.type: Easing.OutCubic
                }
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    FocusGrabManager.clearTopGrab();
                    Visibilities.closeActiveBarPopup();
                }
            }

            Item {
                id: pageLayer
                anchors.fill: parent

                // ── OSD BANNER (Volume / Brightness / Mic) ──
                IslandPage {
                    active: root.currentMode === "osd"

                    IslandOsdBanner {
                        id: osdView
                        bar: root
                        width: parent.width
                        indicator: root.osdIndicator
                        value: root.osdValue
                        muted: root.osdMuted
                    }
                }

                // ── NOTIFICATION BANNER ──
                IslandPage {
                    active: !Notifications.silent && root.currentMode === "notification" && root.hasNotifications && notificationView.activeNotif !== null

                    IslandNotificationBanner {
                        id: notificationView
                        width: parent.width

                        onDismissRequested: {
                            root.collapse();
                        }
                    }
                }

                // ── MAIN DASHBOARD HUB ──
                IslandPage {
                    active: root.currentMode === "dashboard"

                    IslandDashboard {
                        id: dashboardView
                        screen: root.screen
                        width: parent.width
                        lyricsActive: root.currentMode === "dashboard" && !root.retractingToHidden
                        height: implicitHeight

                        onOpenPower: root.expand("power")
                        onOpenSound: root.expand("sound")
                        onOpenMic: root.expand("mic")
                        onOpenWifi: root.expand("wifi")
                        onOpenBluetooth: root.expand("bluetooth")
                        onOpenStats: root.expand("stats")
                        onOpenAlerts: root.expand("alerts")
                        onOpenWallpapers: root.expand("wallpapers")
                        onOpenBattery: root.expand("battery")
                        onOpenWeather: root.expand("weather")
                        onOpenMedia: root.expand("media")
                        onOpenCalendar: root.expand("calendar")
                    }
                }

                // ── POWER MENU ──
                IslandPage {
                    active: root.currentMode === "power"

                    IslandPowerPanel {
                        id: powerView
                        width: parent.width
                        height: implicitHeight

                        onBackRequested: root.expand("dashboard")
                        onActionTriggered: root.collapse()
                    }
                }

                // ── SOUND PANEL ──
                IslandPage {
                    active: root.currentMode === "sound"

                    IslandSoundPanel {
                        id: soundView
                        width: parent.width
                        height: implicitHeight

                        onBackRequested: root.expand("dashboard")
                    }
                }

                // ── MICROPHONE PANEL ──
                IslandPage {
                    active: root.currentMode === "mic"

                    IslandMicPanel {
                        id: micView
                        width: parent.width
                        height: implicitHeight

                        onBackRequested: root.expand("dashboard")
                    }
                }

                // ── WI-FI NETWORKS PANEL ──
                IslandPage {
                    active: root.currentMode === "wifi"

                    IslandWifiPanel {
                        id: wifiView
                        width: parent.width
                        height: implicitHeight

                        onBackRequested: root.expand("dashboard")
                    }
                }

                // ── BLUETOOTH PANEL ──
                IslandPage {
                    active: root.currentMode === "bluetooth"

                    IslandBluetoothPanel {
                        id: bluetoothView
                        width: parent.width
                        height: implicitHeight

                        onBackRequested: root.expand("dashboard")
                    }
                }

                // ── SYSTEM STATS PANEL ──
                IslandPage {
                    active: root.currentMode === "stats"

                    IslandStatsPanel {
                        id: statsView
                        width: parent.width
                        height: implicitHeight

                        onBackRequested: root.expand("dashboard")
                    }
                }

                // ── ALERTS PANEL ──
                IslandPage {
                    active: root.currentMode === "alerts"

                    IslandAlertsPanel {
                        id: alertsView
                        width: parent.width
                        height: implicitHeight

                        onBackRequested: root.expand("dashboard")
                    }
                }

                // ── WALLPAPERS PANEL ──
                IslandPage {
                    active: root.currentMode === "wallpapers"

                    IslandWallpaperPanel {
                        id: wallpapersView
                        screen: root.screen
                        width: parent.width
                        height: implicitHeight

                        onBackRequested: root.expand("dashboard")
                    }
                }

                // ── BATTERY PANEL ──
                IslandPage {
                    active: root.currentMode === "battery"

                    IslandBatteryPanel {
                        id: batteryView
                        width: parent.width
                        height: implicitHeight

                        onBackRequested: root.expand("dashboard")
                    }
                }

                // ── WEATHER PANEL ──
                IslandPage {
                    active: root.currentMode === "weather"

                    IslandWeatherPanel {
                        id: weatherView
                        width: parent.width
                        height: implicitHeight

                        onBackRequested: root.expand("dashboard")
                    }
                }

                // ── MEDIA CENTER PANEL ──
                IslandPage {
                    active: root.currentMode === "media"

                    IslandMediaCenterPanel {
                        id: mediaCenterView
                        width: parent.width
                        maximumHeight: Math.max(0, root.screen.height - 32)
                        lyricsActive: root.currentMode === "media" && !root.retractingToHidden
                        height: implicitHeight

                        onBackRequested: root.expand("dashboard")
                    }
                }

                // ── CALENDAR PANEL ──
                IslandPage {
                    active: root.currentMode === "calendar"

                    IslandCalendarPanel {
                        id: calendarView
                        width: parent.width
                        height: implicitHeight

                        onBackRequested: root.expand("dashboard")
                    }
                }

                // ── APPS & PROJECTS LAUNCHER ──
                IslandPage {
                    active: root.currentMode === "apps" || root.currentMode === "projects"

                    Item {
                        id: launcherViewWrapper
                        width: parent.width
                        height: implicitHeight
                        implicitHeight: launcherView.implicitHeight + 16

                        LauncherView {
                            id: launcherView
                            anchors.fill: parent
                            anchors.margins: 8
                        }
                    }
                }
            }
        }
    }

    // Single hover zone for the autohide reveal
    Item {
        id: hoverZone
        anchors.horizontalCenter: parent.horizontalCenter
        y: 0
        z: 1000
        width: Math.max(200, pillsContainer.width)
        height: Math.max(root.triggerHeight, pillsContainer.height + root.topMargin)

        HoverHandler {
            id: revealHoverHandler
            blocking: false
        }
    }
}
