const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const codec = {};
vm.createContext(codec);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../modules/services/compositor/NiriCodec.js'), 'utf8').replace('.pragma library', ''), codec);
const output = { logical: { width: 1280, height: 720, x: -1280, y: 0, scale: 1.25 }, modes: [{ width: 1600, height: 900, refresh_rate: 60000 }], current_mode: 0 };
const workspaces = [
    { id: 44, idx: 1, output: 'DP-1', name: 'code', is_active: true, is_focused: true, active_window_id: 91 },
    { id: 45, idx: 2, output: 'DP-1', is_active: false },
    { id: 46, idx: 1, output: 'DP-2', is_active: true }
];
const window = { id: 91, workspace_id: 44, app_id: 'test', title: 'Original', is_focused: true,
    layout: { tile_pos_in_workspace_view: [0, 0], tile_size: [1280, 720], window_size: [400, 300], pos_in_scrolling_layout: [1, 0] } };
const normalize = windows => JSON.parse(JSON.stringify(codec.normalize(windows, workspaces, { 'DP-1': output }, false)));
test('Niri identities and fixed-size fullscreen use the tile and logical output', () => {
    const snapshot = normalize([window]);
    assert.equal(snapshot.windows[0].id, '91');
    assert.equal(snapshot.windows[0].workspaceId, '44');
    assert.equal(snapshot.outputs[0].activeWorkspaceId, '44');
    assert.equal(snapshot.workspaces.find(w => w.id === '44').windows, 1);
    assert.equal(snapshot.windows[0].fullscreen, true);
    assert.deepEqual(snapshot.fullscreenOutputs, ['DP-1']);
    assert.deepEqual(snapshot.windows[0].geometry, [0, 0, 1280, 720]);
    assert.equal(snapshot.outputs[0].x, -1280);
    assert.equal(snapshot.outputs[0].width, 1280);
    assert.equal(snapshot.outputs[0].scale, 1.25);
});
test('maximized tiles below the exclusive zone do not hide the bar', () => {
    const snapshot = normalize([{ ...window, layout: { ...window.layout, tile_size: [1280, 676] } }]);
    assert.deepEqual(snapshot.fullscreenOutputs, []);
});
test('a stale active-window reference cannot hide the old workspace during a move', () => {
    assert.deepEqual(normalize([{ ...window, workspace_id: 45 }]).fullscreenOutputs, []);
});
test('floating position and size survive legacy Niri event shapes', () => {
    const snapshot = normalize([{ ...window, is_floating: true, layout: {}, floating_window_position: { x: 20, y: 90 }, floating_window_size: { width: 300, height: 200 } }]);
    assert.deepEqual(snapshot.windows[0].geometry, [20, 90, 300, 200]);
    assert.equal(snapshot.windows[0].tiledAtTop, false);
    assert.equal(snapshot.windows[0].geometryKnown, true);
});
test('taskbar windows retain scrolling column and row order', () => {
    const snapshot = normalize([window, { ...window, id: 92, layout: { ...window.layout, pos_in_scrolling_layout: [0, 1] } }]);
    assert.deepEqual(snapshot.windows.map(w => w.id), ['92', '91']);
});
test('malformed snapshots fail at the Niri boundary', () => {
    assert.throws(() => codec.normalize(null, [], {}, false), /Invalid Niri snapshot/);
    assert.throws(() => codec.normalize([{ id: 'bad' }], [], {}, false), /Invalid Niri identity/);
});
const selection = {};
vm.createContext(selection);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../modules/services/compositor/SessionSelection.js'), 'utf8').replace('.pragma library', ''), selection);
test('session selection handles single sockets, desktop evidence and explicit overrides', () => {
assert.equal(selection.select('', '/niri', '', ''), 'niri');
assert.equal(selection.select('', '', 'hypr', ''), 'hyprland');
assert.equal(selection.select('', '/niri', 'hypr', ''), 'ambiguous');
assert.equal(selection.select('', '/niri', 'hypr', 'niri'), 'niri');
assert.equal(selection.select('hyprland', '/niri', '', ''), 'hyprland');
assert.equal(selection.select('invalid', '/niri', '', ''), 'unsupported');
});

test('a newly focused opened or changed window clears focus from the preceding client', () => {
    const before = [{ id: 2, title: 'B', is_focused: true }, { id: 3, title: 'A', is_focused: false }];
    const updated = codec.updateWindow(before, { id: 3, title: 'A changed', is_focused: true });
    assert.deepEqual(JSON.parse(JSON.stringify(updated.filter(w => w.is_focused).map(w => w.id))), [3]);
    const partial = codec.updateWindow(updated, { id: 3, title: 'Partial update' });
    assert.equal(partial.find(w => w.id === 3).is_focused, true);
    const opened = codec.updateWindow(partial, { id: 4, is_focused: true });
    assert.deepEqual(JSON.parse(JSON.stringify(opened.filter(w => w.is_focused).map(w => w.id))), [4]);
});
