pragma Singleton
pragma ComponentBehavior: Bound

import QtQuick
import Quickshell
import Quickshell.Io
import qs.modules.services

Singleton {
    id: root

    property int watchers: 0
    property string status: "idle"
    property string readFor: ""
    property string askedTrack: ""
    property bool requestQueued: false
    property bool queryActive: false
    property bool queryExited: false
    property bool queryOutputFinished: false
    property bool cancelledRequest: false
    property int retryAttempt: 0
    property list<var> lines: []
    property bool synced: false
    property bool instrumental: false
    property string source: ""
    property int current: -1
    property real playbackPosition: 0
    property real anchorPosition: 0
    property real anchorTime: 0

    readonly property bool hasTrack: MprisController.activePlayer !== null
        && MprisController.trackTitle.trim() !== ""
    readonly property bool youtubeTrack: /^https?:\/\/(?:(?:[a-z0-9-]+\.)*youtube\.com|youtu\.be)(?:[\/?#]|$)/i.test(
        MprisController.activePlayer?.metadata?.["xesam:url"] ?? "")
    readonly property bool ciderPlayer: /^org\.mpris\.MediaPlayer2\.cider(?:\.|$)/i.test(
        MprisController.activePlayer?.dbusName ?? "")
    readonly property string ciderTrackId: {
        if (!root.ciderPlayer)
            return "";
        // Quickshell exposes D-Bus object paths as QVariant strings on this Qt build.
        const path = String(MprisController.activePlayer?.metadata?.["mpris:trackid"] ?? "");
        return path.match(/\/([A-Za-z0-9_.-]+)(?=["')]|$)/)?.[1] ?? "";
    }
    readonly property string track: {
        const player = MprisController.activePlayer;
        if (!player || !MprisController.trackTitle.trim())
            return "";
        return [
            player.dbusName || "",
            MprisController.trackArtists || "",
            MprisController.trackTitle,
            player.trackAlbum || "",
            Math.round(MprisController.length),
            root.youtubeTrack,
            root.ciderTrackId
        ].join("\n");
    }
    readonly property bool wanted: root.watchers > 0 && root.hasTrack
    readonly property bool available: root.readFor === root.track
        && (root.status === "timed" || root.status === "plain" || root.status === "instrumental")
    readonly property string currentText: root.available && root.synced
        && root.current >= 0 && root.current < root.lines.length
        ? root.lines[root.current].text : ""
    readonly property string nextText: root.available && root.synced
        && root.current >= 0 && root.current + 1 < root.lines.length
        ? root.lines[root.current + 1].text : ""

    readonly property real lead: root.source === "cider" ? 0 : 0.25

    onTrackChanged: root.resetTrack()
    onWantedChanged: {
        if (root.wanted) {
            root.reanchor();
            if (root.readFor !== root.track)
                Qt.callLater(root.fetch);
        } else {
            retry.stop();
            root.requestQueued = false;
            if (!root.available)
                root.status = "idle";
            root.cancelQuery();
        }
    }

    Connections {
        target: MprisController
        function onPositionChanged() {
            if (root.wanted)
                root.reanchor();
        }
        function onIsPlayingChanged() {
            if (root.wanted)
                root.reanchor();
        }
    }

    Timer {
        interval: root.source === "cider" ? 33 : 120
        running: root.wanted && root.available && root.synced && MprisController.isPlaying
        repeat: true
        onTriggered: root.place()
    }

    Timer {
        id: retry
        interval: Math.min(120000, 10000 * Math.pow(2, root.retryAttempt))
        onTriggered: {
            root.retryAttempt += 1;
            root.fetch();
        }
    }

    function subscribe(): void {
        root.watchers += 1;
    }

    function release(): void {
        root.watchers = Math.max(0, root.watchers - 1);
    }

    function resetTrack(): void {
        root.lines = [];
        root.synced = false;
        root.instrumental = false;
        root.source = "";
        root.readFor = "";
        root.current = -1;
        root.retryAttempt = 0;
        retry.stop();
        root.anchorPosition = MprisController.position;
        root.anchorTime = Date.now();
        root.status = root.wanted ? "loading" : "idle";

        if (root.queryActive) {
            root.requestQueued = root.wanted;
            root.cancelQuery();
        } else {
            root.requestQueued = false;
            if (root.wanted)
                Qt.callLater(root.fetch);
        }
    }

    function reanchor(): void {
        root.anchorPosition = MprisController.position;
        root.anchorTime = Date.now();
        root.place();
    }

    function place(): void {
        const elapsed = MprisController.isPlaying
            ? Math.max(0, (Date.now() - root.anchorTime) / 1000) : 0;
        root.playbackPosition = root.anchorPosition + elapsed;
        if (!root.available || !root.synced) {
            root.current = -1;
            return;
        }

        const now = root.playbackPosition + root.lead;
        let low = 0;
        let high = root.lines.length;
        while (low < high) {
            const middle = Math.floor((low + high) / 2);
            if (root.lines[middle].t <= now)
                low = middle + 1;
            else
                high = middle;
        }
        root.current = low - 1;
        const line = root.lines[root.current];
        if (line?.end >= 0 && now >= line.end)
            root.current = -1;
    }

    function seekTo(seconds: real): bool {
        const player = MprisController.activePlayer;
        if (!player || !player.canSeek || !Number.isFinite(seconds))
            return false;

        const length = MprisController.length;
        const target = Math.max(0, Math.min(length > 0 ? length : seconds, seconds));
        player.position = target;
        root.anchorPosition = target;
        root.anchorTime = Date.now();
        root.place();
        return true;
    }

    function fetch(): void {
        if (!root.wanted || root.readFor === root.track)
            return;
        if (root.queryActive) {
            if (root.cancelledRequest || root.askedTrack !== root.track) {
                root.requestQueued = true;
                root.status = "loading";
            }
            return;
        }

        const player = MprisController.activePlayer;
        if (!player)
            return;

        root.requestQueued = false;
        root.askedTrack = root.track;
        root.queryActive = true;
        root.queryExited = false;
        root.queryOutputFinished = false;
        root.cancelledRequest = false;
        root.status = "loading";
        query.command = [
            "python3",
            Quickshell.shellPath("scripts/lyrics.py"),
            MprisController.trackArtists || "",
            MprisController.trackTitle,
            player.trackAlbum || "",
            String(Math.round(MprisController.length)),
            root.youtubeTrack ? "https://youtube.com" : ""
        ];
        if (root.ciderPlayer)
            query.command = query.command.concat([root.ciderTrackId]);
        query.running = true;
    }

    function cancelQuery(): void {
        if (!root.queryActive || root.cancelledRequest)
            return;
        root.cancelledRequest = true;
        if (query.running)
            query.running = false;
    }

    function finishQuery(): void {
        if (!root.queryActive || !root.queryExited || !root.queryOutputFinished)
            return;

        const finishedTrack = root.askedTrack;
        const wasCancelled = root.cancelledRequest;
        root.queryActive = false;
        root.queryExited = false;
        root.queryOutputFinished = false;
        root.cancelledRequest = false;
        root.askedTrack = "";

        if (!wasCancelled && finishedTrack === root.track && root.wanted
                && root.status === "loading")
            root.failNetwork(finishedTrack);

        if (root.wanted && root.requestQueued) {
            root.requestQueued = false;
            Qt.callLater(root.fetch);
        } else {
            root.requestQueued = false;
        }
    }

    function failNetwork(requestedTrack: string): void {
        if (!root.wanted || requestedTrack !== root.track)
            return;
        root.status = "network";
        retry.restart();
    }

    function receive(output: string): void {
        const requested = root.askedTrack;
        if (!requested || requested !== root.track || !root.wanted)
            return;

        let report;
        try {
            report = JSON.parse(output);
        } catch (error) {
            console.warn("LyricsService: invalid lyrics response", error);
            root.failNetwork(requested);
            return;
        }
        if (!report || typeof report !== "object" || typeof report.available !== "boolean") {
            root.failNetwork(requested);
            return;
        }
        if (report.reason === "network") {
            root.failNetwork(requested);
            return;
        }

        if (!report.available) {
            root.lines = [];
            root.synced = false;
            root.instrumental = false;
            root.current = -1;
            root.readFor = requested;
            root.status = "missing";
            root.retryAttempt = 0;
            retry.stop();
            return;
        }

        if (report.instrumental === true) {
            root.lines = [];
            root.synced = false;
            root.instrumental = true;
            root.current = -1;
            root.readFor = requested;
            root.status = "instrumental";
            root.retryAttempt = 0;
            retry.stop();
            return;
        }

        if (!Array.isArray(report.lines)) {
            root.failNetwork(requested);
            return;
        }

        const parsed = [];
        for (let i = 0; i < report.lines.length; i++) {
            const line = report.lines[i];
            const time = Number(line?.t);
            if (!line || !Number.isFinite(time) || typeof line.text !== "string") {
                root.failNetwork(requested);
                return;
            }
            const end = line.end === undefined ? -1 : Number(line.end);
            if (!Number.isFinite(end) || (end !== -1 && end <= time)) {
                root.failNetwork(requested);
                return;
            }
            const words = [];
            if (line.words !== undefined && !Array.isArray(line.words)) {
                root.failNetwork(requested);
                return;
            }
            let lastEnd = 0;
            for (const word of line.words ?? []) {
                if (!Number.isFinite(word?.t) || !Number.isFinite(word?.end)
                        || word.t < time || word.end <= word.t
                        || (end >= 0 && word.end > end)
                        || !Number.isInteger(word.start) || !Number.isInteger(word.length)
                        || word.start < lastEnd || word.length <= 0
                        || word.start + word.length > line.text.length) {
                    root.failNetwork(requested);
                    return;
                }
                words.push(word);
                lastEnd = word.start + word.length;
            }
            parsed.push({ t: time, end: end, text: line.text, words: words });
        }
        if (parsed.length === 0) {
            root.lines = [];
            root.synced = false;
            root.instrumental = false;
            root.current = -1;
            root.readFor = requested;
            root.status = "missing";
            root.retryAttempt = 0;
            retry.stop();
            return;
        }

        root.lines = parsed;
        root.source = report.source === "cider" ? "cider" : "lrclib";
        root.synced = report.synced === true;
        root.instrumental = false;
        root.readFor = requested;
        root.status = root.synced ? "timed" : "plain";
        root.retryAttempt = 0;
        retry.stop();
        root.place();
    }

    Process {
        id: query
        command: []
        running: false

        stdout: StdioCollector {
            onStreamFinished: {
                if (!root.cancelledRequest)
                    root.receive(text);
                root.queryOutputFinished = true;
                root.finishQuery();
            }
        }

        onExited: {
            root.queryExited = true;
            root.finishQuery();
        }
        onRunningChanged: {
            // FailedToStart emits neither exited nor stdout completion.
            if (query.running || !root.queryActive || root.queryExited)
                return;
            root.queryOutputFinished = true;
            root.queryExited = true;
            root.finishQuery();
        }
    }

}
