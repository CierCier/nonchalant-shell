pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import qs.modules.components
import qs.modules.theme
import qs.modules.bar.island
import qs.modules.services

Item {
    id: root

    property string screenName: ""
    signal closeRequested()
    implicitWidth: 680
    implicitHeight: dashboardColumn.implicitHeight

    function focusCurrentTab(): void {
        dashboard.focusCurrentTab();
    }

    ColumnLayout {
        id: dashboardColumn
        anchors.fill: parent
        spacing: 8

        IslandMediaCard {
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            onExpandRequested: GlobalShortcuts.run("media")
        }

        StyledRect {
            variant: "popup"
            radius: Styling.radius(4)
            Layout.fillWidth: true
            Layout.fillHeight: true
            implicitHeight: dashboard.implicitHeight + 16
            Layout.preferredHeight: implicitHeight

            DashboardView {
                id: dashboard
                anchors.fill: parent
                anchors.margins: 8
                screenName: root.screenName
                popupMode: true
                onCloseRequested: root.closeRequested()
            }
        }
    }
}
