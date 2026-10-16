pragma Singleton
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Services.Mpris
import qs.modules.services

Singleton {
    id: root

    readonly property MprisPlayer player: MprisController.activePlayer
    readonly property string youtubeId: {
        const url = root.player?.metadata?.["xesam:url"] ?? "";
        const match = url.match(/^https?:\/\/(?:(?:[a-z0-9-]+\.)*youtube\.com\/(?:watch\?(?:[^#]*&)?v=|(?:shorts|embed|live)\/)|youtu\.be\/)([A-Za-z0-9_-]{11})(?:[?&#/]|$)/i);
        return match ? match[1] : "";
    }
    readonly property string identity: root.player
        ? [root.player.dbusName, root.player.uniqueId, root.youtubeId].join("\n") : "";
    readonly property real nativeLength: root.player?.lengthSupported
        ? Math.max(0, root.player.length) : 0;
    readonly property real length: root.live ? 0
        : root.verified && root.learnedFor === root.identity ? root.learnedLength
        : root.nativeLength > 0 ? root.nativeLength
        : root.learnedFor === root.identity ? root.learnedLength : 0;

    property string learnedFor: ""
    property real learnedLength: 0
    property bool verified: false
    property bool live: false
    property int retryAttempt: 0
    property bool busy: false
    property string requestedFor: ""
    property bool exited: false
    property bool outputFinished: false
    property string output: ""

    onIdentityChanged: {
        root.learnedFor = root.identity;
        root.learnedLength = root.nativeLength;
        root.verified = false;
        root.live = false;
        root.retryAttempt = 0;
        retry.stop();
        if (root.busy)
            lookup.running = false;
        Qt.callLater(root.resolve);
    }
    onNativeLengthChanged: {
        if (root.nativeLength > 0 && !root.verified) {
            root.learnedFor = root.identity;
            root.learnedLength = root.nativeLength;
        }
        Qt.callLater(root.resolve);
    }
    Component.onCompleted: Qt.callLater(root.resolve)

    function resolve(): void {
        if (root.verified || !root.youtubeId || root.live) {
            retry.stop();
            if (root.busy)
                lookup.running = false;
            return;
        }
        if (root.busy)
            return;
        root.busy = true;
        root.requestedFor = root.identity;
        root.exited = false;
        root.outputFinished = false;
        root.output = "";
        lookup.command = ["python3", Quickshell.shellPath("scripts/media_duration.py"), root.youtubeId];
        lookup.running = true;
    }

    // Process exit and stdout completion can arrive in either order.
    function finish(): void {
        if (!root.busy || !root.exited || !root.outputFinished)
            return;
        root.busy = false;
        if (root.requestedFor !== root.identity) {
            Qt.callLater(root.resolve);
            return;
        }
        let result = null;
        try {
            result = JSON.parse(root.output);
        } catch (_) {}
        if (result?.id === root.youtubeId && result?.live === true) {
            root.live = true;
        } else if (result?.id === root.youtubeId && Number.isFinite(result?.duration)
            && result.duration > 0) {
            root.learnedFor = root.identity;
            root.learnedLength = result.duration;
            root.verified = true;
        } else if (root.youtubeId) {
            retry.restart();
        }
    }

    Timer {
        id: retry
        interval: Math.min(120000, 2000 * Math.pow(2, root.retryAttempt))
        onTriggered: {
            root.retryAttempt = Math.min(root.retryAttempt + 1, 6);
            root.resolve();
        }
    }

    Process {
        id: lookup
        stdout: StdioCollector {
            onStreamFinished: {
                root.output = text;
                root.outputFinished = true;
                Qt.callLater(root.finish);
            }
        }
        onExited: exitCode => {
            root.exited = true;
            if (exitCode !== 0) {
                root.output = "";
                root.outputFinished = true;
            }
            Qt.callLater(root.finish);
        }
    }
}
