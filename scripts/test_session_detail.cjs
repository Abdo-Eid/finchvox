const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const source = readFileSync(join(__dirname, '../ui/js/session_detail.js'), 'utf8');

function setup({ response = { ok: true } } = {}) {
    const calls = [];
    const window = {
        FinchvoxPreferences: { load: () => ({}) },
        location: { replace(path) { calls.push(['navigate', path]); } },
    };
    const mixin = () => ({});
    const app = vm.runInNewContext(`${source}\nsessionDetailApp()`, {
        window,
        logsViewMixin: mixin,
        conversationViewMixin: mixin,
        metricsViewMixin: mixin,
        environmentViewMixin: mixin,
        async fetch(url, options) { calls.push([options.method, url]); return response; },
    });
    app.sessionId = 'disposable';
    const dialog = {
        open: false,
        showModal() { this.open = true; },
        close() { this.open = false; },
    };
    app.$refs = { deleteDialog: dialog };
    return { app, calls, dialog };
}

test('opening and canceling the dialog leaves the session untouched', async () => {
    const { app, calls, dialog } = setup();
    app.openDeleteDialog();
    assert.equal(dialog.open, true);
    dialog.close();
    await app.deleteSession();
    assert.deepEqual(calls, []);
});

test('confirm deletes just this session and returns to the session list', async () => {
    const { app, calls } = setup();
    app.openDeleteDialog();
    await app.deleteSession();
    assert.deepEqual(calls, [['DELETE', '/api/sessions/disposable'], ['navigate', '/']]);
});

test('a delete failure keeps the dialog open and reports the reason', async () => {
    const { app, calls, dialog } = setup({
        response: { ok: false, status: 409, json: async () => ({ detail: 'Session is in use.' }) },
    });
    app.openDeleteDialog();
    await app.deleteSession();
    assert.deepEqual(calls.map(call => call[0]), ['DELETE']);
    assert.equal(dialog.open, true);
    assert.equal(app.deleteError, 'Session is in use.');
    assert.equal(app.deletingSession, false);
});

test('replay shortcuts do not intercept keys while the dialog is open', () => {
    const { app } = setup();
    app.openDeleteDialog();
    app.handleKeydown({ key: ' ', preventDefault() { assert.fail('Shortcut intercepted'); } });
});
