/* The main user journeys, run inside the real app (Anvil App Server) by tools/ui_test.py through tools/live/drive.mjs.
   Resolves to {ok, log}. Keep log lines ASCII (the Windows console).
   Visitor: landing, the public panel (#f/demo) and its tracking page. Member: sign up, Overview, Inbox (select + bulk,
   drawer, board), a story (edit, autosave, export), Links (live preview, save), Claude & API (make a key, call the API
   with it over HTTP, see the log, revoke it), sign out. The new key is printed as "KEY psk_..." for the CLI test. */
(async function () {
  const log = [], t0 = Date.now();
  const say = (m) => log.push(((Date.now() - t0) / 1000).toFixed(1) + 's ' + m);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function until(fn, what, ms) {
    const end = Date.now() + (ms || 20000);
    while (Date.now() < end) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(150); }
    throw new Error('timed out waiting for: ' + what);
  }
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const norm = (s) => (s || '').trim().replace(/\s+/g, ' ');
  const visible = (e) => e && e.getClientRects().length > 0;
  const button = (text, scope) => $$('button', scope).filter(visible).find((b) => norm(b.textContent) === text);
  async function click(text, scope) {
    const b = await until(() => button(text, scope), 'button "' + text + '"');
    b.scrollIntoView({ block: 'center' });
    b.click();
    return b;
  }
  function type(input, value) {
    input.focus();
    input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }
  function choose(select, label) {
    const i = Array.from(select.options).findIndex((o) => norm(o.textContent) === label);
    if (i < 0) throw new Error('no option ' + label);
    select.selectedIndex = i;
    select.dispatchEvent(new Event('change', { bubbles: true }));
  }
  async function page(hash, ready, what) {
    if (location.hash !== hash) window.UI_READY = false;  // the old page stays until the router runs
    location.hash = hash;
    await until(() => window.UI_READY && location.hash === hash && ready(), what || hash, 40000);
    await sleep(300);
  }
  const dialog = () => $$('.anvil-modal-content').filter(visible).pop();
  const ok = (cond, msg) => { if (!cond) throw new Error('FAILED: ' + msg); say('ok   ' + msg); };

  try {
    // ---- landing (visitors)
    await page('#landing', () => $('.lp-hero'), 'landing');
    ok($('.lp-hero a[href="#auth/signup"]') && $('.ui-header .ui-btn.primary'), 'landing: hero and header sign-up links');
    ok(/Can Claude work on my feedback/.test(document.body.textContent), 'landing: the FAQ mentions Claude');

    // ---- the public panel and the sender's tracking page
    await page('#f/demo', () => $('.px-panel .anvil-role-px-kchip'), 'panel');
    ok(!$('.ui-header') || !visible($('.ui-header')), 'panel: no header (Bare layout)');
    await click('Idea', $('.px-panel'));
    await until(() => $('.anvil-role-px-kchip.anvil-role-on button') && norm($('.anvil-role-px-kchip.anvil-role-on button').textContent) === 'Idea', 'Idea picked');
    ok(/What would you like to see/.test($('.px-panel textarea').placeholder), 'panel: the kind changes the question');
    await click('Send feedback', $('.px-panel'));
    await until(() => visible($('.px-panel .anvil-role-msg-error')), 'empty message refused');
    type($('.px-panel textarea'), 'Flow test: a calendar view for my notes would be great');
    $$('.px-rate button')[3].click();
    await until(() => /Good/.test($('.anvil-role-px-rate-label').textContent), '4 stars');
    await click('Send feedback', $('.px-panel'));
    const track = await until(() => visible($('.px-thanks')) && $('.px-follow a[href*="#t/"]'), 'thank-you screen with a tracking link', 30000);
    ok(true, 'panel: sent, with a private tracking link');
    const tok = decodeURIComponent(track.getAttribute('href').split('#t/')[1]);
    await click('Send another', $('.px-panel'));
    await until(() => $('.anvil-role-px-mine-bar button') && /Your feedback/.test($('.anvil-role-px-mine-bar button').textContent), '"Your feedback" bar');
    ok(true, 'panel: remembers this browser\'s feedback');
    await page('#t/' + tok, () => $('.tk-steps .tk-step'), 'tracking page');
    ok($$('.tk-step').length === 5 && /calendar view/.test($('.anvil-role-tk-quote').textContent), 'tracking: steps and the message');
    type($('.tk-reply textarea'), 'Weekly view first, please');
    await click('Send to the team');
    await until(() => /Weekly view first/.test($('.tk .px-tl').textContent), 'reply in the timeline');
    ok(true, 'tracking: the sender can reply');

    // ---- members-only page sends visitors to sign in, then back
    await page('#profile', () => true);
    await until(() => window.UI_READY && $$('.au-card input').length >= 2, 'redirected to sign in');
    ok(true, 'a members-only page asks visitors to sign in');
    await click('Create account', $('.au-card .ui-seg'));
    await until(() => $$('.au-card input').filter(visible).length >= 3, 'sign-up form');
    const inputs = $$('.au-card input[type=text], .au-card input[type=email], .au-card input[type=password]').filter(visible);
    type(inputs[0], 'Flow Tester'); type(inputs[1], 'flow' + Date.now() + '@example.com'); type(inputs[2], 'Hb-' + Math.random().toString(36).slice(2) + '-Kq7');
    const tick = $('.au-card input[type=checkbox]');
    if (tick && !tick.checked) tick.click();
    await click('Create account', $('.au-card .anvil-role-btn-block'));
    await until(() => location.hash === '#profile' && window.UI_READY && $('.pf-grid'), 'back on the page they wanted', 40000);
    ok(/FT/.test($('.anvil-role-avatar button').textContent), 'sign-up: signed in, sent on, initials in the header');

    // ---- Overview
    await page('#home', () => $('.hm-stats .anvil-role-stat-num') && $$('.px-row').length, 'overview');
    ok(/Flow/.test($('.hm-hello').textContent) && $$('.hm-stats .anvil-role-stat-num').length === 4, 'overview: greeting and four numbers');
    ok($$('.px-bars .b').length === 14 && $$('.hm-link').length >= 1, 'overview: 14-day chart and the starter link');

    // ---- Inbox: select + bulk, the drawer, the board
    localStorage.setItem('prepsto.inbox.mode', '"list"');
    await page('#inbox', () => $$('.px-row').length >= 3, 'inbox');
    const rows = $$('.px-row');
    rows[0].querySelector('.px-sel input').click();
    rows[1].querySelector('.px-sel input').click();
    await until(() => visible($('.ib-bulk')) && /2 selected/.test($('.ib-bulk').textContent), 'bulk bar');
    choose($('.ib-bulk select'), 'Reviewing');
    await until(() => !visible($('.ib-bulk')) || /Moved/.test(document.body.textContent), 'bulk status');
    ok(true, 'inbox: select two, move them to Reviewing');
    await until(() => $$('.px-row').length, 'rows again');
    $$('.px-row')[0].click();
    const drawer = await until(() => $('.px-drawer-in .anvil-role-px-quote'), 'drawer', 30000);
    ok(drawer.textContent.length > 5, 'drawer: opens with the message');
    choose($$('.px-drawer-in .px-controls select')[1], 'Urgent');
    await until(() => /urgent/i.test($('.px-drawer-in .anvil-role-px-prio').textContent), 'priority urgent');
    type($$('.px-drawer-in textarea').pop(), 'Flow test comment');
    await click('Post', $('.px-drawer-in'));
    await until(() => /Flow test comment/.test($('.px-drawer-in .anvil-role-px-comments').textContent), 'comment shown');
    ok(true, 'drawer: priority and a team comment');
    await click('Close', $('.px-drawer-in .px-drawer-head'));
    await until(() => !$('.px-drawer-in'), 'drawer closed');
    await click('Board');
    await until(() => $$('.ib-col').length === 4 && $$('.ib-card').length, 'board');
    ok(true, 'inbox: board view with four columns');
    await click('List');
    await until(() => $$('.px-row').length, 'list again');

    // ---- a story: edit (autosave), export
    await page('#stories', () => $('a.st-card'), 'stories');
    const storyHref = $('a.st-card').getAttribute('href');
    await page(storyHref, () => $('.sy-sentence input'), 'story');
    ok($('textarea.anvil-role-sy-title, .anvil-role-sy-title textarea').value.length > 3, 'story: the title is filled in');
    type($('.sy-sentence input'), 'busy flow tester');
    await until(() => /busy flow tester/.test($('.sy-preview').textContent), 'live sentence');
    await until(() => norm($('.anvil-role-sy-saved').textContent) === 'Saved', 'autosaved', 15000);
    ok(true, 'story: the sentence updates live and autosaves');
    await click('Export');
    await until(() => dialog() && /^# /.test(norm(dialog().querySelector('.ex-out').textContent)), 'export markdown');
    await click('Gherkin', dialog());
    await until(() => /Feature:/.test(dialog().querySelector('.ex-out').textContent), 'gherkin');
    ok(true, 'story: Export shows Markdown and Gherkin');
    await click('Close', dialog());
    await until(() => !dialog(), 'export closed');
    await page('#stories', () => $('a.st-card'), 'stories again');
    await page(storyHref, () => $('.sy-sentence input'), 'story again');
    ok($('.sy-sentence input').value === 'busy flow tester', 'story: the change was saved');

    // ---- Links: live preview, save
    await page('#links', () => $('.lk-form input') && $('.lk-stage .px-panel'), 'links');
    const prompt = $$('.lk-form input[type=text]').filter(visible)[1];  // name, question, button text, thanks
    type(prompt, 'Flow test question?');
    await until(() => /Flow test question/.test($('.lk-stage .anvil-role-px-panel-prompt').textContent), 'preview follows the form');
    ok(true, 'links: the live preview follows the form');
    await click('Save changes');
    await until(() => /Saved/.test(document.body.textContent), 'saved');
    ok($('.lk-install .px-code') && /widget\.js/.test($('.lk-install .px-code').textContent), 'links: saved, with the install code');

    // ---- Claude & API: make a key, use it, see the log, revoke it
    await page('#claude', () => $('.ak-setup .px-code'), 'claude page');
    ok(/claude mcp add prepsto/.test($('.ak-setup .px-code').textContent), 'claude: setup commands for Claude Code');
    await click('New key');
    await until(() => dialog() && dialog().querySelector('.ak-form'), 'new key dialog');
    type(dialog().querySelector('.ak-form input[type=text]'), 'Flow test key');
    await click('Create key', dialog());
    const keyLabel = await until(() => dialog() && dialog().querySelector('.anvil-role-ak-key'), 'key shown', 20000);
    const KEY = norm(keyLabel.textContent);
    ok(/^psk_[A-Za-z0-9]{40}$/.test(KEY), 'claude: the new key is shown once');
    say('KEY ' + KEY);
    await click('Done', dialog());
    await until(() => !dialog() && $$('.ak-row').length === 1, 'key in the list');
    ok(/Flow test key/.test($('.ak-row').textContent) && /update tickets/.test($('.ak-row').textContent), 'claude: the key is listed with what it may do');
    const apiBase = location.origin + '/_/api';
    const call = (method, path, body, key) => fetch(apiBase + path, { method: method, headers: Object.assign({ 'Authorization': 'Bearer ' + (key || KEY) },
      body ? { 'Content-Type': 'application/json' } : {}), body: body ? JSON.stringify(body) : undefined }).then(async (r) => ({ status: r.status, json: await r.json() }));
    let r = await call('GET', '/v1/me');
    ok(r.status === 200 && r.json.user.name === 'Flow Tester', 'api: /v1/me answers with the key');
    r = await call('GET', '/v1/me', null, 'psk_' + 'x'.repeat(40));
    ok(r.status === 401, 'api: a wrong key gets 401');
    r = await call('GET', '/v1/tickets?status=all&limit=50');
    ok(r.status === 200 && r.json.tickets.length >= 10 && !/@example\.com/.test(JSON.stringify(r.json)), 'api: lists tickets, without senders\' emails');
    const tk = r.json.tickets[0];
    r = await call('GET', '/v1/tickets/' + tk.id);
    ok(r.status === 200 && r.json.ticket.id === tk.id && r.json.you_can.update, 'api: one ticket in full');
    r = await call('POST', '/v1/tickets/' + tk.id, { status: 'done', add_tag: 'flow' });
    ok(r.status === 200 && r.json.ticket.status === 'done' && r.json.ticket.tags.indexOf('flow') >= 0, 'api: POST changes the status and tags');
    r = await call('PATCH', '/v1/tickets/' + tk.id, { starred: true });
    say((r.status === 200 ? 'ok   ' : 'note ') + 'api: PATCH answers ' + r.status);
    r = await call('POST', '/v1/tickets/' + tk.id + '/comments', { body: 'Fixed by the flow test' });
    ok(r.status === 200, 'api: a team comment');
    r = await call('POST', '/v1/tickets/' + tk.id + '/replies', { body: 'Hello' });
    ok(r.status === 403, 'api: replying to senders needs the reply permission');
    await page('#home', () => $('.hm-stats'), 'home');
    await page('#claude', () => $$('.ak-log').length, 'claude again');
    ok($$('.ak-log').length >= 6 && /POST \/v1\/tickets/.test($('.anvil-role-ak-log').textContent), 'claude: the requests are logged');
    await click('Revoke', $('.ak-row'));
    await until(() => dialog(), 'confirm');
    await click('Revoke', dialog());
    await until(() => /revoked/.test($('.ak-row').textContent), 'revoked');
    r = await call('GET', '/v1/me');
    ok(r.status === 401, 'api: a revoked key stops working');
    // a second key that may also reply, left active for the CLI + MCP test (tools/testing/cli_test.py)
    await click('New key');
    await until(() => dialog() && dialog().querySelector('.ak-form'), 'new key dialog');
    type(dialog().querySelector('.ak-form input[type=text]'), 'CLI test key');
    $$('.ak-scopes input[type=checkbox]', dialog())[2].click();
    await click('Create key', dialog());
    const key2 = await until(() => dialog() && dialog().querySelector('.anvil-role-ak-key'), 'second key shown', 20000);
    say('CLIKEY ' + norm(key2.textContent));
    await click('Done', dialog());
    await until(() => !dialog(), 'dialog closed');

    // ---- light / dark switch in the account menu, then sign out
    await click(norm($('.anvil-role-avatar button').textContent));
    await click('Dark', $('.ui-menu:not(.px-notifs)'));
    ok(document.documentElement.classList.contains('ui-dark'), 'menu: Dark switches the theme');
    await click('Auto', $('.ui-menu:not(.px-notifs)'));
    await click('Sign out', $('.ui-menu:not(.px-notifs)'));
    await until(() => location.hash === '#landing' && window.UI_READY && $('.ui-header .ui-btn.primary'), 'signed out');
    ok(true, 'sign out: back to the landing page as a visitor');

    say('PASSED');
    return { ok: true, log: log };
  } catch (e) {
    say(String(e && e.message || e));
    return { ok: false, log: log };
  }
})();
