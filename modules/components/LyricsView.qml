pragma ComponentBehavior: Bound

import QtQuick
import qs.config
import qs.modules.services
import qs.modules.theme

Item {
    id: root

    property string mode: "compact"
    property bool lyricsEnabled: Config.bar?.lyricsEnabled ?? true
    property bool active: false
    property bool subscribed: false
    property bool collapseWhenEmpty: false
    readonly property bool hasLyrics: root.hasTrack && root.lyricsEnabled
        && LyricsService.available && !LyricsService.instrumental && LyricsService.lines.length > 0
    visible: !root.collapseWhenEmpty || root.hasLyrics
    clip: root.mode === "compact"

    implicitHeight: root.mode === "detail" ? 140 : 22
    readonly property bool shouldRender: root.active && root.visible
        && root.width > 0 && root.height > 0
    // Empty media views still request lyrics while their owning panel is open.
    readonly property bool shouldSubscribe: root.active && root.lyricsEnabled
        && (root.collapseWhenEmpty || root.shouldRender)

    readonly property bool hasTrack: MprisController.activePlayer !== null
        && MprisController.trackTitle.trim() !== ""
    readonly property string statusText: {
        if (!root.lyricsEnabled)
            return "Lyrics are off";
        if (!root.hasTrack)
            return "Nothing playing";
        switch (LyricsService.status) {
        case "loading": return "Looking for lyrics";
        case "network": return "Network unavailable · retrying";
        case "missing": return "No lyrics for this track";
        case "instrumental": return "Instrumental";
        case "plain": return "Lyrics, untimed";
        case "timed": return "";
        default: return "Looking for lyrics";
        }
    }
    readonly property string compactText: {
        if (!root.lyricsEnabled || !root.hasTrack || !LyricsService.available)
            return root.statusText;
        if (LyricsService.instrumental)
            return "Instrumental";
        if (LyricsService.synced)
            return LyricsService.currentText || "♪";
        return "Lyrics, untimed";
    }

    function escapeText(text: string): string {
        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // TTML word ranges retain original spacing, including unspaced scripts and syllables.
    function timedText(index: int): string {
        const line = LyricsService.lines[index];
        if (!line || !line.words?.length)
            return line?.text || "♪";
        const position = LyricsService.playbackPosition;
        let text = "";
        let offset = 0;
        for (const word of line.words) {
            text += root.escapeText(line.text.slice(offset, word.start));
            const fragment = root.escapeText(line.text.slice(word.start, word.start + word.length));
            if (position >= word.t && position < word.end)
                text += '<font color="' + Colors.primary + '"><u>' + fragment + '</u></font>';
            else if (position >= word.end)
                text += '<font color="' + Colors.primary + '">' + fragment + '</font>';
            else
                text += '<font color="' + Colors.overSurfaceVariant + '">' + fragment + '</font>';
            offset = word.start + word.length;
        }
        return text + root.escapeText(line.text.slice(offset));
    }

    function syncSubscription(): void {
        if (root.shouldSubscribe === root.subscribed)
            return;
        root.subscribed = root.shouldSubscribe;
        if (root.subscribed)
            LyricsService.subscribe();
        else
            LyricsService.release();
    }

    onShouldSubscribeChanged: root.syncSubscription()
    Component.onCompleted: root.syncSubscription()
    Component.onDestruction: {
        if (root.subscribed)
            LyricsService.release();
    }

    FontMetrics {
        id: compactFontMetrics
        font: compactLine.font
    }

    Text {
        id: compactLine
        anchors.verticalCenter: parent.verticalCenter
        width: wordTimed ? Math.max(root.width, compactFontMetrics.advanceWidth(root.compactText)) : root.width
        height: root.height
        visible: root.shouldRender && root.mode === "compact"
        readonly property bool wordTimed: root.shouldRender && root.mode === "compact"
            && root.lyricsEnabled && LyricsService.available && LyricsService.synced
            && (LyricsService.lines[LyricsService.current]?.words?.length ?? 0) > 0
        text: wordTimed ? root.timedText(LyricsService.current) : root.compactText
        textFormat: wordTimed ? Text.StyledText : Text.PlainText
        Accessible.name: root.compactText
        x: {
            if (!compactLine.wordTimed || width <= root.width)
                return 0;
            const words = LyricsService.lines[LyricsService.current].words;
            const position = LyricsService.playbackPosition;
            let character = words[0].start;
            for (const word of words) {
                if (word.t <= position)
                    character = word.start + Math.floor(word.length / 2);
            }
            const prefix = LyricsService.lines[LyricsService.current].text.slice(0, character);
            return Math.max(root.width - width,
                Math.min(0, root.width / 2 - compactFontMetrics.advanceWidth(prefix)));
        }
        Behavior on x {
            NumberAnimation { duration: Config.animDuration; easing.type: Easing.OutQuad }
        }
        color: root.lyricsEnabled && LyricsService.available && LyricsService.synced
            && LyricsService.current >= 0 ? Colors.primary : Colors.overSurfaceVariant
        font.family: Config.theme.font
        font.pixelSize: Styling.fontSize(-1)
        font.weight: Font.DemiBold
        wrapMode: Text.NoWrap
        elide: wordTimed ? Text.ElideNone : Text.ElideRight
        horizontalAlignment: wordTimed && width > root.width ? Text.AlignLeft : Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    Text {
        anchors.centerIn: parent
        width: parent.width
        visible: root.shouldRender && root.mode === "detail"
            && (!root.lyricsEnabled || !LyricsService.available || LyricsService.instrumental)
        text: root.statusText
        color: Colors.overSurfaceVariant
        font.family: Config.theme.font
        font.pixelSize: Styling.fontSize(1)
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        wrapMode: Text.Wrap
    }

    FontMetrics {
        id: lyricFontMetrics
        font.family: Config.theme.font
        font.pixelSize: Styling.fontSize(1)
        font.weight: Font.DemiBold
    }

    ListView {
        id: lyricLines
        anchors.fill: parent
        visible: root.shouldRender && root.mode === "detail" && root.lyricsEnabled
            && LyricsService.available && !LyricsService.instrumental
        clip: true
        model: visible ? LyricsService.lines : []
        spacing: 8
        interactive: !LyricsService.synced
        currentIndex: visible && LyricsService.synced && count > 0
            ? Math.min(LyricsService.current, count - 1) : -1
        highlightRangeMode: LyricsService.synced
            ? ListView.StrictlyEnforceRange : ListView.NoHighlightRange
        // Strict range enforcement can change currentItem; do not size the range from it.
        preferredHighlightBegin: Math.max(0, (height - lyricFontMetrics.height) / 2)
        preferredHighlightEnd: Math.min(height,
            preferredHighlightBegin + lyricFontMetrics.height)
        highlightMoveDuration: Config.animDuration
        highlightFollowsCurrentItem: true
        header: Item {
            width: 1
            height: LyricsService.synced ? 0 : lyricLines.height / 3
        }
        footer: Item {
            width: 1
            height: lyricLines.height / 3
        }

        delegate: Item {
            id: lyricLine
            required property var modelData
            required property int index

            readonly property bool seekable: LyricsService.synced
                && (MprisController.activePlayer?.canSeek ?? false)
                && Number(lyricLine.modelData.t) >= 0

            activeFocusOnTab: seekable
            Accessible.role: seekable ? Accessible.Button : Accessible.StaticText
            Accessible.name: lyricLine.modelData.text
            Accessible.description: seekable ? "Seek to this lyric" : ""
            Accessible.onPressAction: {
                if (lyricLine.seekable)
                    LyricsService.seekTo(Number(lyricLine.modelData.t));
            }
            Keys.onReturnPressed: event => {
                if (lyricLine.seekable) {
                    LyricsService.seekTo(Number(lyricLine.modelData.t));
                    event.accepted = true;
                }
            }
            Keys.onSpacePressed: event => {
                if (lyricLine.seekable) {
                    LyricsService.seekTo(Number(lyricLine.modelData.t));
                    event.accepted = true;
                }
            }
            readonly property int distance: LyricsService.current < 0
                ? lyricLine.index + 1
                : Math.abs(lyricLine.index - LyricsService.current)

            width: lyricLines.width
            implicitHeight: lineText.implicitHeight

            Text {
                id: lineText
                anchors.fill: parent
                readonly property bool wordTimed: lyricLine.distance === 0
                    && (lyricLine.modelData.words?.length ?? 0) > 0
                text: wordTimed ? root.timedText(lyricLine.index)
                    : (lyricLine.modelData.text !== "" ? lyricLine.modelData.text : "♪")
                textFormat: wordTimed ? Text.StyledText : Text.PlainText
                color: lyricLine.distance === 0 ? Colors.primary : Colors.overBackground
                opacity: !LyricsService.synced || lyricLine.distance === 0
                    ? 1 : Math.max(0.24, 0.56 - 0.1 * lyricLine.distance)
                font.family: Config.theme.font
                font.pixelSize: Styling.fontSize(1)
                font.weight: Font.DemiBold
                font.underline: lyricLine.activeFocus
                wrapMode: Text.Wrap
                horizontalAlignment: Text.AlignHCenter
            }

            MouseArea {
                anchors.fill: parent
                enabled: lyricLine.seekable
                cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                onClicked: {
                    lyricLine.forceActiveFocus();
                    LyricsService.seekTo(Number(lyricLine.modelData.t));
                }
            }
        }
    }
}
