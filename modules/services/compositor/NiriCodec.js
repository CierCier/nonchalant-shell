.pragma library

function normalize(windows, workspaces, outputs, overviewOpen) {
    if (!Array.isArray(windows) || !Array.isArray(workspaces) || !outputs || typeof outputs !== "object" || Array.isArray(outputs))
    throw new Error("Invalid Niri snapshot");
    if (windows.some(window => !window || !Number.isSafeInteger(window.id))
    || workspaces.some(workspace => !workspace || !Number.isSafeInteger(workspace.id) || !Number.isInteger(workspace.idx)))
    throw new Error("Invalid Niri identity");
    const workspaceMap = {};
    const workspaceValues = workspaces.map(workspace => {
        const normalized = {
            id: String(workspace.id),
            idx: Number(workspace.idx),
            name: workspace.name || String(workspace.idx),
            isNamed: typeof workspace.name === "string" && workspace.name.trim().length > 0,
            output: workspace.output || "",
            active: workspace.is_active === true,
            focused: workspace.is_focused === true,
            is_urgent: workspace.is_urgent === true,
            activeWindowId: workspace.active_window_id == null ? "" : String(workspace.active_window_id),
            windows: 0,
            special: false
        };
        workspaceMap[normalized.id] = normalized;
        return normalized;
    }).sort((a, b) => a.idx - b.idx);

    const clientValues = windows.map(window => {
        const workspace = workspaceMap[String(window.workspace_id)] ?? null;
        const layout = window.layout || {};
        const scrollingPosition = layout.pos_in_scrolling_layout || [0, 0];
        const tilePosition = layout.tile_pos_in_workspace_view
            || (Array.isArray(window.floating_window_position) ? window.floating_window_position : null)
            || (window.floating_window_position ? [window.floating_window_position.x, window.floating_window_position.y] : null)
            || (window.metadata ? [window.metadata.x, window.metadata.y] : null)
            || [0, 0];
        const tileSize = layout.tile_size
            || layout.window_size
            || (Array.isArray(window.floating_window_size) ? window.floating_window_size : null)
            || (window.floating_window_size ? [window.floating_window_size.width, window.floating_window_size.height] : null)
            || (window.metadata ? [window.metadata.width, window.metadata.height] : null)
            || [100, 100];


        if (workspace)
            workspace.windows += 1;

        return {
            id: String(window.id),
            pid: Number(window.pid || 0),
            appId: window.app_id || "",
            title: window.title || "",
            workspaceId: String(window.workspace_id ?? ""),
            output: workspace ? workspace.output : "",
            floating: window.is_floating === true,
            fullscreen: false,
            urgent: window.is_urgent === true,
            geometry: [Number(tilePosition[0]), Number(tilePosition[1]), Number(tileSize[0]), Number(tileSize[1])],
            geometryKnown: layout.tile_pos_in_workspace_view !== undefined || window.floating_window_position !== undefined || window.metadata !== undefined,
            tiledAtTop: window.is_floating !== true,
            is_focused: window.is_focused === true,
            scrollingPosition: scrollingPosition
        };
    }).sort((a, b) => {
        const workspaceA = workspaceMap[a.workspaceId];
        const workspaceB = workspaceMap[b.workspaceId];
        const workspaceOrder = (workspaceA ? workspaceA.idx : 0) - (workspaceB ? workspaceB.idx : 0);
        if (workspaceOrder !== 0)
            return workspaceOrder;
        const columnOrder = Number(a.scrollingPosition[0] || 0) - Number(b.scrollingPosition[0] || 0);
        if (columnOrder !== 0)
            return columnOrder;
        const tileOrder = Number(a.scrollingPosition[1] || 0) - Number(b.scrollingPosition[1] || 0);
        return tileOrder !== 0 ? tileOrder : a.id - b.id;
    });

    clientValues.forEach(client => delete client.scrollingPosition);

    const monitorValues = Object.keys(outputs).map(name => {
        const output = outputs[name] || {};
        const logical = output.logical || {};
        const activeWorkspace = workspaceValues.find(workspace => workspace.output === name && workspace.active) ?? null;
        const currentMode = output.modes && output.current_mode !== null ? output.modes[output.current_mode] : null;
        return {
            id: name,
            name: name,
            focused: activeWorkspace ? activeWorkspace.focused : false,
            width: Number(logical.width || (currentMode ? currentMode.width : 0)),
            height: Number(logical.height || (currentMode ? currentMode.height : 0)),
            refreshRate: currentMode ? Number(currentMode.refresh_rate || 0) / 1000 : 0,
            scale: Number(logical.scale || 1),
            x: Number(logical.x || 0),
            y: Number(logical.y || 0),
            activeWorkspaceId: activeWorkspace ? activeWorkspace.id : ""
        };
    });

    const clientMap = {};
    clientValues.forEach(client => clientMap[client.id] = client);

    // Niri 26.04 does not expose a fullscreen boolean through IPC. A real
    // fullscreen window occupies the complete logical output as a tile.
    // Unlike fullscreen, maximize-to-edges still leaves the bar's
    // exclusive zone available, so tile geometry distinguishes the two.
    // Check only the tile: fixed-size fullscreen clients can keep a
    // smaller window geometry centered over Niri's black backdrop.
    const fullscreenOutputs = workspaceValues
        .filter(workspace => {
            if (!workspace.active || !workspace.output || workspace.activeWindowId === "")
                return false;

            const client = clientMap[workspace.activeWindowId] ?? null;
            const monitor = monitorValues.find(value => value.name === workspace.output) ?? null;
            if (!client || client.workspaceId !== workspace.id || !monitor || monitor.width <= 0 || monitor.height <= 0)
                return false;

            const epsilon = 0.5;
            const fillsOutput = Math.abs(Number(client.geometry[2]) - monitor.width) <= epsilon
                && Math.abs(Number(client.geometry[3]) - monitor.height) <= epsilon;
            client.fullscreen = fillsOutput;
            return fillsOutput;
        })
        .map(workspace => workspace.output);

    return { windows: clientValues, workspaces: workspaceValues, outputs: monitorValues, fullscreenOutputs: fullscreenOutputs, overviewOpen: overviewOpen };
}

function updateWindow(windows, changed) {
    const exists = windows.some(window => window.id === changed.id);
    const next = windows.map(window => {
        if (window.id === changed.id)
            return Object.assign({}, window, changed);
        return changed.is_focused === true ? Object.assign({}, window, { is_focused: false }) : window;
    });
    return exists ? next : next.concat([changed]);
}
