/* core.js: the shared front-end engine (window.UI). Same in every app made from APP_MAKER/template;
   app-specific things live in web/app.js (brand, nav, footer) and web/pages/*.html (the pages).

   Pages:   UI.page(name, {title, nav, icon, auth, order, chrome}, mount)
              auth: null (anyone) | 'guest' (signed-out only) | 'user' | 'admin'
              nav: label for the header / phone tab bar (omit to keep it out of the menus)
              mount(view, ctx) draws into `view`; ctx = {args, me, go, api}. Return a Promise (the page
              is "ready" when it resolves) or {ready, destroy}. URLs are #name/arg1/arg2.
   Server:  UI.api(fn, ...args) -> Promise of the server function's return value. A reply of
              {ok: false, error} rejects with that message (shown as a toast unless you .catch it).
            UI.apiQuiet(fn, ...args) is the same without Anvil's loading spinner.
   Auth:    UI.auth('login'|'signup'|'reset'|'logout', {...}) -> Promise of {ok, me, message}
   Helpers: UI.esc, UI.icon, UI.toast, UI.modal, UI.confirm, UI.busy, UI.formData, UI.fmtDate, UI.ago,
            UI.store, UI.setTheme, UI.feedback, UI.go, UI.refresh
   Tests:   window.UI_READY is true when the current page has finished loading. */
(function () {
  'use strict';
  if (window.UI && window.UI.__v) return;
  var UI = window.UI = { __v: 1, pages: {}, me: null, config: { name: 'App', key: 'app', home: 'home', landing: 'landing' } };
  window.UI_READY = false;

  UI.configure = function (cfg) { Object.keys(cfg).forEach(function (k) { UI.config[k] = cfg[k]; }); };

  /* ------------------------------------------------------------------ small helpers */
  UI.esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  UI.plural = function (n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); };
  UI.initials = function (name) {
    var p = String(name || '?').trim().split(/\s+/);
    return ((p[0] || '?')[0] + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase();
  };
  UI.fmtDate = function (iso, opts) {
    if (!iso) return '';
    var d = iso.length <= 10 ? new Date(iso + 'T12:00:00') : new Date(iso);
    return d.toLocaleDateString(undefined, opts || { day: 'numeric', month: 'short', year: 'numeric' });
  };
  UI.fmtDateTime = function (iso) {
    return iso ? new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
  };
  UI.ago = function (iso) {
    if (!iso) return '';
    var s = (Date.now() - new Date(iso).getTime()) / 1000;
    if (s < 60) return 'just now';
    var steps = [[60, 'minute'], [24, 'hour'], [7, 'day'], [4.35, 'week'], [12, 'month'], [Infinity, 'year']], n = s / 60;
    for (var i = 0; i < steps.length; i++) {
      if (n < steps[i][0]) { n = Math.floor(n); return UI.plural(n, steps[i][1]) + ' ago'; }
      n = n / steps[i][0];
    }
    return '';
  };
  UI.store = {
    get: function (k, dflt) { try { var v = localStorage.getItem(UI.config.key + '.' + k); return v == null ? dflt : JSON.parse(v); } catch (e) { return dflt; } },
    set: function (k, v) { try { localStorage.setItem(UI.config.key + '.' + k, JSON.stringify(v)); } catch (e) {} }
  };
  UI.formData = function (form) {
    var out = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.disabled) return;
      if (el.type === 'checkbox') out[el.name] = el.checked;
      else if (el.type === 'radio') { if (el.checked) out[el.name] = el.value; }
      else out[el.name] = el.value;
    });
    return out;
  };
  /* Disable a button while a Promise runs; returns the Promise. */
  UI.busy = function (btn, promise) {
    if (!btn) return promise;
    btn.disabled = true; btn.classList.add('is-busy');
    var done = function () { btn.disabled = false; btn.classList.remove('is-busy'); };
    promise.then(done, done);
    return promise;
  };

  var ICONS = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.5 3-5.5 6.5-5.5s6.5 2 6.5 5.5"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7"/><path d="M18 14.7c2.2.6 3.5 2.4 3.5 5.3"/>',
    sliders: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    shield: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    trash: '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 14h10l1-14"/>',
    edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
    check: '<path d="M5 12.5l4.5 4.5L19 7"/>',
    x: '<path d="M6 6l12 12M18 6 6 18"/>',
    chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-4.9A8 8 0 1 1 21 12z"/>',
    bell: '<path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    moon: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    back: '<path d="M19 12H5M11 18l-6-6 6-6"/>',
    mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    bug: '<rect x="7" y="8" width="10" height="12" rx="5"/><path d="M12 8V5M9 5.5 7.5 4M15 5.5 16.5 4M7 13H3M21 13h-4M7.5 18l-3 2M16.5 18l3 2M7.5 9.5l-3-2M16.5 9.5l3-2"/>',
    bulb: '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"/>',
    star: '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    heart: '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    chevron: '<path d="m6 9 6 6 6-6"/>',
    external: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    inbox: '<path d="M3 13h5l1.5 3h5L16 13h5"/><path d="M5 5h14l2 8v6H3v-6z"/>',
    grid: '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
    sparkle: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
    database: '<ellipse cx="12" cy="5.5" rx="7.5" ry="2.5"/><path d="M4.5 5.5v13c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5v-13"/><path d="M4.5 12c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14.3-4.9L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.3 4.9L20 16"/><path d="M20 20v-4h-4"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    map: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>',
    pin: '<path d="M12 21s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/>',
    camera: '<path d="M4 8h3l2-3h6l2 3h3v12H4z"/><circle cx="12" cy="13.5" r="3.5"/>',
    image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z"/>',
    copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
    filter: '<path d="M4 5h16l-6 7.5V19l-4 1.5v-8z"/>',
    more: '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>'
  };
  UI.ICONS = ICONS;
  UI.icon = function (name, cls) {
    return '<svg class="ui-ic ' + (cls || '') + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (ICONS[name] || ICONS.sparkle) + '</svg>';
  };

  /* ------------------------------------------------------------------ toasts, modals */
  UI.toast = function (msg, kind) {
    var box = document.querySelector('.ui-toasts');
    if (!box) { box = document.createElement('div'); box.className = 'ui ui-toasts'; box.setAttribute('aria-live', 'polite'); document.body.appendChild(box); }
    var t = document.createElement('div');
    t.className = 'ui-toast' + (kind ? ' ' + kind : '');
    t.innerHTML = (kind === 'error' ? UI.icon('info') : kind === 'ok' ? UI.icon('check') : '') + '<span>' + UI.esc(msg) + '</span>';
    box.appendChild(t);
    setTimeout(function () { t.classList.add('out'); setTimeout(function () { t.remove(); }, 300); }, kind === 'error' ? 6500 : 3200);
  };
  UI.modal = function (html, opts) {
    opts = opts || {};
    var prev = document.activeElement;
    var wrap = document.createElement('div');
    wrap.className = 'ui ui-modal-wrap';
    wrap.innerHTML = '<div class="ui-modal' + (opts.wide ? ' wide' : '') + '" role="dialog" aria-modal="true">' +
      '<button class="ui-btn ghost icon ui-modal-x" data-close aria-label="Close">' + UI.icon('x') + '</button>' + html + '</div>';
    document.body.appendChild(wrap);
    document.documentElement.classList.add('ui-modal-open');
    function key(e) { if (e.key === 'Escape') close(); }
    function close() {
      if (!wrap.parentNode) return;
      wrap.remove(); document.removeEventListener('keydown', key);
      if (!document.querySelector('.ui-modal-wrap')) document.documentElement.classList.remove('ui-modal-open');
      if (opts.onclose) opts.onclose();
      if (prev && prev.focus) prev.focus();
    }
    document.addEventListener('keydown', key);
    wrap.addEventListener('mousedown', function (e) { if (e.target === wrap) close(); });
    wrap.addEventListener('click', function (e) { if (e.target.closest('[data-close]')) close(); });
    var first = wrap.querySelector('input, textarea, select');
    setTimeout(function () { (first || wrap.querySelector('.ui-modal')).focus && (first || wrap.querySelector('.ui-modal')).focus(); }, 30);
    return { el: wrap.querySelector('.ui-modal'), close: close };
  };
  UI.confirm = function (o) {
    o = typeof o === 'string' ? { title: o } : (o || {});
    return new Promise(function (resolve) {
      var answered = false;
      var m = UI.modal('<h2>' + UI.esc(o.title || 'Are you sure?') + '</h2>' + (o.text ? '<p class="muted">' + UI.esc(o.text) + '</p>' : '') +
        '<div class="ui-row end" style="margin-top:20px"><button class="ui-btn ghost" data-close>' + UI.esc(o.cancel || 'Cancel') + '</button>' +
        '<button class="ui-btn ' + (o.danger ? 'danger solid' : 'primary') + '" data-ok>' + UI.esc(o.ok || 'OK') + '</button></div>',
      { onclose: function () { if (!answered) resolve(false); } });
      m.el.querySelector('[data-ok]').onclick = function () { answered = true; m.close(); resolve(true); };
    });
  };

  /* ------------------------------------------------------------------ theme */
  UI.theme = function () { return UI.store.get('theme', 'auto'); };
  UI.applyTheme = function (t) {
    if (t === 'light' || t === 'dark') document.documentElement.setAttribute('data-theme', t);
    else document.documentElement.removeAttribute('data-theme');
    var dark = t === 'dark' || (t !== 'light' && window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.classList.toggle('ui-dark', !!dark);
  };
  UI.setTheme = function (t) { UI.store.set('theme', t); UI.applyTheme(t); };
  UI.applyTheme(UI.theme());
  if (window.matchMedia) {
    try { matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () { UI.applyTheme(UI.theme()); }); } catch (e) {}
  }

  /* ------------------------------------------------------------------ server bridge */
  var bridge = null;
  function send(kind, payload) {
    if (!bridge) return Promise.reject(new Error('The app is still starting.'));
    var out;
    try { out = bridge(kind, JSON.stringify(payload || {})); } catch (e) { return Promise.reject(e); }
    return Promise.resolve(out).then(function (r) {
      r = typeof r === 'string' ? JSON.parse(r) : (r || {});
      if (r.error) {
        var err = new Error(r.error); err.uiApi = true; err.denied = !!r.denied;
        if (r.detail) console.error(kind, payload && payload.fn, r.detail);
        if (r.reload) setTimeout(function () { location.reload(); }, 2500);
        throw err;
      }
      return r.result;
    });
  }
  function apiCall(quiet, fn, args) {
    return send('call', { fn: fn, args: args, quiet: quiet }).then(function (res) {
      if (res && typeof res === 'object' && res.ok === false) {
        var err = new Error(res.error || 'That didn\'t work.'); err.uiApi = true; err.expected = true; err.result = res;
        throw err;
      }
      return res;
    });
  }
  UI.api = function (fn) { return apiCall(false, fn, Array.prototype.slice.call(arguments, 1)); };
  UI.apiQuiet = function (fn) { return apiCall(true, fn, Array.prototype.slice.call(arguments, 1)); };
  /* Errors nobody caught become a toast, so a failed action is never silent. */
  window.addEventListener('unhandledrejection', function (e) {
    if (e.reason && e.reason.uiApi) { e.preventDefault(); UI.toast(e.reason.message, 'error'); }
  });

  /* Sign in / up / out. On success it navigates: to where the visitor was heading (UI.after) or home
     after signing in, to the landing page after signing out. */
  UI.auth = function (kind, payload) {
    return send(kind, payload || {}).then(function (r) {
      if (r && r.ok === false) { var err = new Error(r.error); err.uiApi = true; err.expected = true; throw err; }
      if (r && 'me' in r && (r.me || kind === 'logout')) {
        UI.me = r.me || null;
        var target = r.me ? (UI.after || '#' + UI.config.home) : '#' + UI.config.landing;
        UI.after = null;
        if (location.hash === target) route(); else location.hash = target;
      }
      return r;
    });
  };
  /* Update the signed-in user's details (e.g. a new name) and redraw the header, without reloading the page. */
  UI.setMe = function (me) {
    UI.me = me || null;
    if (shellRoot) renderChrome(current.name);
  };

  /* ------------------------------------------------------------------ pages and routing */
  UI.page = function (name, opts, mount) {
    if (typeof opts === 'function') { mount = opts; opts = {}; }
    opts.name = name; opts.mount = mount;
    UI.pages[name] = opts;
  };
  UI.allowed = function (p) {
    if (!p) return false;
    if (p.auth === 'user') return !!UI.me;
    if (p.auth === 'admin') return !!(UI.me && UI.me.is_admin);
    if (p.auth === 'guest') return !UI.me;
    return true;
  };
  UI.navPages = function () {
    return Object.keys(UI.pages).map(function (k) { return UI.pages[k]; })
      .filter(function (p) { return p.nav && UI.allowed(p) && (!p.when || p.when()); })
      .sort(function (a, b) { return (a.order || 50) - (b.order || 50); });
  };
  UI.parseHash = function () {
    var h = (location.hash || '').replace(/^#!?\/?/, '');
    var parts = h.split('?')[0].split('/').filter(function (x) { return x !== ''; }).map(decodeURIComponent);
    return { name: parts[0] || '', args: parts.slice(1) };
  };
  UI.hashFor = function (name) {
    var args = Array.prototype.slice.call(arguments, 1).filter(function (a) { return a != null && a !== ''; });
    return '#' + [name].concat(args.map(encodeURIComponent)).join('/');
  };
  UI.go = function (name) {
    var h = UI.hashFor.apply(null, arguments);
    if (location.hash === h) route(); else location.hash = h;
  };
  UI.refresh = function () { route(); };
  UI.after = null;  // where to go after signing in

  var shellRoot = null, view = null, current = { name: null, destroy: null }, routeSeq = 0;

  function defaultPage() { return UI.me ? UI.config.home : UI.config.landing; }

  function route() {
    var r = UI.parseHash(), name = r.name || defaultPage(), p = UI.pages[name];
    if (!p) { name = defaultPage(); p = UI.pages[name]; r.args = []; }
    if (p.auth === 'guest' && UI.me) { p = UI.pages[UI.config.home]; name = UI.config.home; r.args = []; }
    if ((p.auth === 'user' || p.auth === 'admin') && !UI.me) {
      UI.after = location.hash && location.hash !== '#' ? location.hash : null;
      p = UI.pages.auth; name = 'auth'; r.args = [];
    }
    if (p.auth === 'admin' && !(UI.me && UI.me.is_admin)) {
      UI.toast('That page is for admins only.', 'error');
      p = UI.pages[UI.config.home]; name = UI.config.home; r.args = [];
    }
    var seq = ++routeSeq;
    window.UI_READY = false;
    if (current.destroy) { try { current.destroy(); } catch (e) { console.error(e); } }
    current = { name: name, args: r.args, destroy: null };
    if (shellRoot) {
      shellRoot.className = 'ui ui-shell page-' + name + (UI.me ? ' signed-in' : ' signed-out') + (p.chrome === false ? ' no-chrome' : '');
      renderChrome(name);
    }
    // A fresh element for every page, so listeners a page adds to `view` never pile up.
    var fresh = view.cloneNode(false);
    view.parentNode.replaceChild(fresh, view);
    view = fresh;
    window.scrollTo(0, 0);
    document.title = (p.title ? (typeof p.title === 'function' ? p.title(r.args) : p.title) + ' · ' : '') + UI.config.name;
    var ctx = { name: name, args: r.args, me: UI.me, go: UI.go, api: UI.api, page: p };
    var out;
    try { out = p.mount(view, ctx); } catch (e) { console.error(e); out = Promise.reject(e); }
    var ready = out && typeof out.then === 'function' ? out : (out && out.ready) || Promise.resolve();
    if (out && out.destroy) current.destroy = out.destroy;
    Promise.resolve(ready).then(function () { if (seq === routeSeq) window.UI_READY = true; },
      function (e) {
        if (seq !== routeSeq) return;
        console.error(e);
        if (!view.innerHTML) view.innerHTML = '<div class="ui-wrap"><div class="ui-empty">' + UI.icon('info') +
          '<h3>This page didn\'t load</h3><p class="muted">' + UI.esc(e && e.message || 'Something went wrong.') + '</p>' +
          '<button class="ui-btn" onclick="UI.refresh()">Try again</button></div></div>';
        window.UI_READY = true;
      });
  }
  UI.current = function () { return current; };

  /* The shell's parts come from web/app.js: UI.shell = {header(me, active), footer(me), tabbar(me, active)} */
  function renderChrome(active) {
    var S = UI.shell || {};
    var hd = shellRoot.querySelector('[data-ui-header]'), ft = shellRoot.querySelector('[data-ui-footer]'), tb = shellRoot.querySelector('[data-ui-tabbar]');
    if (hd) hd.innerHTML = S.header ? S.header(UI.me, active) : '';
    if (ft) ft.innerHTML = S.footer ? S.footer(UI.me, active) : '';
    if (tb) tb.innerHTML = S.tabbar ? S.tabbar(UI.me, active) : '';
  }
  UI.renderChrome = function () { if (shellRoot) renderChrome(current.name); };

  /* Called by client_code/Main.py (and by the local harness) once the page is up. */
  UI.start = function (node, bridgeFn, bootJson) {
    bridge = bridgeFn;
    var boot = typeof bootJson === 'string' ? JSON.parse(bootJson || '{}') : (bootJson || {});
    UI.me = boot.me || null;
    var host = node && node.matches && node.matches('[data-ui-app]') ? node : (node && node.querySelector('[data-ui-app]')) || node || document.body;
    host.innerHTML = '<div class="ui ui-shell">' +
      '<header class="ui-header" data-ui-header></header>' +
      '<main class="ui-main" data-ui-view></main>' +
      '<footer class="ui-footer" data-ui-footer></footer>' +
      '<nav class="ui-tabbar" data-ui-tabbar aria-label="Main"></nav></div>';
    shellRoot = host.firstChild;
    view = host.querySelector('[data-ui-view]');
    if (UI.shell && UI.shell.wire) UI.shell.wire(shellRoot);
    window.addEventListener('hashchange', route);
    route();
  };

  /* ------------------------------------------------------------------ feedback form (footer + menu) */
  UI.feedback = function (kind) {
    var kinds = [['bug', 'Something\'s broken', 'bug'], ['idea', 'An idea', 'bulb'], ['question', 'A question', 'info'], ['other', 'Something else', 'chat']];
    var m = UI.modal('<h2>Send feedback</h2><p class="muted">Found a bug or have an idea? It goes straight to the people who make ' + UI.esc(UI.config.name) + '.</p>' +
      '<form class="ui-stack" data-fb>' +
      '<div class="ui-choices">' + kinds.map(function (k) {
        return '<label class="ui-choice"><input type="radio" name="kind" value="' + k[0] + '"' + ((kind || 'bug') === k[0] ? ' checked' : '') + '>' +
          '<span>' + UI.icon(k[2]) + UI.esc(k[1]) + '</span></label>';
      }).join('') + '</div>' +
      '<label class="ui-field"><span>What happened, or what would you like?</span><textarea name="message" rows="5" required minlength="5" placeholder="The more detail, the better."></textarea></label>' +
      (UI.me ? '' : '<label class="ui-field"><span>Your email <em>(optional, if you\'d like a reply)</em></span><input type="email" name="email" autocomplete="email"></label>') +
      '<p class="ui-hint">We also send the page you were on, your screen size and browser, to help us fix bugs.</p>' +
      '<div class="ui-row end"><button type="button" class="ui-btn ghost" data-close>Cancel</button><button class="ui-btn primary" type="submit">' + UI.icon('arrow') + 'Send</button></div></form>');
    var form = m.el.querySelector('[data-fb]');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var v = UI.formData(form);
      var ctx = { page: location.hash || '#', screen: innerWidth + 'x' + innerHeight, browser: navigator.userAgent.slice(0, 280), theme: UI.theme() };
      UI.busy(form.querySelector('[type=submit]'), UI.api('submit_feedback', v.kind, v.message, v.email || null, ctx)).then(function () {
        m.close(); UI.toast('Thank you! Your message was sent.', 'ok');
      });
    });
    return m;
  };

  /* Shared clicks: [data-go="page/arg"], [data-feedback], [data-theme-set] anywhere in the app. */
  document.addEventListener('click', function (e) {
    var el = e.target.closest && e.target.closest('[data-go],[data-feedback],[data-theme-set]');
    if (!el) return;
    if (el.hasAttribute('data-go')) { e.preventDefault(); UI.go.apply(null, el.getAttribute('data-go').split('/')); }
    else if (el.hasAttribute('data-feedback')) { e.preventDefault(); UI.feedback(el.getAttribute('data-feedback') || null); }
    else if (el.hasAttribute('data-theme-set')) { e.preventDefault(); UI.setTheme(el.getAttribute('data-theme-set')); if (UI.shell && UI.shell.onTheme) UI.shell.onTheme(); }
  });
})();


/* app.js: this app's identity and frame: name, header, footer, phone tab bar.
   Pages live in web/pages/*.html. The engine (window.UI) is web/core.js. */
(function () {
  'use strict';
  UI.configure({
    name: 'Prepsto',
    key: 'prepsto',          // prefix for this app's browser storage
    tagline: 'Customer feedback, from one link to user stories.',   // footer line
    home: 'home',                // first page after signing in
    landing: 'landing'           // first page for visitors who aren't signed in
  });

  var esc = UI.esc;

  function brand() {
    return '<a class="ui-brand" href="#" data-go="' + (UI.me ? UI.config.home : UI.config.landing) + '" aria-label="' + esc(UI.config.name) + ' home">' +
      '<img src="_/theme/icon.svg" alt="" width="32" height="32"><span>' + esc(UI.config.name) + '</span></a>';
  }

  function themeSwitch() {
    var t = UI.theme();
    return '<div class="ui-seg" role="group" aria-label="Appearance">' + [['auto', 'Auto'], ['light', 'Light'], ['dark', 'Dark']].map(function (o) {
      return '<button type="button" data-theme-set="' + o[0] + '" class="' + (t === o[0] ? 'on' : '') + '">' + o[1] + '</button>';
    }).join('') + '</div>';
  }

  function userMenu(me) {
    return '<div class="ui-menu" data-menu hidden>' +
      '<div class="ui-menu-head"><strong>' + esc(me.name) + '</strong><span class="muted small">' + esc(me.email) + '</span></div>' +
      '<a href="#profile" data-go="profile">' + UI.icon('user') + 'Your profile</a>' +
      (me.is_admin ? '<a href="#admin" data-go="admin">' + UI.icon('shield') + 'Admin</a>' : '') +
      '<div class="ui-menu-block"><span class="small muted">Appearance</span>' + themeSwitch() + '</div>' +
      '<button type="button" data-feedback>' + UI.icon('chat') + 'Send feedback</button>' +
      '<button type="button" data-lk-open="overview">' + UI.icon('lock') + 'Privacy &amp; Terms</button>' +
      '<button type="button" data-signout>' + UI.icon('logout') + 'Sign out</button></div>';
  }

  /* The notification bell: mentions, assignments, invites, people joining (server_code/Team.py).
     Refreshed quietly at most every 20 seconds, when a page opens. */
  var bell = { at: 0, data: null, busy: false };
  function bellHtml() {
    var n = bell.data ? bell.data.unread : 0;
    return '<button type="button" class="ui-btn ghost icon px-bell" data-bell aria-label="Notifications' + (n ? ' (' + n + ' new)' : '') + '" aria-haspopup="true">' +
      UI.icon('bell') + (n ? '<span class="px-bell-n">' + (n > 9 ? '9+' : n) + '</span>' : '') + '</button><div class="ui-menu px-notifs" data-bell-panel hidden></div>';
  }
  var VERB = { mention: 'mentioned you', assign: 'assigned you feedback', invite: 'invited you to', joined: 'joined' };
  function notifHtml(n) {
    var href = n.kind === 'invite' ? (n.token ? '#join/' + n.token : '#home') : n.story_id ? '#story/' + n.story_id : n.entry_id ? '#inbox/entry/' + n.entry_id : '#links';
    var what = n.kind === 'invite' ? VERB.invite + ' <b>' + esc(n.board) + '</b>' : n.kind === 'joined' ? VERB.joined + ' <b>' + esc(n.board) + '</b>'
      : VERB[n.kind] + ' <span class="faint">in ' + esc(n.board) + '</span>';
    return '<a href="' + esc(href) + '" data-notif="' + esc(n.id) + '" class="px-notif' + (n.read ? '' : ' unread') + '"><span class="ui-avatar">' + esc(UI.initials(n.actor)) + '</span><span class="grow">' +
      '<span><b>' + esc(n.actor) + '</b> ' + what + '</span>' + (n.text && n.kind !== 'invite' && n.kind !== 'joined' ? '<span class="q">' + esc(n.text) + '</span>' : '') +
      '<span class="t">' + esc(UI.ago(n.created)) + '</span></span></a>';
  }
  function paintBell() {
    var b = document.querySelector('[data-bell]');
    if (!b) return;
    var open = !document.querySelector('[data-bell-panel]').hidden;
    var holder = document.createElement('div'); holder.innerHTML = bellHtml();
    b.replaceWith(holder.firstChild);
    var panel = document.querySelector('[data-bell-panel]');
    if (open) { panel.hidden = false; fillPanel(panel); }
  }
  function fillPanel(panel) {
    var d = bell.data;
    panel.innerHTML = '<div class="px-notifs-head"><b>Notifications</b>' + (d && d.unread ? '<button type="button" data-bell-read>Mark all read</button>' : '') + '</div>' +
      (!d ? '<p class="small muted" style="padding:10px 12px;margin:0">Loading…</p>' : d.items.length ? d.items.map(notifHtml).join('')
        : '<p class="small muted" style="padding:14px 12px;margin:0">Nothing yet. When a teammate mentions you or assigns you feedback, it shows up here.</p>');
  }
  UI.refreshBell = function (force) {
    if (!UI.me || bell.busy || (!force && Date.now() - bell.at < 20000)) return;
    bell.busy = true;
    UI.apiQuiet('get_notifications').then(function (d) { bell.data = d; bell.at = Date.now(); bell.busy = false; paintBell(); },
      function () { bell.busy = false; });
  };

  UI.shell = {
    header: function (me, active) {
      var nav = UI.navPages();
      if (me) setTimeout(function () { UI.refreshBell(); }, 50);
      return '<div class="ui-header-in">' + brand() +
        (me ? '<nav class="ui-nav" aria-label="Main">' + nav.map(function (p) {
          return '<a href="#' + p.name + '" class="' + (p.name === active ? 'on' : '') + '">' + UI.icon(p.icon) + '<span>' + esc(p.nav) + '</span></a>';
        }).join('') + '</nav>' : '') +
        '<div class="ui-header-right">' +
        (me ? bellHtml() + '<button type="button" class="ui-avatar-btn" data-menu-toggle aria-label="Your account" aria-haspopup="true">' + esc(UI.initials(me.name)) + '</button>' + userMenu(me)
          : (active === 'auth' ? '' : '<a class="ui-btn ghost" href="#auth" data-go="auth">Sign in</a><a class="ui-btn primary" href="#auth/signup" data-go="auth/signup">Get started</a>')) +
        '</div></div>';
    },
    footer: function (me) {
      return '<div class="ui-footer-in"><div class="ui-footer-brand">' + brand() + '<p class="muted small">' + esc(UI.config.tagline) + '</p></div>' +
        '<div class="ui-footer-links">' +
        '<a href="#landing" data-go="landing">About</a>' +
        '<a href="#f/demo">Try the panel</a>' +
        '<button type="button" data-feedback>Send feedback</button>' +
        '<button type="button" data-lk-open="overview">Privacy &amp; Terms</button>' +
        '</div><p class="ui-footer-legal small muted">© ' + new Date().getFullYear() + ' ' + esc(UI.config.name) + '</p></div>';
    },
    tabbar: function (me, active) {
      var nav = UI.navPages();
      if (!me || nav.length < 2) return '';
      return nav.slice(0, 4).map(function (p) {
        return '<a href="#' + p.name + '" class="' + (p.name === active ? 'on' : '') + '">' + UI.icon(p.icon) + '<span>' + esc(p.nav) + '</span></a>';
      }).join('') + '<a href="#profile" class="' + (active === 'profile' ? 'on' : '') + '">' + UI.icon('user') + '<span>You</span></a>';
    },
    wire: function (root) {
      root.addEventListener('click', function (e) {
        var bp = root.querySelector('[data-bell-panel]');
        if (e.target.closest('[data-bell]') && bp) {
          bp.hidden = !bp.hidden;
          if (!bp.hidden) { fillPanel(bp); UI.refreshBell(true); }
          return;
        }
        var nl = e.target.closest('[data-notif]');
        if (nl && nl.classList.contains('unread')) UI.apiQuiet('mark_notifications_read', [nl.getAttribute('data-notif')]).then(function () { UI.refreshBell(true); });
        if (e.target.closest('[data-bell-read]')) {
          UI.apiQuiet('mark_notifications_read').then(function () { UI.refreshBell(true); });
          return;
        }
        if (bp && !bp.hidden && !e.target.closest('[data-bell-panel] .px-notifs-head')) bp.hidden = true;
        var t = e.target.closest('[data-menu-toggle]');
        var menu = root.querySelector('[data-menu]');
        if (t && menu) { menu.hidden = !menu.hidden; t.setAttribute('aria-expanded', String(!menu.hidden)); return; }
        if (e.target.closest('[data-signout]')) { UI.auth('logout').then(function () { UI.toast('Signed out. See you soon!'); }); }
        if (menu && !menu.hidden && !e.target.closest('[data-menu] .ui-seg')) menu.hidden = true;
      });
      document.addEventListener('keydown', function (e) {
        var menu = root.querySelector('[data-menu]');
        if (e.key === 'Escape' && menu) menu.hidden = true;
        var bp = root.querySelector('[data-bell-panel]');
        if (e.key === 'Escape' && bp) bp.hidden = true;
      });
    },
    onTheme: function () {  // redraw the menu's Auto/Light/Dark buttons and keep the menu open
      var menu = document.querySelector('[data-menu]'), open = menu && !menu.hidden;
      UI.renderChrome();
      if (open) document.querySelector('[data-menu]').hidden = false;
    }
  };
})();


/* ===== _px.html ===== */
(function () {
  var esc = UI.esc;
  // Extra icons for this app.
  UI.ICONS.code = '<path d="m8 8-4 4 4 4M16 8l4 4-4 4M13.5 5l-3 14"/>';
  UI.ICONS.link = '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>';
  UI.ICONS.story = '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>';
  UI.ICONS.board = '<rect x="3" y="4" width="5" height="16" rx="1.5"/><rect x="10" y="4" width="5" height="11" rx="1.5"/><rect x="17" y="4" width="4" height="7" rx="1.5"/>';
  UI.ICONS.list = '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>';
  UI.ICONS.download = '<path d="M12 4v11M7 10l5 5 5-5"/><path d="M5 20h14"/>';
  UI.ICONS.flag = '<path d="M5 21V4h11l-2 4 2 4H5"/>';
  UI.ICONS.wand = '<path d="m4 20 11-11M14 4v3M18.5 5.5l-2 2M20 10h-3M12.5 9.5l2 2"/>';
  UI.ICONS.eye = '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>';
  UI.ICONS.pulse = '<path d="M3 12h4l3-8 4 16 3-8h4"/>';
  UI.ICONS.archive = '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v10h14V9M10 13h4"/>';
  UI.ICONS.praise = '<path d="M7 11v9H4v-9zM7 11l4-7c1.5 0 2.5 1 2.2 2.6L12.6 10H19a2 2 0 0 1 2 2.3l-1.2 6A2 2 0 0 1 17.8 20H7"/>';

  var PX = window.PX = {};
  PX.KINDS = { bug: ['Bug', 'bug'], idea: ['Idea', 'bulb'], praise: ['Praise', 'praise'], question: ['Question', 'info'], other: ['Other', 'chat'] };
  PX.STATUSES = [['new', 'New'], ['reviewing', 'Reviewing'], ['planned', 'Planned'], ['done', 'Done'], ['archived', 'Archived']];
  PX.PRIORITIES = [['', 'No priority'], ['low', 'Low'], ['medium', 'Medium'], ['high', 'High'], ['urgent', 'Urgent']];
  PX.STORY_STATUSES = [['draft', 'Draft'], ['ready', 'Ready'], ['in_progress', 'In progress'], ['shipped', 'Shipped']];
  PX.label = function (list, key) { var f = list.filter(function (x) { return x[0] === key; })[0]; return f ? f[1] : key; };

  PX.kind = function (k) { var m = PX.KINDS[k] || PX.KINDS.other; return '<span class="px-kind ' + esc(k) + '">' + UI.icon(m[1]) + esc(m[0]) + '</span>'; };
  PX.status = function (s) { return '<span class="px-status ' + esc(s) + '">' + esc(PX.label(PX.STATUSES, s)) + '</span>'; };
  PX.prio = function (p) { return p ? '<span class="px-prio ' + esc(p) + '">' + (p === 'urgent' ? '!! ' : p === 'high' ? '! ' : '') + esc(p) + '</span>' : ''; };
  PX.senti = function (ai) { return ai && ai.sentiment ? '<span class="px-senti ' + esc(ai.sentiment) + '" title="Sentiment (' + esc(ai.provider || 'rules') + ')"><i></i>' + esc(ai.sentiment) + '</span>' : ''; };
  PX.stars = function (n) { if (!n) return ''; var s = ''; for (var i = 1; i <= 5; i++) s += i <= n ? '★' : '<span>★</span>'; return '<span class="px-stars" title="' + n + ' out of 5">' + s + '</span>'; };
  PX.who = function (e) { return e.name || (e.email ? e.email.split('@')[0] : 'Anonymous'); };
  PX.host = function (url) { try { var u = new URL(url); return u.host + (u.pathname === '/' ? '' : u.pathname); } catch (e) { return url || ''; } };

  /* Links and snippets for a board. On prepsto.com: https://prepsto.com/#f/<slug> */
  PX.base = function () { return location.origin + location.pathname.replace(/[^/]*$/, ''); };
  PX.link = function (b) { return PX.base() + '#f/' + b.slug; };
  PX.snippet = function (b) {
    return '<script src="' + PX.base() + '_/theme/widget.js" data-prepsto="' + b.slug + '" data-color="' + b.color + '" data-label="' + b.label.replace(/"/g, '') + '" data-position="' + b.position + '" async></' + 'script>';
  };
  PX.anchor = function (b) { return '<a href="' + PX.link(b) + '" target="_blank" rel="noopener">' + esc(b.label) + '</a>'; };
  PX.highlight = function (code) {
    return esc(code).replace(/ ([a-z-]+)=/g, ' \u0001$1\u0002=').replace(/(&lt;\/?[a-z]+)/g, '<span class="tok-tag">$1</span>')
      .replace(/\u0001/g, '<span class="tok-attr">').replace(/\u0002/g, '</span>');
  };
  PX.copy = function (text, what) {
    function done() { UI.toast((what || 'Copied') + ' to the clipboard', 'ok'); }
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(text).then(done, fallback);
    fallback();
    function fallback() {
      var t = document.createElement('textarea'); t.value = text; t.style.position = 'fixed'; t.style.opacity = '0'; document.body.appendChild(t); t.select();
      try { document.execCommand('copy'); done(); } catch (e) { UI.toast('Copy didn\'t work: select the text and copy it.', 'error'); }
      t.remove();
    }
  };
  PX.download = function (name, text, type) {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type: type || 'text/plain' }));
    a.download = name; document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  };

  /* ------------------------------------------------------------------ the panel
     PX.panel(el, board, {preview, embed, onClose, page}) draws the feedback form into el. */
  PX.panel = function (el, b, opts) {
    opts = opts || {};
    var rating = 0, kinds = b.kinds && b.kinds.length ? b.kinds : ['idea'];
    var foot = '<div class="px-panel-foot"><span>' + (opts.preview ? 'Preview' : 'Private: only the team reads this') + '</span>' +
      '<a href="' + esc(PX.base()) + '" target="_blank" rel="noopener"><img src="_/theme/icon.svg" alt="">Prepsto</a></div>';
    function head() {
      return '<div class="px-panel-head"><span class="mark">' + UI.icon('chat') + '</span><div><h2>' + esc(b.prompt) + '</h2><p>' + esc(b.name) + '</p></div>' +
        (opts.embed || opts.onClose ? '<button type="button" class="ui-btn ghost icon x" data-px-close aria-label="Close">' + UI.icon('x') + '</button>' : '') + '</div>';
    }
    function form() {
      if (!b.is_open) return '<div class="px-closed">' + UI.icon('lock') + '<p>This feedback panel is closed for now.</p></div>';
      return '<form data-px-form novalidate>' +
        (kinds.length > 1 ? '<div class="px-kinds" role="radiogroup" aria-label="Kind of feedback">' + kinds.map(function (k, i) {
          var m = PX.KINDS[k] || PX.KINDS.other;
          return '<label><input type="radio" name="kind" value="' + esc(k) + '"' + (i === 0 ? ' checked' : '') + '><span>' + UI.icon(m[1]) + esc(m[0]) + '</span></label>';
        }).join('') + '</div>' : '<input type="hidden" name="kind" value="' + esc(kinds[0]) + '">') +
        '<label class="ui-field"><span>Your message</span><textarea name="message" maxlength="4000" required placeholder="' + esc(placeholder(kinds[0])) + '"></textarea></label>' +
        (b.ask_rating ? '<div class="ui-field"><span>How do you rate it overall?</span><div class="px-rate" data-rate>' +
          [1, 2, 3, 4, 5].map(function (n) { return '<button type="button" data-n="' + n + '" aria-label="' + n + ' out of 5">★</button>'; }).join('') + '<small data-rate-label></small></div></div>' : '') +
        (b.ask_email ? '<label class="ui-field"><span>Email <em>(optional, for a reply)</em></span><input type="email" name="email" autocomplete="email" placeholder="you@example.com"></label>' : '') +
        '<label class="px-hp" aria-hidden="true">Website<input type="text" name="website" tabindex="-1" autocomplete="off"></label>' +
        '<div class="ui-error" data-px-err hidden></div>' +
        '<button class="ui-btn send block" type="submit">' + UI.icon('arrow') + 'Send feedback</button></form>';
    }
    function placeholder(k) {
      return { bug: 'What went wrong? What did you expect to happen?', idea: 'What would you like to see?', praise: 'What do you like?',
        question: 'What would you like to know?', other: 'Tell us anything.' }[k] || 'Tell us anything.';
    }
    function draw() {
      el.innerHTML = '<div class="px-panel" style="--pc:' + esc(b.color) + '">' + head() + form() + foot + '</div>';
    }
    draw();
    var LABELS = ['', 'Poor', 'Meh', 'OK', 'Good', 'Great'];
    el.addEventListener('click', function (e) {
      var r = e.target.closest('[data-rate] button');
      if (r) {
        rating = +r.getAttribute('data-n') === rating ? 0 : +r.getAttribute('data-n');
        el.querySelectorAll('[data-rate] button').forEach(function (x) { x.classList.toggle('on', +x.getAttribute('data-n') <= rating); });
        el.querySelector('[data-rate-label]').textContent = LABELS[rating] || '';
        return;
      }
      if (e.target.closest('[data-px-close]')) { if (opts.onClose) opts.onClose(); return; }
      if (e.target.closest('[data-px-again]')) { rating = 0; draw(); }
    });
    el.addEventListener('change', function (e) {
      if (e.target.name === 'kind') { var t = el.querySelector('textarea[name=message]'); if (t) t.placeholder = placeholder(e.target.value); }
    });
    el.addEventListener('submit', function (e) {
      if (!e.target.matches('[data-px-form]')) return;
      e.preventDefault();
      var f = e.target, v = UI.formData(f), err = f.querySelector('[data-px-err]');
      err.hidden = true;
      if ((v.message || '').trim().length < 3) { err.textContent = 'Please write a few words.'; err.hidden = false; return; }
      if (opts.preview) { thanks(b.thanks); return; }
      var data = { kind: v.kind, message: v.message, rating: rating || null, email: v.email || '', website: v.website || '',
        page: opts.page || document.referrer || '', context: { screen: screen.width + 'x' + screen.height, browser: navigator.userAgent.slice(0, 160), lang: navigator.language || '' } };
      UI.busy(f.querySelector('[type=submit]'), UI.api('widget_submit', b.slug, data)).then(function (r) {
        thanks(r.thanks);
        if (opts.onSent) opts.onSent();
      }, function (ex) { err.textContent = ex.message; err.hidden = false; });
    });
    function thanks(msg) {
      var panel = el.querySelector('.px-panel');
      panel.innerHTML = head() + '<div class="px-thanks" data-px-thanks><span class="tick">' + UI.icon('check') + '</span><h2>Sent</h2><p>' + esc(msg || b.thanks) + '</p>' +
        '<button type="button" class="ui-btn sm" data-px-again>Send another</button></div>' + foot;
    }
  };

  /* ------------------------------------------------------------------ the drawer
     PX.drawer(entryId, {onChange}) shows one piece of feedback with triage controls. */
  PX.drawer = function (id, opts) {
    opts = opts || {};
    var wrap = document.createElement('div');
    wrap.className = 'ui px-drawer-wrap';
    wrap.innerHTML = '<aside class="px-drawer" role="dialog" aria-modal="true" aria-label="Feedback"><div class="px-drawer-head"><span class="mono small">Feedback</span>' +
      '<span class="ui-spacer"></span><button class="ui-btn ghost icon" data-x aria-label="Close">' + UI.icon('x') + '</button></div>' +
      '<div class="px-drawer-body"><div class="ui-skel" style="height:300px"></div></div></aside>';
    document.body.appendChild(wrap);
    document.documentElement.classList.add('ui-modal-open');
    var body = wrap.querySelector('.px-drawer-body'), changed = false, data = null;
    function close() {
      wrap.remove(); document.removeEventListener('keydown', key);
      if (!document.querySelector('.ui-modal-wrap, .px-drawer-wrap')) document.documentElement.classList.remove('ui-modal-open');
      if (changed && opts.onChange) opts.onChange();
    }
    function key(e) { if (e.key === 'Escape' && !document.querySelector('.ui-modal-wrap')) close(); }
    document.addEventListener('keydown', key);
    wrap.addEventListener('mousedown', function (e) { if (e.target === wrap) close(); });

    function draw(d) {
      data = d;
      var e = d.entry, ai = e.ai || {}, c = e.context || {};
      var suggested = (ai.tags || []).filter(function (t) { return e.tags.indexOf(t) < 0; });
      body.innerHTML =
        '<div class="ui-row">' + PX.kind(e.kind) + PX.status(e.status) + PX.prio(e.priority) + '<span class="ui-spacer"></span>' +
          '<button class="ui-btn ghost icon" data-star aria-label="Star" title="Star" style="color:' + (e.starred ? 'var(--c-accent)' : 'inherit') + '">' + UI.icon('star') + '</button></div>' +
        '<p class="px-quote">' + esc(e.message) + '</p>' +
        '<dl class="px-meta"><dt>From</dt><dd>' + esc(PX.who(e)) + (e.email ? ' · <a href="mailto:' + esc(e.email) + '">' + esc(e.email) + '</a>' : '') + '</dd>' +
          '<dt>When</dt><dd>' + esc(UI.fmtDateTime(e.created)) + ' <span class="faint">(' + esc(UI.ago(e.created)) + ')</span></dd>' +
          '<dt>Link</dt><dd>' + esc(e.board) + '</dd>' +
          (e.rating ? '<dt>Rating</dt><dd>' + PX.stars(e.rating) + '</dd>' : '') +
          (e.page_url ? '<dt>Page</dt><dd class="mono">' + esc(e.page_url) + '</dd>' : '') +
          (c.screen || c.browser ? '<dt>Device</dt><dd class="small muted">' + esc([c.screen, c.lang, c.browser].filter(Boolean).join(' · ')) + '</dd>' : '') + '</dl>' +
        '<div class="px-controls"><label class="ui-field"><span class="small">Status</span><select data-set="status">' +
          PX.STATUSES.map(function (s) { return '<option value="' + s[0] + '"' + (s[0] === e.status ? ' selected' : '') + '>' + s[1] + '</option>'; }).join('') + '</select></label>' +
          '<label class="ui-field"><span class="small">Priority</span><select data-set="priority">' +
          PX.PRIORITIES.map(function (s) { return '<option value="' + s[0] + '"' + (s[0] === e.priority ? ' selected' : '') + '>' + s[1] + '</option>'; }).join('') + '</select></label>' +
          '<label class="ui-field px-assign"><span class="small">Assigned to</span><select data-assign><option value="">Nobody</option>' +
          (d.team || []).map(function (p) { return '<option value="' + esc(p.id) + '"' + (e.assignee && e.assignee.id === p.id ? ' selected' : '') + '>' + esc(p.name) + (UI.me && p.name === UI.me.name ? ' (me)' : '') + '</option>'; }).join('') +
          '</select></label></div>' +
        '<div class="px-section"><h4>Tags</h4><div class="px-tags">' +
          e.tags.map(function (t) { return '<span class="px-tag">#' + esc(t) + '<button data-untag="' + esc(t) + '" aria-label="Remove ' + esc(t) + '">×</button></span>'; }).join('') +
          '<form data-tagform style="display:inline"><input type="text" name="tag" placeholder="+ add tag" maxlength="24"></form></div></div>' +
        '<div class="px-ai"><h4 class="px-section" style="margin:0 0 8px;font:600 .72rem/1.2 var(--font-mono);text-transform:uppercase;letter-spacing:.08em;color:var(--c-muted)">' +
          UI.icon('sparkle') + ' Insights <span class="ui-badge" style="margin-left:4px">' + esc(ai.provider === 'ai' ? 'AI' : 'rules engine') + '</span></h4>' +
          '<div class="row">' + PX.senti(ai) + '<span class="px-prio ' + (ai.urgency === 'high' ? 'urgent' : '') + '">urgency: ' + esc(ai.urgency || '-') + '</span>' +
          (ai.theme ? '<span class="mono small muted">theme: ' + esc(ai.theme) + '</span>' : '') + '</div>' +
          (suggested.length ? '<p class="small">Suggested tags: ' + suggested.map(function (t) { return '<button class="px-tag ai" data-addtag="' + esc(t) + '" style="cursor:pointer">+ ' + esc(t) + '</button>'; }).join(' ') + '</p>' : '') +
          (ai.summary ? '<p class="small muted">Summary: ' + esc(ai.summary) + '</p>' : '') + '</div>' +
        '<div class="px-section"><h4>' + UI.icon('story') + ' User story</h4>' +
          (e.story ? '<div class="ui-row"><a class="ui-btn sm" href="#story/' + esc(e.story.id) + '">' + UI.icon('story') + esc(e.story.title) + '</a>' +
            '<button class="ui-btn sm ghost" data-unstory>Unlink</button></div>'
            : '<div class="ui-row"><button class="ui-btn sm primary" data-newstory>' + UI.icon('wand') + 'Draft a story from this</button>' +
              (d.stories.length ? '<select data-addstory style="max-width:240px;min-height:34px;padding:5px 8px;font-size:.88rem"><option value="">Add to a story…</option>' +
                d.stories.map(function (s) { return '<option value="' + esc(s.id) + '">' + esc(s.title) + '</option>'; }).join('') + '</select>' : '') + '</div>') + '</div>' +
        '<div class="px-section"><h4>' + UI.icon('chat') + ' Team comments</h4><div class="px-comments">' +
          (d.comments.length ? d.comments.map(PX.comment).join('') : '<p class="small faint" style="margin:0">No comments yet. Notes here show up in the story export as supporting comments.</p>') + '</div>' +
          '<form class="px-addc" data-commentform><textarea name="body" placeholder="Add a comment. Type @ to mention a teammate" maxlength="2000"></textarea><button class="ui-btn sm primary" type="submit">Post</button></form></div>' +
        (d.similar.length ? '<div class="px-section"><h4>' + UI.icon('pulse') + ' Similar feedback</h4><div class="px-similar">' + d.similar.map(function (s) {
          return '<button data-open="' + esc(s.id) + '"><span class="mono small">' + Math.round(s.score * 100) + '%</span><span class="t">' + esc(s.message) + '</span></button>';
        }).join('') + '</div></div>' : '') +
        '<div class="ui-row" style="border-top:1px solid var(--c-line);padding-top:14px"><button class="ui-btn sm" data-set-archive>' + UI.icon('archive') + (e.status === 'archived' ? 'Unarchive' : 'Archive') + '</button>' +
          '<span class="ui-spacer"></span>' + (d.role === 'owner' ? '<button class="ui-btn sm danger" data-del>' + UI.icon('trash') + 'Delete</button>' : '') + '</div>';
      PX.mentions(body.querySelector('[data-commentform] textarea'), d.team);
    }
    function load() { return UI.api('get_entry', id).then(draw, function (e) { body.innerHTML = '<div class="ui-empty"><h3>Not found</h3><p>' + esc(e.message) + '</p></div>'; }); }
    function update(changes) {
      changed = true;
      return UI.apiQuiet('update_entry', id, changes).then(function () { return load(); });
    }
    wrap.addEventListener('click', function (e) {
      var t = e.target;
      if (t.closest('[data-x]')) return close();
      if (!data) return;
      if (t.closest('[data-star]')) return update({ starred: !data.entry.starred });
      var ut = t.closest('[data-untag]');
      if (ut) return update({ tags: data.entry.tags.filter(function (x) { return x !== ut.getAttribute('data-untag'); }) });
      var at = t.closest('[data-addtag]');
      if (at) return update({ add_tag: at.getAttribute('data-addtag') });
      if (t.closest('[data-unstory]')) return update({ story_id: '' });
      if (t.closest('[data-set-archive]')) return update({ status: data.entry.status === 'archived' ? 'new' : 'archived' }).then(function () { UI.toast(data.entry.status === 'archived' ? 'Archived' : 'Back in the inbox', 'ok'); });
      var op = t.closest('[data-open]');
      if (op) { id = op.getAttribute('data-open'); body.scrollTop = 0; return load(); }
      if (t.closest('[data-newstory]')) {
        return UI.busy(t.closest('button'), UI.api('create_story', null, [id])).then(function (r) { changed = true; close(); UI.toast('Story drafted', 'ok'); UI.go('story', r.story.id); });
      }
      if (t.closest('[data-del]')) {
        UI.confirm({ title: 'Delete this feedback?', text: 'It and its comments are gone for good. Archive it instead if you might need it.', ok: 'Delete', danger: true }).then(function (yes) {
          if (yes) UI.api('delete_entry', id).then(function () { changed = true; close(); UI.toast('Deleted', 'ok'); });
        });
        return;
      }
      var dc = t.closest('[data-delc]');
      if (dc) UI.api('delete_comment', dc.getAttribute('data-delc')).then(load);
      if (t.closest('a[href^="#story/"]')) close();
    });
    wrap.addEventListener('change', function (e) {
      var s = e.target.closest('[data-set]');
      if (s) { var ch = {}; ch[s.getAttribute('data-set')] = s.value; update(ch); }
      if (e.target.matches('[data-addstory]') && e.target.value) update({ story_id: e.target.value }).then(function () { UI.toast('Added to the story', 'ok'); });
      if (e.target.matches('[data-assign]')) update({ assignee_id: e.target.value }).then(function () { UI.toast(e.target.value ? 'Assigned' : 'Unassigned', 'ok'); });
    });
    wrap.addEventListener('submit', function (e) {
      e.preventDefault();
      var f = e.target, v = UI.formData(f);
      if (f.matches('[data-tagform]') && v.tag.trim()) update({ add_tag: v.tag });
      if (f.matches('[data-commentform]') && v.body.trim()) {
        UI.busy(f.querySelector('button'), UI.api('add_comment', 'entry', id, v.body, PX.mentionIds(f.querySelector('textarea')))).then(function () { changed = true; load(); });
      }
    });
    load();
    return { close: close };
  };

  PX.comment = function (c) {
    var body = esc(c.body);
    (c.mentions || []).forEach(function (m) {
      var tag = esc('@' + m.name);
      body = body.split(tag).join('<span class="px-mention">' + tag + '</span>');
    });
    return '<div class="px-comment' + (c.me_mentioned ? ' to-me' : '') + '"><span class="ui-avatar">' + esc(UI.initials(c.author)) + '</span><div class="body"><div class="who"><b>' + esc(c.author) + '</b>' +
      '<span>' + esc(UI.ago(c.created)) + '</span>' + (c.can_delete || c.mine ? '<button data-delc="' + esc(c.id) + '" aria-label="Delete comment">Delete</button>' : '') + '</div><p>' + body + '</p></div></div>';
  };

  /* @mentions: PX.mentions(textarea, team) adds autocomplete (type @, pick with arrows + Enter, or click);
     PX.mentionIds(textarea) = the ids of the people still named in the text. team = [{id, name}]. */
  PX.mentions = function (ta, team) {
    if (!ta || ta._mx) return;
    ta._mx = { team: team || [], picked: {} };
    var wrap = ta.parentNode, list = document.createElement('div'), hits = [], sel = 0;
    wrap.classList.add('px-mx-wrap');
    list.className = 'px-mx'; list.hidden = true; list.setAttribute('role', 'listbox');
    wrap.appendChild(list);
    function query() {
      var m = /(^|\s)@([^\s@]{0,30})$/.exec(ta.value.slice(0, ta.selectionStart));
      return m ? m[2] : null;
    }
    function show() {
      var q = query();
      if (q === null || !ta._mx.team.length) { list.hidden = true; return; }
      hits = ta._mx.team.filter(function (p) { return p.name.toLowerCase().indexOf(q.toLowerCase()) === 0 || p.name.toLowerCase().indexOf(' ' + q.toLowerCase()) > 0; }).slice(0, 6);
      if (!hits.length) { list.hidden = true; return; }
      sel = Math.min(sel, hits.length - 1);
      list.innerHTML = hits.map(function (p, i) {
        return '<button type="button" role="option" data-mx="' + i + '" class="' + (i === sel ? 'on' : '') + '"><span class="ui-avatar">' + esc(UI.initials(p.name)) + '</span>' + esc(p.name) + '</button>';
      }).join('');
      list.hidden = false;
    }
    function pick(p) {
      var pos = ta.selectionStart, before = ta.value.slice(0, pos).replace(/@([^\s@]{0,30})$/, '@' + p.name + ' ');
      ta.value = before + ta.value.slice(pos);
      ta.selectionStart = ta.selectionEnd = before.length;
      ta._mx.picked[p.id] = p.name;
      list.hidden = true; ta.focus();
    }
    ta.addEventListener('input', function () { sel = 0; show(); });
    ta.addEventListener('keydown', function (e) {
      if (list.hidden) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); sel = (sel + (e.key === 'ArrowDown' ? 1 : hits.length - 1)) % hits.length; show(); }
      else if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); e.stopPropagation(); pick(hits[sel]); }
      else if (e.key === 'Escape') { e.stopPropagation(); list.hidden = true; }
    });
    ta.addEventListener('blur', function () { setTimeout(function () { list.hidden = true; }, 150); });
    list.addEventListener('mousedown', function (e) { var b = e.target.closest('[data-mx]'); if (b) { e.preventDefault(); pick(hits[+b.getAttribute('data-mx')]); } });
  };
  PX.mentionIds = function (ta) {
    var out = [], mx = ta && ta._mx;
    if (!mx) return out;
    mx.team.forEach(function (p) { if (ta.value.indexOf('@' + p.name) >= 0) out.push(p.id); });
    return out;
  };

  PX.assignee = function (e) {
    return e.assignee ? '<span class="px-who" title="Assigned to ' + esc(e.assignee.name) + '">' + esc(UI.initials(e.assignee.name)) + '</span>' : '';
  };

  /* One line of feedback in a list (home + inbox). */
  PX.row = function (e, opts) {
    opts = opts || {};
    return '<article class="px-row' + (e.status === 'new' ? ' is-new' : '') + '" data-entry="' + esc(e.id) + '" tabindex="0">' +
      (opts.select ? '<label class="px-sel" title="Select"><input type="checkbox" data-pick value="' + esc(e.id) + '"' + (opts.picked ? ' checked' : '') + '></label>' : '') +
      '<div class="px-row-main"><div class="px-row-top">' + PX.kind(e.kind) + PX.prio(e.priority) + (e.starred ? '<span style="color:var(--c-accent)">' + UI.icon('star') + '</span>' : '') +
      '<span class="px-row-who">' + esc(PX.who(e)) + '</span><span class="ui-spacer"></span>' + PX.assignee(e) + '<span class="mono small faint">' + esc(UI.ago(e.created)) + '</span></div>' +
      '<p class="px-row-msg">' + esc(e.message) + '</p>' +
      '<div class="px-row-bot">' + PX.status(e.status) + PX.senti(e.ai) + PX.stars(e.rating) +
      e.tags.map(function (t) { return '<span class="px-tag">#' + esc(t) + '</span>'; }).join('') +
      (e.story ? '<span class="px-tag">' + UI.icon('story') + esc(e.story.title.length > 30 ? e.story.title.slice(0, 28) + '…' : e.story.title) + '</span>' : '') +
      (opts.board ? '<span class="mono small faint">' + esc(e.board) + '</span>' : '') + '</div></div></article>';
  };

  /* A 14-day bar chart (one series; the hover tooltip gives the exact count). */
  PX.daily = function (days) {
    var max = Math.max.apply(null, days.map(function (d) { return d.count; }).concat([1]));
    return '<div class="px-bars" role="img" aria-label="Feedback per day, last 14 days">' + days.map(function (d) {
      var h = Math.round(d.count / max * 100);
      return '<div class="b' + (d.count ? '' : ' zero') + '" tabindex="0"><i style="height:' + Math.max(h, 2) + '%"></i><span class="tip">' +
        esc(UI.fmtDate(d.date, { day: 'numeric', month: 'short' })) + ': ' + d.count + '</span></div>';
    }).join('') + '</div><div class="px-axis"><span>' + esc(UI.fmtDate(days[0].date, { day: 'numeric', month: 'short' })) + '</span><span>Today</span></div>';
  };
  PX.hbars = function (pairs) {  // [[label, n]] sorted, single hue, value printed in ink
    var max = Math.max.apply(null, pairs.map(function (p) { return p[1]; }).concat([1]));
    return pairs.map(function (p) {
      return '<div class="px-hbar"><span>' + p[0] + '</span><span class="track"><i style="width:' + Math.round(p[1] / max * 100) + '%"></i></span><b>' + p[1] + '</b></div>';
    }).join('');
  };
})();

/* ===== admin.html ===== */
(function () {
  var esc = UI.esc;
  var TABS = [['overview', 'Overview', 'grid'], ['feedback', 'Feedback', 'inbox'], ['links', 'Links', 'link'], ['users', 'Users', 'users'], ['demo', 'Demo data', 'database']];

  UI.page('admin', { title: 'Admin', auth: 'admin' }, function (view, ctx) {
    var tab = TABS.some(function (t) { return t[0] === ctx.args[0]; }) ? ctx.args[0] : 'overview';
    var fbFilter = 'new';
    view.innerHTML = '<div class="ui-wrap"><div class="ui-page-head"><div><h1>Admin</h1><p class="muted">Only admins see this page.</p></div></div>' +
      '<nav class="ui-tabs">' + TABS.map(function (t) {
        return '<a href="#admin/' + t[0] + '" class="' + (t[0] === tab ? 'on' : '') + '">' + UI.icon(t[2]) + t[1] + '</a>';
      }).join('') + '</nav><div data-body><div class="ui-skel"></div></div></div>';
    var body = view.querySelector('[data-body]');

    function overview() {
      return UI.api('admin_overview').then(function (d) {
        var stat = function (n, label, go) { return '<a class="ui-card ui-stat" href="#admin/' + go + '" style="text-decoration:none;color:inherit"><b>' + n + '</b><span>' + label + '</span></a>'; };
        body.innerHTML = '<div class="ad-stats">' + stat(d.users, 'people signed up', 'users') + stat(d.admins, UI.plural(d.admins, 'admin').replace(/^\d+ /, ''), 'users') +
          stat(d.feedback_new, 'new feedback', 'feedback') + stat(d.boards, 'feedback links', 'links') + stat(d.entries, 'messages received', 'links') + stat(d.stories, 'user stories', 'links') + '</div>' +
          '<p class="muted small" style="margin-top:18px">Demo data is <b>' + esc(d.demo.state) + '</b> (' + d.demo.counts.users + ' demo people). Manage it in the Demo data tab.</p>';
      });
    }

    function feedback() {
      return UI.api('list_feedback', null).then(function (d) {
        var items = d.items.filter(function (i) { return fbFilter === 'all' || i.status === fbFilter; });
        body.innerHTML = '<div class="ui-row" style="margin-bottom:16px"><div class="ui-seg">' + [['new', 'New'], ['read', 'Read'], ['done', 'Done'], ['all', 'All']].map(function (f) {
          var n = f[0] === 'all' ? d.items.length : d.counts[f[0]];
          return '<button data-filter="' + f[0] + '" class="' + (fbFilter === f[0] ? 'on' : '') + '">' + f[1] + ' (' + n + ')</button>';
        }).join('') + '</div></div>' +
          (items.length ? '<div class="ad-fb">' + items.map(function (i) {
            var c = i.context || {};
            return '<div class="ui-item" data-id="' + esc(i.id) + '"><div class="meta"><span class="ui-badge ' + (i.kind === 'bug' ? 'bad' : i.kind === 'idea' ? 'brand' : '') + '">' + esc(i.kind_label) + '</span>' +
              '<b>' + esc(i.name) + '</b>' + (i.email ? '<a href="mailto:' + esc(i.email) + '">' + esc(i.email) + '</a>' : '') + '<span>' + esc(UI.fmtDateTime(i.created)) + '</span></div>' +
              '<p class="msg">' + esc(i.message) + '</p>' +
              '<div class="ctx">' + esc([c.page, c.screen, c.theme, c.browser].filter(Boolean).join(' · ')) + '</div>' +
              '<textarea data-note placeholder="Private note (only admins see it)">' + esc(i.note) + '</textarea>' +
              '<div class="ui-row" style="margin-top:10px">' + ['new', 'read', 'done'].map(function (s) {
                return '<button class="ui-btn sm' + (i.status === s ? ' primary' : '') + '" data-status="' + s + '">' + s[0].toUpperCase() + s.slice(1) + '</button>';
              }).join('') + '<span class="ui-spacer"></span><button class="ui-btn sm danger" data-del-fb>' + UI.icon('trash') + 'Delete</button></div></div>';
          }).join('') + '</div>'
            : '<div class="ui-empty">' + UI.icon('inbox') + '<h3>No ' + (fbFilter === 'all' ? '' : fbFilter + ' ') + 'messages</h3><p>Messages from the "Send feedback" form show up here.</p></div>');
      });
    }

    function users(query) {
      return UI.api('list_users', query || null).then(function (d) {
        body.innerHTML = '<form class="ui-row" data-search style="margin-bottom:14px"><input type="search" name="q" placeholder="Search by name or email" value="' + esc(query || '') + '" style="max-width:360px">' +
          '<button class="ui-btn" type="submit">' + UI.icon('search') + 'Search</button><span class="muted small">' + UI.plural(d.total, 'person', 'people') + '</span></form>' +
          '<table class="ad-users"><thead><tr><th>Name</th><th>Email</th><th>Joined</th><th>Admin</th><th>Active</th></tr></thead><tbody>' +
          d.users.map(function (u) {
            return '<tr data-id="' + esc(u.id) + '"><td><b>' + esc(u.name) + '</b></td><td class="email">' + esc(u.email) + '</td><td class="joined muted">' + esc(UI.fmtDate(u.joined)) + '</td>' +
              '<td><label class="ui-check"><input type="checkbox" data-admin' + (u.is_admin ? ' checked' : '') + '> Admin</label></td>' +
              '<td><label class="ui-check"><input type="checkbox" data-enabled' + (u.enabled ? ' checked' : '') + '> Active</label></td></tr>';
          }).join('') + '</tbody></table>';
      });
    }

    function demo() {
      return UI.api('admin_overview').then(function (d) {
        var c = d.demo.counts;
        body.innerHTML = '<div class="ui-card ui-narrow" style="margin:0"><h3>Demo data</h3>' +
          '<p class="muted">Example people and content, so the app never looks empty for the first visitors. Demo rows are flagged, so removing them never touches real data. Once removed, it stays removed until you load it again.</p>' +
          '<p>Status: <b>' + esc(d.demo.state) + '</b> · ' + Object.keys(c).map(function (k) { return c[k] + ' ' + esc(k); }).join(', ') + '</p>' +
          '<div class="ui-row"><button class="ui-btn primary" data-demo="load">' + UI.icon('refresh') + (d.demo.state === 'loaded' ? 'Reload demo data' : 'Load demo data') + '</button>' +
          '<button class="ui-btn danger" data-demo="remove">' + UI.icon('trash') + 'Remove demo data</button></div></div>';
      });
    }

    function links() {
      return UI.api('admin_boards').then(function (d) {
        body.innerHTML = '<p class="muted small">' + UI.plural(d.total, 'link') + '. Close a link that is being abused; owners can reopen it. You do not see the feedback itself.</p>' +
          '<table class="ad-users"><thead><tr><th>Link</th><th>Owner</th><th>Created</th><th>Messages</th><th>Open</th></tr></thead><tbody>' +
          d.boards.map(function (b) {
            return '<tr data-board="' + esc(b.id) + '"><td><b>' + esc(b.name) + '</b> <span class="mono small faint">' + esc(b.slug) + '</span>' + (b.demo ? ' <span class="ui-badge">demo</span>' : '') + (b.is_sample ? ' <span class="ui-badge">sample</span>' : '') + '</td>' +
              '<td class="email">' + esc(b.owner) + ' <span class="small muted">' + esc(b.owner_email) + '</span></td><td class="joined muted">' + esc(UI.fmtDate(b.created)) + '</td>' +
              '<td class="mono">' + b.total + '</td><td><label class="ui-check"><input type="checkbox" data-open' + (b.is_open ? ' checked' : '') + '> Open</label></td></tr>';
          }).join('') + '</tbody></table>';
      });
    }

    var DRAW = { overview: overview, feedback: feedback, links: links, users: users, demo: demo };

    view.addEventListener('click', function (e) {
      var f = e.target.closest('[data-filter]');
      if (f) { fbFilter = f.getAttribute('data-filter'); feedback(); return; }
      var st = e.target.closest('[data-status]');
      if (st) {
        var card = st.closest('[data-id]');
        UI.api('set_feedback_status', card.getAttribute('data-id'), st.getAttribute('data-status'), card.querySelector('[data-note]').value).then(function () { UI.toast('Saved', 'ok'); feedback(); });
        return;
      }
      var del = e.target.closest('[data-del-fb]');
      if (del) {
        UI.confirm({ title: 'Delete this message?', ok: 'Delete', danger: true }).then(function (yes) {
          if (yes) UI.api('delete_feedback', del.closest('[data-id]').getAttribute('data-id')).then(feedback);
        });
        return;
      }
      var dm = e.target.closest('[data-demo]');
      if (dm) {
        var load = dm.getAttribute('data-demo') === 'load';
        UI.confirm({ title: load ? 'Load the demo data?' : 'Remove the demo data?', text: load ? 'Demo people and content are added (any old demo rows are replaced).' : 'Every demo row is deleted. Real data stays.', ok: load ? 'Load' : 'Remove', danger: !load })
          .then(function (yes) { if (yes) UI.busy(dm, UI.api(load ? 'demo_load' : 'demo_remove')).then(function () { UI.toast('Done', 'ok'); demo(); }); });
      }
    });
    view.addEventListener('change', function (e) {
      var br = e.target.closest('tr[data-board]');
      if (br && e.target.matches('[data-open]')) {
        var box2 = e.target;
        UI.api('admin_set_board_open', br.getAttribute('data-board'), box2.checked).then(function () { UI.toast(box2.checked ? 'Link reopened' : 'Link closed', 'ok'); }, function (err) { box2.checked = !box2.checked; UI.toast(err.message, 'error'); });
        return;
      }
      var row = e.target.closest('tr[data-id]');
      if (!row) return;
      var id = row.getAttribute('data-id'), box = e.target;
      var fn = box.hasAttribute('data-admin') ? 'set_admin' : box.hasAttribute('data-enabled') ? 'set_enabled' : null;
      if (fn) UI.api(fn, id, box.checked).then(function () { UI.toast('Saved', 'ok'); }, function (err) { box.checked = !box.checked; UI.toast(err.message, 'error'); });
    });
    view.addEventListener('submit', function (e) {
      if (e.target.matches('[data-search]')) { e.preventDefault(); users(UI.formData(e.target).q); }
    });
    return DRAW[tab]();
  });
})();

/* ===== auth.html ===== */
(function () {
  var esc = UI.esc;
  function pw(name, auto) {
    return '<div class="au-pw"><input type="password" name="' + name + '" autocomplete="' + auto + '" required minlength="8">' +
      '<button type="button" data-show>Show</button></div>';
  }
  UI.page('auth', { title: 'Sign in', auth: 'guest' }, function (view, ctx) {
    var mode = ['signup', 'reset'].indexOf(ctx.args[0]) >= 0 ? ctx.args[0] : 'login';
    function draw(msg, isErr) {
      var heading = { login: 'Welcome back', signup: 'Create your account', reset: 'Reset your password' }[mode];
      var sub = { login: 'Sign in to continue to ' + esc(UI.config.name) + '.', signup: 'It\'s free and takes a few seconds.',
        reset: 'We\'ll email you a link to choose a new password.' }[mode];
      view.innerHTML = '<div class="au-wrap"><div class="ui-card au-card">' +
        '<h1>' + heading + '</h1><p class="muted">' + sub + '</p>' +
        (mode !== 'reset' ? '<div class="ui-seg" role="tablist"><button type="button" data-mode="login" class="' + (mode === 'login' ? 'on' : '') + '">Sign in</button>' +
          '<button type="button" data-mode="signup" class="' + (mode === 'signup' ? 'on' : '') + '">Create account</button></div>' : '<div style="height:14px"></div>') +
        '<form class="ui-stack" data-form="' + mode + '" novalidate>' +
        (mode === 'signup' ? '<label class="ui-field"><span>Your name</span><input type="text" name="name" autocomplete="name" required maxlength="60"></label>' : '') +
        '<label class="ui-field"><span>Email</span><input type="email" name="email" autocomplete="email" required></label>' +
        (mode === 'login' ? '<label class="ui-field"><span>Password</span>' + pw('password', 'current-password') + '</label>' : '') +
        (mode === 'signup' ? '<label class="ui-field"><span>Password <em>(at least 8 characters)</em></span>' + pw('password', 'new-password') + '</label>' +
          (window.LegalKit ? '<div>' + LegalKit.consentField() + '</div>' : '') : '') +
        '<div data-msg role="alert"' + (msg ? ' class="' + (isErr ? 'ui-error' : 'ui-note') + '">' + esc(msg) : ' hidden>') + '</div>' +
        '<button class="ui-btn primary block" type="submit">' + { login: 'Sign in', signup: 'Create account', reset: 'Send the link' }[mode] + '</button></form>' +
        '<div class="au-links">' + (mode === 'login' ? '<a data-mode="reset">Forgot your password?</a>' : '<a data-mode="login">' + UI.icon('back') + ' Back to sign in</a>') +
        '<a href="#landing" data-go="landing">About ' + esc(UI.config.name) + '</a></div></div></div>';
      var first = view.querySelector('input');
      if (first && !msg) first.focus();
    }
    view.addEventListener('click', function (e) {
      var m = e.target.closest('[data-mode]');
      if (m) { e.preventDefault(); mode = m.getAttribute('data-mode'); history.replaceState(null, '', '#auth' + (mode === 'login' ? '' : '/' + mode)); draw(); return; }
      var s = e.target.closest('[data-show]');
      if (s) { var i = s.parentNode.querySelector('input'); i.type = i.type === 'password' ? 'text' : 'password'; s.textContent = i.type === 'password' ? 'Show' : 'Hide'; }
    });
    view.addEventListener('submit', function (e) {
      e.preventDefault();
      var form = e.target, v = UI.formData(form);
      var problem = !/^\S+@\S+\.\S+$/.test(v.email || '') ? 'Please enter a valid email address.'
        : mode !== 'reset' && (v.password || '').length < (mode === 'signup' ? 8 : 1) ? (mode === 'signup' ? 'Please choose a password of at least 8 characters.' : 'Please enter your password.')
        : mode === 'signup' && (v.name || '').trim().length < 2 ? 'Please tell us your name.' : null;
      if (problem) { say(problem, true); return; }
      if (mode === 'signup' && window.LegalKit && !LegalKit.consentChecked(form)) return;  // the kit shows its own message
      UI.busy(form.querySelector('[type=submit]'), UI.auth(mode, v)).then(function (r) {
        if (mode === 'reset' || (r && !r.me)) { mode = 'login'; draw(r && r.message, false); restore({ email: v.email }); }
        else UI.toast(mode === 'signup' ? 'Welcome to ' + UI.config.name + '!' : 'Welcome back!', 'ok');
      }, function (err) { say(err.message, true); });
    });
    function say(msg, isErr) {
      var box = view.querySelector('[data-msg]');
      box.className = isErr ? 'ui-error' : 'ui-note'; box.textContent = msg; box.hidden = false;
    }
    function restore(v) {
      ['name', 'email'].forEach(function (k) { var i = view.querySelector('[name=' + k + ']'); if (i && v[k]) i.value = v[k]; });
    }
    draw();
  });
})();

/* ===== f.html ===== */
(function () {
  UI.page('f', { title: 'Feedback', chrome: false }, function (view, ctx) {
    var slug = ctx.args[0] || '', embed = ctx.args[1] === 'embed', page = ctx.args[2] || '';
    var shell = view.closest('.ui-shell');
    if (shell && embed) shell.classList.add('f-embed');
    function tell(msg) { try { if (window.parent !== window) window.parent.postMessage({ prepsto: msg, slug: slug }, '*'); } catch (e) {} }
    view.innerHTML = '<div class="f-wrap"><div class="ui-skel" style="height:420px"></div></div>';
    return UI.api('widget_config', slug).then(function (r) {
      document.title = r.board.name + ' · Feedback';
      var wrap = view.querySelector('.f-wrap');
      PX.panel(wrap, r.board, { embed: embed, page: page || document.referrer, onClose: embed ? function () { tell('close'); } : null,
        onSent: function () { tell('sent'); } });
    }, function (e) {
      view.innerHTML = '<div class="f-missing"><img src="_/theme/icon.svg" alt=""><h2>Feedback link not found</h2><p class="muted">' + UI.esc(e.message) +
        ' Check the link with the person who shared it.</p><a class="ui-btn" href="#landing">What is Prepsto?</a></div>';
    });
  });
})();

/* ===== home.html ===== */
(function () {
  var esc = UI.esc;
  UI.page('home', { title: 'Overview', nav: 'Overview', icon: 'grid', auth: 'user', order: 10 }, function (view, ctx) {
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:110px;margin-bottom:18px"></div><div class="ui-skel" style="height:320px"></div></div>';
    function trend(now, before) {
      if (!before && !now) return '<small>no feedback yet</small>';
      if (!before) return '<small class="up">new this week</small>';
      var p = Math.round((now - before) / before * 100);
      return '<small class="' + (p > 0 ? 'up' : p < 0 ? 'down' : '') + '">' + (p > 0 ? '+' : '') + p + '% vs last week</small>';
    }
    function draw(d) {
      var hour = new Date().getHours(), hi = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
      var kinds = Object.keys(d.kinds).sort(function (a, b) { return d.kinds[b] - d.kinds[a]; }).map(function (k) { return [PX.kind(k), d.kinds[k]]; });
      var s = d.sentiment, st = s.positive + s.neutral + s.negative;
      view.innerHTML = '<div class="ui-wrap">' +
        '<div class="hm-hello"><div><div class="eyebrow">// overview</div><h1>' + hi + ', ' + esc(d.name.split(' ')[0]) + '</h1>' +
          '<p class="muted">' + (d.new ? UI.plural(d.new, 'new piece', 'new pieces') + ' of feedback waiting for you.' : 'Inbox zero. Nicely done.') + '</p></div>' +
          '<div class="ui-row"><a class="ui-btn" href="#links">' + UI.icon('code') + 'Get the code</a><a class="ui-btn primary" href="#inbox">' + UI.icon('inbox') + 'Open inbox</a></div></div>' +
        '<div class="hm-stats">' +
          '<a class="ui-stat" href="#inbox"><b>' + d.new + '</b><span>New</span><small>' + d.open + ' open in total</small></a>' +
          '<div class="ui-stat"><b>' + d.week + '</b><span>This week</span>' + trend(d.week, d.prev_week) + '</div>' +
          '<div class="ui-stat"><b>' + (d.avg_rating == null ? '–' : d.avg_rating + '<span style="font-size:1rem;color:var(--c-faint)">/5</span>') + '</b><span>Avg rating</span><small>' + UI.plural(d.rated, 'rating') + ', 30 days</small></div>' +
          '<a class="ui-stat" href="#stories"><b>' + d.stories + '</b><span>Stories</span><small>' + d.stories_ready + ' ready to build</small></a></div>' +
        (d.invites.length ? '<section class="hm-invites">' + d.invites.map(function (v) {
          return '<div class="hm-invite"><span class="ui-avatar">' + esc(UI.initials(v.from)) + '</span><div class="grow"><span><b>' + esc(v.from) + '</b> invited you to the team of <b>' + esc(v.board) + '</b></span>' +
            '<span class="mono small faint">' + esc(UI.ago(v.created)) + '</span></div><button class="ui-btn sm ghost" data-decline="' + esc(v.token) + '">Decline</button>' +
            '<button class="ui-btn sm primary" data-accept="' + esc(v.token) + '">' + UI.icon('check') + 'Join</button></div>';
        }).join('') + '</section>' : '') +
        '<div class="hm-grid"><div>' +
          '<section class="ui-card hm-card"><h3>' + UI.icon('pulse') + 'Feedback per day <span class="mono small faint" style="font-weight:400">last 14 days</span></h3>' + PX.daily(d.daily) + '</section>' +
          (d.assigned.length ? '<section class="hm-card"><h3>' + UI.icon('user') + 'Assigned to you <a href="#inbox" data-mine-go>See all ' + UI.icon('arrow') + '</a></h3><div class="px-list hm-attn">' +
            d.assigned.map(function (e) { return PX.row(e, { board: true }); }).join('') + '</div></section>' : '') +
          (d.attention.length ? '<section class="hm-card"><h3>' + UI.icon('flag') + 'Needs attention <a href="#inbox">See all ' + UI.icon('arrow') + '</a></h3><div class="px-list hm-attn">' +
            d.attention.map(function (e) { return PX.row(e, { board: true }); }).join('') + '</div></section>' : '') +
          '<section class="hm-card"><h3>' + UI.icon('inbox') + 'Latest feedback <a href="#inbox">Inbox ' + UI.icon('arrow') + '</a></h3>' +
            (d.recent.length ? '<div class="px-list">' + d.recent.map(function (e) { return PX.row(e, { board: true }); }).join('') + '</div>'
              : '<div class="ui-empty">' + UI.icon('inbox') + '<h3>No feedback yet</h3><p>Put your link on your site and it will show up here.</p><a class="ui-btn primary" href="#links">Get your link</a></div>') + '</section>' +
        '</div><div>' +
          '<section class="ui-card hm-card"><h3>' + UI.icon('sparkle') + 'Sentiment</h3>' +
            (st ? '<div class="hm-senti" role="img" aria-label="' + s.positive + ' positive, ' + s.neutral + ' neutral, ' + s.negative + ' negative">' +
              ['positive', 'neutral', 'negative'].filter(function (k) { return s[k]; }).map(function (k) { return '<i class="' + k + '" style="flex:' + s[k] + '" title="' + k + ': ' + s[k] + '"></i>'; }).join('') + '</div>' +
              '<div class="hm-legend">' + ['positive', 'neutral', 'negative'].map(function (k) { return '<span class="px-senti ' + k + '"><i></i>' + k + ' ' + s[k] + '</span>'; }).join('') + '</div>'
              : '<p class="muted small">Appears once feedback arrives.</p>') +
            '<p class="small faint" style="margin:12px 0 0">Read by the ' + (d.provider === 'ai' ? 'AI' : 'built-in rules engine') + '. Ready for AI analysis.</p></section>' +
          '<section class="ui-card hm-card"><h3>' + UI.icon('filter') + 'By kind</h3>' + (kinds.length ? PX.hbars(kinds) : '<p class="muted small">Nothing yet.</p>') + '</section>' +
          '<section class="ui-card hm-card"><h3>' + UI.icon('grid') + 'Themes</h3>' + (d.tags.length ? '<div class="hm-tags">' + d.tags.map(function (t) {
              return '<a href="#inbox/tag/' + encodeURIComponent(t[0]) + '"><span class="px-tag">#' + esc(t[0]) + ' <b>' + t[1] + '</b></span></a>';
            }).join('') + '</div>' : '<p class="muted small">Themes show up as feedback comes in.</p>') + '</section>' +
          '<section class="ui-card hm-card"><h3>' + UI.icon('link') + 'Your links <a href="#links">Manage ' + UI.icon('arrow') + '</a></h3><div class="hm-links">' +
            (d.boards.length ? d.boards.map(function (b) {
              return '<div class="hm-link"><span class="dot" style="background:' + esc(b.color) + '"></span><div class="grow"><b>' + esc(b.name) + '</b><span>' + (b.role === 'member' ? 'shared by ' + esc(b.owner_name) : esc(b.slug)) + ' · ' + b.total + ' total · ' + b.new + ' new' + (b.team > 1 ? ' · ' + UI.plural(b.team, 'person', 'people') : '') + '</span></div>' +
                '<button class="ui-btn sm" data-copy="' + esc(b.slug) + '">' + UI.icon('copy') + 'Link</button></div>';
            }).join('') : '<a class="ui-btn primary block" href="#links">' + UI.icon('plus') + 'Create your first link</a>') + '</div></section>' +
        '</div></div></div>';
      view._boards = d.boards;
    }
    view.addEventListener('click', function (e) {
      var ac = e.target.closest('[data-accept]'), dc = e.target.closest('[data-decline]');
      if (ac) { UI.busy(ac, UI.api('accept_invite', ac.getAttribute('data-accept'))).then(function (r) { UI.toast('You joined ' + r.board, 'ok'); UI.refreshBell(true); load(); }); return; }
      if (dc) { UI.api('decline_invite', dc.getAttribute('data-decline')).then(function () { UI.toast('Invitation declined'); load(); }); return; }
      if (e.target.closest('[data-mine-go]')) { e.preventDefault(); var fl = UI.store.get('inbox.filters', {}) || {}; fl.mine = true; fl.board = ''; fl.status = 'open'; UI.store.set('inbox.filters', fl); UI.go('inbox'); return; }
      var c = e.target.closest('[data-copy]');
      if (c) { var b = view._boards.filter(function (x) { return x.slug === c.getAttribute('data-copy'); })[0]; PX.copy(PX.link(b), 'Link copied'); return; }
      var r = e.target.closest('[data-entry]');
      if (r) PX.drawer(r.getAttribute('data-entry'), { onChange: load });
    });
    view.addEventListener('keydown', function (e) { var r = e.target.closest('[data-entry]'); if (r && e.key === 'Enter') PX.drawer(r.getAttribute('data-entry'), { onChange: load }); });
    function load() { return UI.api('get_overview').then(draw); }
    return load();
  });
})();

/* ===== inbox.html ===== */
(function () {
  var esc = UI.esc;
  var COLS = ['new', 'reviewing', 'planned', 'done'];

  UI.page('inbox', { title: 'Inbox', nav: 'Inbox', icon: 'inbox', auth: 'user', order: 20 }, function (view, ctx) {
    var f = UI.store.get('inbox.filters', {}) || {};
    f = { board: f.board || '', kind: f.kind || '', tag: f.tag || '', sort: f.sort || 'newest', starred: !!f.starred, mine: !!f.mine, status: f.status || 'open', q: '' };
    if (ctx.args[0] === 'tag' && ctx.args[1]) { f.tag = ctx.args[1]; f.status = 'all'; }
    var mode = UI.store.get('inbox.mode', 'list'), picked = {}, data = null;
    function save() { UI.store.set('inbox.filters', { board: f.board, kind: f.kind, tag: f.tag, sort: f.sort, starred: f.starred, mine: f.mine, status: f.status }); }

    view.innerHTML = '<div class="ui-wrap"><div class="ib-head"><h1>Inbox</h1>' +
      '<div class="ui-seg" role="group" aria-label="View"><button data-mode="list">' + UI.icon('list') + ' List</button><button data-mode="board">' + UI.icon('board') + ' Board</button></div>' +
      '<form class="ib-search" data-search>' + UI.icon('search') + '<input type="search" name="q" placeholder="Search messages, people, pages" aria-label="Search"></form></div>' +
      '<div data-body><div class="ui-skel" style="height:420px"></div></div></div>';
    var body = view.querySelector('[data-body]');

    function opt(v, label, cur) { return '<option value="' + esc(v) + '"' + (v === cur ? ' selected' : '') + '>' + esc(label) + '</option>'; }
    function filters(d) {
      var any = f.board || f.kind || f.tag || f.starred || f.mine || f.q;
      return '<div class="ib-filters">' +
        '<select data-f="board" aria-label="Link">' + opt('', 'All links', f.board) + d.boards.map(function (b) { return opt(b.id, b.name + (b.role === 'member' ? ' (shared)' : ''), f.board); }).join('') + '</select>' +
        '<select data-f="kind" aria-label="Kind">' + opt('', 'All kinds', f.kind) + Object.keys(PX.KINDS).map(function (k) { return opt(k, PX.KINDS[k][0], f.kind); }).join('') + '</select>' +
        '<select data-f="tag" aria-label="Tag">' + opt('', 'All tags', f.tag) + (f.tag && d.tags.indexOf(f.tag) < 0 ? opt(f.tag, '#' + f.tag, f.tag) : '') + d.tags.map(function (t) { return opt(t, '#' + t, f.tag); }).join('') + '</select>' +
        '<select data-f="sort" aria-label="Sort">' + opt('newest', 'Newest first', f.sort) + opt('oldest', 'Oldest first', f.sort) + opt('priority', 'Priority', f.sort) + opt('rating', 'Lowest rating', f.sort) + '</select>' +
        '<button class="ui-btn sm' + (f.starred ? ' on' : '') + '" data-starred>' + UI.icon('star') + 'Starred</button>' +
        '<button class="ui-btn sm' + (f.mine ? ' on' : '') + '" data-mine>' + UI.icon('user') + 'Assigned to me</button>' +
        (any ? '<button class="ui-btn sm ghost clear" data-clear>' + UI.icon('x') + 'Clear filters</button>' : '') + '</div>';
    }
    function tabs(d) {
      var T = [['open', 'Open']].concat(PX.STATUSES).concat([['all', 'All']]);
      return '<nav class="ui-tabs ib-tabs">' + T.map(function (t) {
        return '<button data-status="' + t[0] + '" class="' + (f.status === t[0] ? 'on' : '') + '">' + t[1] + ' <span class="count">' + (d.counts[t[0]] || 0) + '</span></button>';
      }).join('') + '</nav>';
    }
    function empty() {
      return '<div class="ui-empty">' + UI.icon('inbox') + '<h3>' + (f.q || f.kind || f.tag || f.board || f.starred || f.mine ? 'Nothing matches these filters' : 'Nothing here') + '</h3>' +
        '<p>' + (f.status === 'new' ? 'No new feedback. Everything has been looked at.' : 'Try another tab or clear the filters.') + '</p></div>';
    }
    function list(d) {
      var n = Object.keys(picked).length;
      return tabs(d) + (d.entries.length ? '<div class="ib-count"><label><input type="checkbox" data-all' + (n && n === d.entries.length ? ' checked' : '') + '> Select all</label><span>' + UI.plural(d.total, 'result') + '</span></div>' +
        '<div class="px-list">' + d.entries.map(function (e) { return PX.row(e, { select: true, picked: !!picked[e.id], board: !f.board }).replace('class="px-row', 'class="px-row' + (picked[e.id] ? ' picked' : '')); }).join('') + '</div>' : empty()) + bulk(d);
    }
    function bulk(d) {
      var ids = Object.keys(picked);
      if (!ids.length) return '';
      return '<div class="ib-bulk" role="toolbar" aria-label="Selected feedback"><b>' + ids.length + ' selected</b>' +
        '<select data-bulk-status aria-label="Set status"><option value="">Set status…</option>' + PX.STATUSES.map(function (s) { return '<option value="' + s[0] + '">' + s[1] + '</option>'; }).join('') + '</select>' +
        '<button class="ui-btn sm" data-bulk-tag>' + UI.icon('plus') + 'Tag</button>' +
        '<button class="ui-btn sm primary" data-bulk-story>' + UI.icon('wand') + 'Draft a story</button>' +
        '<button class="ui-btn sm ghost" data-bulk-del>' + UI.icon('trash') + 'Delete</button>' +
        '<span class="ui-spacer"></span><button class="ui-btn sm ghost" data-bulk-clear>' + UI.icon('x') + 'Clear</button></div>';
    }
    function board(d) {
      var by = {}; COLS.forEach(function (c) { by[c] = []; });
      d.entries.forEach(function (e) { if (by[e.status]) by[e.status].push(e); });
      return '<p class="ib-count">Drag a card to another column to change its status. Archived feedback is hidden here.</p><div class="ib-board">' + COLS.map(function (c) {
        return '<section class="ib-col" data-col="' + c + '"><div class="ib-col-head">' + PX.status(c) + '<span class="mono small">' + by[c].length + '</span></div><div class="ib-cards">' +
          (by[c].length ? by[c].map(function (e) {
            return '<article class="ib-card" draggable="true" data-entry="' + esc(e.id) + '" tabindex="0"><div class="ui-row">' + PX.kind(e.kind) + PX.prio(e.priority) +
              (e.starred ? '<span style="color:var(--c-accent)">' + UI.icon('star') + '</span>' : '') + '<span class="ui-spacer"></span>' + PX.assignee(e) + '<span class="mono small faint">' + esc(UI.ago(e.created).replace(' ago', '')) + '</span></div>' +
              '<p>' + esc(e.message) + '</p><div class="ui-row">' + PX.senti(e.ai) + e.tags.slice(0, 2).map(function (t) { return '<span class="px-tag">#' + esc(t) + '</span>'; }).join('') +
              (e.story ? '<span class="px-tag" title="' + esc(e.story.title) + '">' + UI.icon('story') + 'story</span>' : '') + '</div></article>';
          }).join('') : '<div class="ib-colempty">Drop feedback here</div>') + '</div></section>';
      }).join('') + '</div>';
    }
    function draw() {
      var d = data;
      view.querySelectorAll('[data-mode]').forEach(function (b) { b.classList.toggle('on', b.getAttribute('data-mode') === mode); });
      body.innerHTML = filters(d) + (mode === 'board' ? board(d) : list(d));
    }
    function load() {
      var q = { board: f.board, kind: f.kind, tag: f.tag, sort: f.sort, starred: f.starred, mine: f.mine, q: f.q, status: mode === 'board' ? 'all' : f.status };
      return UI.apiQuiet('get_inbox', q).then(function (d) {
        if (f.board && !d.boards.some(function (b) { return b.id === f.board; })) { f.board = ''; save(); return load(); }
        data = d;
        if (mode === 'board') data.entries = d.entries.filter(function (e) { return e.status !== 'archived'; });
        var ids = {}; data.entries.forEach(function (e) { ids[e.id] = 1; });
        Object.keys(picked).forEach(function (k) { if (!ids[k]) delete picked[k]; });
        draw();
      });
    }
    function open(id) { PX.drawer(id, { onChange: load }); }
    function bulkDo(changes, msg) {
      var ids = Object.keys(picked);
      return UI.api('bulk_update', ids, changes).then(function (r) { if (changes.delete) picked = {}; UI.toast(msg.replace('#', r.count), 'ok'); return load(); });
    }

    view.addEventListener('click', function (e) {
      var t = e.target;
      var m = t.closest('[data-mode]');
      if (m) { mode = m.getAttribute('data-mode'); UI.store.set('inbox.mode', mode); picked = {}; load(); return; }
      var s = t.closest('[data-status]');
      if (s) { f.status = s.getAttribute('data-status'); save(); picked = {}; load(); return; }
      if (t.closest('[data-starred]')) { f.starred = !f.starred; save(); load(); return; }
      if (t.closest('[data-mine]')) { f.mine = !f.mine; save(); load(); return; }
      if (t.closest('[data-clear]')) { f.board = f.kind = f.tag = f.q = ''; f.starred = f.mine = false; view.querySelector('[data-search] input').value = ''; save(); load(); return; }
      if (t.closest('[data-bulk-clear]')) { picked = {}; draw(); return; }
      if (t.closest('[data-bulk-tag]')) {
        var mm = UI.modal('<h2>Tag ' + UI.plural(Object.keys(picked).length, 'piece') + ' of feedback</h2><form data-tagall class="ui-stack"><input type="text" name="tag" maxlength="24" required placeholder="e.g. onboarding">' +
          '<div class="ui-row end"><button type="button" class="ui-btn ghost" data-close>Cancel</button><button class="ui-btn primary">Add tag</button></div></form>');
        mm.el.querySelector('form').addEventListener('submit', function (ev) { ev.preventDefault(); var v = UI.formData(ev.target).tag; mm.close(); bulkDo({ add_tag: v }, 'Tagged #'); });
        return;
      }
      if (t.closest('[data-bulk-story]')) {
        UI.busy(t.closest('button'), UI.api('create_story', null, Object.keys(picked))).then(function (r) { picked = {}; UI.toast('Story drafted from ' + UI.plural(r.story.feedback_count, 'piece') + ' of feedback', 'ok'); UI.go('story', r.story.id); });
        return;
      }
      if (t.closest('[data-bulk-del]')) {
        UI.confirm({ title: 'Delete ' + UI.plural(Object.keys(picked).length, 'piece') + ' of feedback?', text: 'This can\'t be undone. Archiving keeps them out of the way instead.', ok: 'Delete', danger: true })
          .then(function (yes) { if (yes) bulkDo({ delete: true }, 'Deleted #'); });
        return;
      }
      if (t.closest('.px-sel')) return;
      var r = t.closest('[data-entry]');
      if (r) open(r.getAttribute('data-entry'));
    });
    view.addEventListener('change', function (e) {
      var t = e.target;
      if (t.matches('[data-f]')) { f[t.getAttribute('data-f')] = t.value; save(); load(); return; }
      if (t.matches('[data-pick]')) { if (t.checked) picked[t.value] = 1; else delete picked[t.value]; draw(); return; }
      if (t.matches('[data-all]')) { picked = {}; if (t.checked) data.entries.forEach(function (x) { picked[x.id] = 1; }); draw(); return; }
      if (t.matches('[data-bulk-status]') && t.value) bulkDo({ status: t.value }, 'Moved # to ' + PX.label(PX.STATUSES, t.value));
    });
    view.addEventListener('submit', function (e) {
      if (!e.target.matches('[data-search]')) return;
      e.preventDefault(); f.q = UI.formData(e.target).q; load();
    });
    var timer;
    view.addEventListener('input', function (e) {
      if (!e.target.closest('[data-search]')) return;
      clearTimeout(timer); timer = setTimeout(function () { f.q = e.target.value; load(); }, 300);
    });
    view.addEventListener('keydown', function (e) { var r = e.target.closest('[data-entry]'); if (r && e.key === 'Enter' && !e.target.matches('input')) open(r.getAttribute('data-entry')); });
    // drag and drop on the board
    var dragId = null;
    view.addEventListener('dragstart', function (e) { var c = e.target.closest('.ib-card'); if (!c) return; dragId = c.getAttribute('data-entry'); c.classList.add('dragging'); e.dataTransfer.effectAllowed = 'move'; try { e.dataTransfer.setData('text/plain', dragId); } catch (x) {} });
    view.addEventListener('dragend', function (e) { var c = e.target.closest('.ib-card'); if (c) c.classList.remove('dragging'); view.querySelectorAll('.ib-col.over').forEach(function (x) { x.classList.remove('over'); }); });
    view.addEventListener('dragover', function (e) { var col = e.target.closest('.ib-col'); if (!col || !dragId) return; e.preventDefault(); view.querySelectorAll('.ib-col.over').forEach(function (x) { if (x !== col) x.classList.remove('over'); }); col.classList.add('over'); });
    view.addEventListener('drop', function (e) {
      var col = e.target.closest('.ib-col'); if (!col || !dragId) return;
      e.preventDefault();
      var st = col.getAttribute('data-col'), id = dragId; dragId = null;
      var en = data.entries.filter(function (x) { return x.id === id; })[0];
      if (!en || en.status === st) { draw(); return; }
      en.status = st; draw();
      UI.apiQuiet('update_entry', id, { status: st }).then(function () { UI.toast('Moved to ' + PX.label(PX.STATUSES, st), 'ok'); load(); }, function (err) { UI.toast(err.message, 'error'); load(); });
    });
    return load().then(function () {
      if (ctx.args[0] === 'entry' && ctx.args[1]) open(ctx.args[1]);
    });
  });
})();

/* ===== join.html ===== */
(function () {
  var esc = UI.esc;
  UI.page('join', { title: 'Join a team' }, function (view, ctx) {
    var token = ctx.args[0] || '';
    view.innerHTML = '<div class="ui-wrap"><div class="jn"><div class="ui-skel" style="height:300px"></div></div></div>';
    return UI.api('get_invite', token).then(function (r) {
      var me = ctx.me, actions;
      if (r.is_owner) actions = '<p class="muted">You own this link, so you\'re already on its team.</p><div class="ui-row"><a class="ui-btn primary" href="#links">Go to your links</a></div>';
      else if (r.already) actions = '<p class="muted">You\'re already on this team.</p><div class="ui-row"><a class="ui-btn primary" href="#inbox">Open the inbox</a></div>';
      else if (me) actions = '<p class="muted small">Signed in as ' + esc(me.email) + '</p><div class="ui-row"><button class="ui-btn ghost" data-no>Not now</button>' +
        '<button class="ui-btn primary lg" data-yes>' + UI.icon('check') + 'Join the team</button></div>';
      else actions = '<p class="muted">Create a free Prepsto account (or sign in) to join.</p><div class="ui-row"><button class="ui-btn" data-auth="auth">Sign in</button>' +
        '<button class="ui-btn primary" data-auth="auth/signup">Create an account ' + UI.icon('arrow') + '</button></div>';
      view.innerHTML = '<div class="ui-wrap"><div class="jn"><div class="ui-card"><div class="marks"><span class="ui-avatar">' + esc(UI.initials(r.inviter)) + '</span><i></i>' +
        '<img src="_/theme/icon.svg" alt=""></div><div class="eyebrow">// team invitation</div><h1>' + esc(r.inviter) + ' invited you to <span style="color:var(--c-brand)">' + esc(r.board) + '</span></h1>' +
        '<ul><li>' + UI.icon('check') + 'Read and triage the feedback this link collects</li><li>' + UI.icon('check') + 'Assign feedback, comment and @mention teammates</li>' +
        '<li>' + UI.icon('check') + 'Write and export user stories together</li></ul>' + actions + '</div></div></div>';
    }, function (e) {
      view.innerHTML = '<div class="ui-wrap"><div class="jn"><div class="ui-empty">' + UI.icon('link') + '<h3>Invitation not found</h3><p>' + esc(e.message) + '</p>' +
        '<a class="ui-btn" href="#">Go to Prepsto</a></div></div></div>';
    });
  });
  document.addEventListener('click', function (e) {
    if (!(UI.current() && UI.current().name === 'join')) return;
    var token = UI.current().args[0];
    var a = e.target.closest('[data-auth]');
    if (a) { UI.after = '#join/' + token; UI.go.apply(null, a.getAttribute('data-auth').split('/')); return; }
    var y = e.target.closest('[data-yes]');
    if (y) { UI.busy(y, UI.api('accept_invite', token)).then(function (r) { UI.toast('Welcome to the team of ' + r.board, 'ok'); UI.go('inbox'); }); return; }
    if (e.target.closest('[data-no]')) UI.go('home');
  });
})();

/* ===== landing.html ===== */
(function () {
  var COPY = {
    eyebrow: '// customer feedback, structured',
    title: 'One link. Every piece of feedback. <em>Ready-to-build stories.</em>',
    lead: 'Drop a Prepsto link or one line of code on your site. Your users get a clean feedback panel; you get an inbox that sorts itself, and user stories with the customer\'s own words attached.',
    cta: 'Create your feedback link',
    proof: ['Free while in beta', 'No cookies on your site', 'Works with any website'],
    stepsTitle: 'From "this is broken" to a story your team can build',
    stepsLead: 'Prepsto sits between your users and your backlog.',
    steps: [['Drop in the panel', 'Share your link, or paste one script tag. A "Feedback" button appears and slides the panel in. Pick the colour, the question and the kinds of feedback you want.'],
            ['Triage in seconds', 'Everything lands in one inbox with the page, device and rating. Sentiment, urgency and themes are suggested for you. Drag cards across a board, tag, star, comment.'],
            ['Ship user stories', 'Select related feedback and draft a story: As a…, I want…, so that…, with acceptance criteria, team comments and client quotes. Export to Markdown, Gherkin, Jira or CSV.']],
    featuresTitle: 'Built for people who ship',
    features: [['code', 'One line to install', 'A script tag for a floating button, a plain link for emails and QR codes, or your own button.'],
               ['sparkle', 'Insights on arrival', 'Each message is read for sentiment, urgency and themes, and similar feedback is grouped. AI-ready from day one.'],
               ['board', 'List or board', 'Filter by link, kind, tag or rating, bulk-edit, or drag cards from New to Done.'],
               ['story', 'Real user stories', 'Persona, goal, benefit, testable acceptance criteria, estimates and priority, with the evidence attached.'],
               ['download', 'Export anywhere', 'Markdown, plain text, Gherkin, Jira markup, CSV, and a structured JSON bundle made for AI models.'],
               ['moon', 'Light and dark', 'A calm, technical interface that follows your system theme, on desktop and phone.']],
    makersTitle: 'For makers',
    makers: ['Several links: one per app, page or beta group', 'Close a panel or rotate its code in one click', 'Team comments that travel with the story'],
    usersTitle: 'For the people giving feedback',
    users: ['No account, no sign-up, ten seconds', 'Email is optional, only if they want a reply', 'A clear thank-you, so they know it landed'],
    faq: [['Is it free?', 'Yes, Prepsto is free while it is in beta. If we ever add paid plans, current links keep working and you will hear about it first.'],
          ['What does the code add to my site?', 'A small script that draws the button and, when clicked, opens the panel in a frame served by prepsto.com. It sets no cookies on your site and loads nothing until someone opens it.'],
          ['Who can read the feedback?', 'Only you, the owner of the link. The people sending feedback can\'t see each other\'s messages. Our Privacy & Terms page has the details.'],
          ['Does it use AI?', 'Today Prepsto uses a built-in rules engine for sentiment, themes and story drafts, so nothing leaves the app. It is built so an AI model can take over those jobs later, and you can already export an AI-ready JSON bundle.'],
          ['Can my users send feedback from their phone?', 'Yes. The panel is designed for phones first and works in any modern browser.'],
          ['Can I export my stories to Jira or Linear?', 'Copy Jira markup straight into an issue, import the CSV, or paste the Markdown into Linear, GitHub or Notion.']],
    bandTitle: 'Your next feature is already in someone\'s head.',
    bandLead: 'Give them a place to say it. It takes about a minute.'
  };

  function heroArt() {
    var I = UI.icon;
    return '<div class="lp-art" aria-hidden="true"><div class="win"><div class="bar"><i></i><i></i><i></i><span>your-app.com/editor</span></div>' +
      '<div class="site"><b></b><i></i><i style="width:85%"></i><i style="width:70%"></i><i style="width:90%"></i><i style="width:55%"></i></div>' +
      '<div class="panel"><h4>How can we make this better?</h4><div class="chips"><span>' + I('bug') + 'Bug</span><span class="on">' + I('bulb') + 'Idea</span><span>' + I('praise') + 'Praise</span></div>' +
      '<div class="msg">Would love a dark mode for the editor, I write late at night</div><div class="stars">★★★★<span style="color:var(--c-line)">★</span></div><div class="send">Send feedback</div></div>' +
      '<span class="fab">' + I('chat') + 'Feedback</span></div>' +
      '<div class="story"><div class="top"><span class="px-kind idea">' + I('story') + 'Story</span><span class="px-prio high">! high</span><span class="ui-spacer"></span><span class="mono small faint">3 client quotes</span></div>' +
      '<p>As a <b>night-time writer</b>, I want <b>a dark theme for the editor</b>, so that <b>my eyes can rest</b>.</p>' +
      '<ul><li>' + I('check') + 'Toggle in settings, remembered per device</li><li>' + I('check') + 'Follows the system theme by default</li></ul></div></div>';
  }

  UI.page('landing', { title: 'Customer feedback to user stories' }, function (view, ctx) {
    var me = ctx.me, C = COPY, esc = UI.esc;
    var primary = me ? '<a class="ui-btn primary lg" href="#home" data-go="home">Open your dashboard ' + UI.icon('arrow') + '</a><a class="ui-btn lg" href="#f/demo">' + UI.icon('chat') + 'Try the panel</a>'
      : '<a class="ui-btn primary lg" href="#auth/signup" data-go="auth/signup">' + esc(C.cta) + ' ' + UI.icon('arrow') + '</a>' +
        '<a class="ui-btn lg" href="#f/demo">' + UI.icon('chat') + 'Try the panel</a>';
    var snippet = '<script src="https://prepsto.com/_/theme/widget.js" data-prepsto="k7m2xq9" async></' + 'script>';
    view.innerHTML =
      '<section class="lp-hero"><div class="ui-wrap"><div>' +
        '<div class="eyebrow">' + esc(C.eyebrow) + '</div><h1>' + C.title + '</h1><p class="lp-lead">' + esc(C.lead) + '</p>' +
        '<div class="lp-cta">' + primary + '</div>' +
        '<div class="lp-proof">' + C.proof.map(function (p) { return '<span>' + UI.icon('check') + esc(p) + '</span>'; }).join('') + '</div>' +
        '<div class="lp-snip"><small>// the whole installation</small><pre class="px-code">' + PX.highlight(snippet) + '</pre></div>' +
      '</div>' + heroArt() + '</div></section>' +
      '<section class="lp-section" id="how"><div class="ui-wrap"><div class="lp-head"><div class="eyebrow">// how it works</div><h2>' + esc(C.stepsTitle) + '</h2><p>' + esc(C.stepsLead) + '</p></div>' +
        '<div class="lp-steps">' + C.steps.map(function (s, i) { return '<div class="lp-step"><span class="n">0' + (i + 1) + '</span><h3>' + esc(s[0]) + '</h3><p>' + esc(s[1]) + '</p></div>'; }).join('') + '</div></div></section>' +
      '<section class="lp-section"><div class="ui-wrap"><div class="lp-head"><div class="eyebrow">// features</div><h2>' + esc(C.featuresTitle) + '</h2></div>' +
        '<div class="lp-features">' + C.features.map(function (f) { return '<div class="lp-feature">' + UI.icon(f[0]) + '<h3>' + esc(f[1]) + '</h3><p>' + esc(f[2]) + '</p></div>'; }).join('') + '</div></div></section>' +
      '<section class="lp-section"><div class="ui-wrap"><div class="lp-two">' +
        [[C.makersTitle, C.makers, 'sliders'], [C.usersTitle, C.users, 'heart']].map(function (a) {
          return '<div class="ui-card lp-aud"><h3>' + esc(a[0]) + '</h3><ul>' + a[1].map(function (x) { return '<li>' + UI.icon(a[2]) + esc(x) + '</li>'; }).join('') + '</ul></div>';
        }).join('') + '</div></div></section>' +
      '<section class="lp-section"><div class="ui-wrap"><div class="lp-head"><div class="eyebrow">// faq</div><h2>Questions</h2></div><div class="lp-faq">' +
        C.faq.map(function (q) { return '<details><summary>' + esc(q[0]) + '</summary><p>' + esc(q[1]) + '</p></details>'; }).join('') + '</div></div></section>' +
      '<section class="lp-section" style="border-bottom:0"><div class="ui-wrap"><div class="lp-band"><div><h2>' + esc(C.bandTitle) + '</h2><p>' + esc(C.bandLead) + '</p></div>' +
        (me ? '<a class="ui-btn lg" href="#links" data-go="links">Get your link</a>' : '<a class="ui-btn lg" href="#auth/signup" data-go="auth/signup">' + esc(C.cta) + '</a>') +
      '</div></div></section>';
  });
})();

/* ===== links.html ===== */
(function () {
  var esc = UI.esc;
  var SWATCHES = ['#2b59ff', '#0c0e14', '#ff5a1f', '#0f8a5f', '#7c3aed', '#e11d74', '#0891b2'];
  var BLANK = { id: '', name: '', site_url: '', prompt: 'How can we make this better?', thanks: 'Thank you! We read every message.', label: 'Feedback', color: '#2b59ff',
    position: 'right', kinds: ['bug', 'idea', 'praise', 'question'], ask_email: true, ask_rating: true, is_open: true, slug: 'preview' };

  UI.page('links', { title: 'Links', nav: 'Links', icon: 'link', auth: 'user', order: 40 }, function (view, ctx) {
    var boards = [], cur = null, tab = UI.store.get('links.tab', 'script');
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:460px"></div></div>';

    function form(b) {
      var isNew = !b.id, ro = b.role === 'member';
      return '<form class="lk-form" data-form><fieldset class="lk-fs"' + (ro ? ' disabled' : '') + '>' +
        (ro ? '<p class="lk-ro">' + UI.icon('lock') + ' Shared with you by ' + esc(b.owner_name) + '. Only the owner can change these settings.</p>' : '') +
        '<label class="ui-field"><span>Name <em>(only you see it)</em></span><input type="text" name="name" value="' + esc(b.name) + '" maxlength="60" required placeholder="e.g. My app – beta"></label>' +
        '<label class="ui-field"><span>Website <em>(optional)</em></span><input type="url" name="site_url" value="' + esc(b.site_url) + '" maxlength="200" placeholder="https://myapp.com"></label>' +
        '<label class="ui-field"><span>The question at the top</span><input type="text" name="prompt" value="' + esc(b.prompt) + '" maxlength="140"></label>' +
        '<div class="ui-field"><span>Kinds of feedback <em>(the first one is picked when the panel opens)</em></span><div class="lk-kinds">' + b.kinds.concat(Object.keys(PX.KINDS).filter(function (k) { return b.kinds.indexOf(k) < 0; })).map(function (k) {
          return '<label><input type="checkbox" name="kind_' + k + '"' + (b.kinds.indexOf(k) >= 0 ? ' checked' : '') + '><span>' + UI.icon(PX.KINDS[k][1]) + PX.KINDS[k][0] + '</span></label>';
        }).join('') + '</div></div>' +
        '<div class="lk-two"><div class="ui-field"><span>Colour</span><div class="lk-swatches">' + SWATCHES.map(function (c) {
          return '<button type="button" data-color="' + c + '" style="background:' + c + '" class="' + (c === b.color ? 'on' : '') + '" aria-label="Colour ' + c + '"></button>';
        }).join('') + '<input type="color" name="color" value="' + esc(b.color) + '" aria-label="Any colour"></div></div>' +
          '<label class="ui-field"><span>Button text</span><input type="text" name="label" value="' + esc(b.label) + '" maxlength="24"></label></div>' +
        '<div class="lk-two"><label class="ui-field"><span>Button position</span><select name="position"><option value="right"' + (b.position === 'right' ? ' selected' : '') + '>Bottom right</option>' +
          '<option value="left"' + (b.position === 'left' ? ' selected' : '') + '>Bottom left</option></select></label>' +
          '<label class="ui-field"><span>Thank-you message</span><input type="text" name="thanks" value="' + esc(b.thanks) + '" maxlength="200"></label></div>' +
        '<div class="lk-switches"><label class="ui-check"><input type="checkbox" name="ask_rating"' + (b.ask_rating ? ' checked' : '') + '> Ask for a star rating</label>' +
          '<label class="ui-check"><input type="checkbox" name="ask_email"' + (b.ask_email ? ' checked' : '') + '> Ask for an email (optional for them)</label>' +
          '<label class="ui-check"><input type="checkbox" name="is_open"' + (b.is_open ? ' checked' : '') + '> Open: accepting feedback</label></div>' +
        (ro ? '' : '<div class="ui-row"><button class="ui-btn primary" type="submit">' + UI.icon('check') + (isNew ? 'Create link' : 'Save changes') + '</button>' +
          (isNew && boards.length ? '<button type="button" class="ui-btn ghost" data-cancel>Cancel</button>' : '') + '</div>') + '</fieldset></form>';
    }
    function install(b) {
      var T = [['script', 'Script', 'code'], ['link', 'Link', 'link'], ['button', 'Own button', 'sliders'], ['html', 'HTML link', 'external']];
      var body = '';
      if (tab === 'link') {
        body = '<div class="lk-url"><input type="text" readonly value="' + esc(PX.link(b)) + '" aria-label="Link"><button class="ui-btn" data-cp="link">' + UI.icon('copy') + 'Copy</button>' +
          '<a class="ui-btn" href="' + esc(PX.link(b)) + '" target="_blank" rel="noopener">' + UI.icon('external') + 'Open</a></div>' +
          '<p class="lk-step">Share it anywhere: an email, a QR code, your app\'s menu or help page. It opens the panel full screen.</p>';
      } else {
        var code = tab === 'script' ? PX.snippet(b) : tab === 'button' ? PX.snippet(b).replace(' async>', ' data-button="false" async>') + '\n\n<button data-prepsto-open>Give feedback</button>' : PX.anchor(b);
        body = '<pre class="px-code" data-code>' + PX.highlight(code) + '</pre><div class="ui-row" style="margin-top:10px"><button class="ui-btn sm primary" data-cp="code">' + UI.icon('copy') + 'Copy code</button></div>' +
          (tab === 'script' ? '<p class="lk-step"><b>01</b>Paste it before <code>&lt;/body&gt;</code> on every page (or in your site builder\'s "custom code").</p><p class="lk-step" style="margin-top:6px"><b>02</b>A "' + esc(b.label) + '" button appears; it slides the panel in. The page address is sent with each message.</p>'
            : tab === 'button' ? '<p class="lk-step">No floating button: any element with <code>data-prepsto-open</code> opens the panel, or call <code>Prepsto.open()</code> from your code.</p>'
            : '<p class="lk-step">A plain link for emails, docs or places where scripts aren\'t allowed.</p>');
        view._code = code;
      }
      return '<section class="ui-card lk-install"><h3 class="lk-h">' + UI.icon('code') + 'Put it on your site</h3><nav class="ui-tabs">' + T.map(function (t) {
        return '<button data-tab="' + t[0] + '" class="' + (tab === t[0] ? 'on' : '') + '">' + UI.icon(t[2]) + t[1] + '</button>'; }).join('') + '</nav>' + body + '</section>';
    }
    function preview(b) {
      return '<section class="lk-preview"><h3 class="lk-h">' + UI.icon('eye') + 'Live preview <span class="mono small faint" style="text-transform:none;letter-spacing:0">try it, nothing is sent</span></h3>' +
        '<div class="lk-browser"><div class="lk-bar"><i></i><i></i><i></i><span>' + esc(PX.host(b.site_url) || 'your-site.com') + '</span></div>' +
        '<div class="lk-stage ui-gridbg ' + esc(b.position) + '" data-stage><div class="fake"><i style="width:40%"></i><i style="width:75%"></i><i style="width:62%"></i></div>' +
        '<div class="panelbox" data-panel></div><span class="lk-fab" data-fab style="background:' + esc(b.color) + '">' + UI.icon('chat') + '<span>' + esc(b.label) + '</span></span></div></div></section>';
    }
    function draw() {
      var b = cur;
      view.innerHTML = '<div class="ui-wrap"><div class="ui-page-head"><div><div class="eyebrow">// feedback links</div><h1>Links</h1>' +
        '<p class="muted">Each link is one feedback panel: share the link, or add one line of code to your site for a floating button.</p></div></div>' +
        '<div class="lk-picker">' + boards.map(function (x) {
          return '<a class="lk-pick' + (b.id === x.id ? ' on' : '') + '" href="#links/' + esc(x.id) + '"><span class="dot" style="background:' + esc(x.color) + '"></span>' + esc(x.name) +
            ' <small>' + x.total + (x.new ? ' · ' + x.new + ' new' : '') + (x.is_open ? '' : ' · closed') + (x.role === 'member' ? ' · shared' : x.team > 1 ? ' · team of ' + x.team : '') + '</small></a>';
        }).join('') + '<a class="lk-pick add' + (!b.id ? ' on' : '') + '" href="#links/new">' + UI.icon('plus') + 'New link</a></div>' +
        '<div class="lk-grid"><div>' +
          (b.is_sample && b.role === 'owner' ? '<div class="lk-sample">' + UI.icon('info') + ' This sample link came with your account so you can explore. Delete it whenever you like.</div>' : '') +
          '<section class="ui-card"><h3 class="lk-h">' + UI.icon('sliders') + (b.id ? 'Panel settings' : 'New feedback link') + '</h3>' + form(b) + '</section>' +
          (b.id ? install(b) + '<section class="ui-card" data-team><h3 class="lk-h">' + UI.icon('users') + 'Team</h3><div class="ui-skel" style="min-height:60px"></div></section>' +
            '<section class="ui-card"><h3 class="lk-h">' + UI.icon('shield') + 'Manage</h3><div class="ui-row" style="margin-bottom:12px"><span class="mono small muted">code: ' + esc(b.slug) + ' · created ' + esc(UI.fmtDate(b.created)) + ' · ' + UI.plural(b.total, 'message') + '</span></div>' +
            '<div class="lk-danger"><a class="ui-btn sm" href="#inbox" data-inbox>' + UI.icon('inbox') + 'See its feedback</a>' +
            (b.role === 'owner' ? '<button class="ui-btn sm" data-newcode>' + UI.icon('refresh') + 'New code</button>' : '') +
            '<button class="ui-btn sm" data-reanalyze>' + UI.icon('sparkle') + 'Re-run insights</button>' +
            (b.role === 'owner' ? '<button class="ui-btn sm danger" data-delete>' + UI.icon('trash') + 'Delete link</button>' : '') + '</div>' +
            (b.role === 'owner' ? '<p class="ui-hint">A new code stops the old link and snippet working (handy if spam finds it). Deleting removes all its feedback and stories.</p>' : '') + '</section>' : '') +
        '</div><div>' + preview(b) + '</div></div></div>';
      paint();
      if (b.id) team();
    }
    function team() {
      var box = view.querySelector('[data-team]'), id = cur.id;
      return UI.apiQuiet('list_team', id).then(function (d) {
        if (!box.isConnected || cur.id !== id) return;
        box.innerHTML = '<h3 class="lk-h">' + UI.icon('users') + 'Team <span class="mono small faint" style="text-transform:none;letter-spacing:0">' + UI.plural(d.people.filter(function (p) { return p.status === 'active'; }).length, 'person', 'people') + '</span></h3>' +
          '<div class="lk-team">' + d.people.map(function (p) {
            var pending = p.status === 'invited';
            return '<div class="lk-person' + (pending ? ' pending' : '') + '" data-member="' + esc(p.id || '') + '"><span class="ui-avatar">' + (pending ? UI.icon('mail') : esc(UI.initials(p.name))) + '</span>' +
              '<div class="grow"><b>' + esc(pending ? p.email : p.name) + (p.me ? ' <span class="faint">(you)</span>' : '') + '</b><span>' +
              (pending ? 'invited ' + esc(UI.ago(p.created)) + ' · not joined yet' : p.role + (p.email && !p.me ? ' · ' + esc(p.email) : '')) + '</span></div>' +
              (pending && d.is_owner ? '<button class="ui-btn sm" data-invlink="' + esc(p.token) + '">' + UI.icon('link') + 'Copy invite link</button>' : '') +
              (p.role !== 'owner' && (d.is_owner || p.me) ? '<button class="ui-btn sm ghost" data-remove="' + esc(p.id) + '" data-name="' + esc(pending ? p.email : p.name) + '"' + (p.me ? ' data-leave' : '') + '>' +
                (p.me ? 'Leave' : pending ? 'Cancel' : 'Remove') + '</button>' : '') + '</div>';
          }).join('') + '</div>' +
          (d.is_owner ? '<form class="lk-invite" data-inviteform><input type="email" name="email" placeholder="teammate@company.com" required aria-label="Teammate\'s email">' +
            '<button class="ui-btn primary" type="submit">' + UI.icon('plus') + 'Invite</button></form>' +
            '<p class="ui-hint">They see the invitation when they sign in with that email. Prepsto doesn\'t send email: copy the invite link and send it yourself to be sure. Teammates can triage, assign, comment and write stories; only you change settings and the team.</p>'
            : '<p class="ui-hint">Type @ in a comment to mention a teammate. Only ' + esc(cur.owner_name) + ' can invite people.</p>');
      });
    }
    function values() {
      var f = view.querySelector('[data-form]'), v = UI.formData(f);
      v.kinds = Array.prototype.map.call(f.querySelectorAll('.lk-kinds input:checked'), function (i) { return i.name.slice(5); });
      return { name: v.name, site_url: v.site_url, prompt: v.prompt, thanks: v.thanks, label: v.label, color: v.color, position: v.position,
        kinds: v.kinds, ask_email: v.ask_email, ask_rating: v.ask_rating, is_open: v.is_open };
    }
    function paint() {  // redraw the preview from the form, without saving
      var v = Object.assign({}, cur, cur.role === 'member' ? {} : values());
      v.name = v.name || 'Your app'; v.prompt = v.prompt || BLANK.prompt; v.label = v.label || 'Feedback';
      if (!v.kinds.length) v.kinds = ['idea'];
      var stage = view.querySelector('[data-stage]');
      stage.className = 'lk-stage ui-gridbg ' + v.position;
      var fab = view.querySelector('[data-fab]'); fab.style.background = v.color; fab.querySelector('span').textContent = v.label;
      var box = view.querySelector('[data-panel]'), fresh = box.cloneNode(false);
      box.parentNode.replaceChild(fresh, box);
      PX.panel(fresh, v, { preview: true, onClose: function () {} });
      view.querySelectorAll('[data-color]').forEach(function (s) { s.classList.toggle('on', s.getAttribute('data-color') === v.color); });
    }
    function pick() {
      var a = ctx.args[0];
      if (a === 'new' || !boards.length) cur = Object.assign({}, BLANK);
      else cur = boards.filter(function (x) { return x.id === a; })[0] || boards.filter(function (x) { return !x.is_sample; })[0] || boards[0];
    }
    function load() { return UI.api('list_boards').then(function (d) { boards = d.boards; pick(); draw(); }); }

    var t;
    view.addEventListener('input', function (e) { if (e.target.closest('[data-form]')) { clearTimeout(t); t = setTimeout(paint, 120); } });
    view.addEventListener('change', function (e) { if (e.target.closest('[data-form]')) paint(); });
    view.addEventListener('click', function (e) {
      var x = e.target;
      var c = x.closest('[data-color]');
      if (c) { view.querySelector('[name=color]').value = c.getAttribute('data-color'); paint(); return; }
      var tb = x.closest('[data-tab]');
      if (tb) { tab = tb.getAttribute('data-tab'); UI.store.set('links.tab', tab); var sec = view.querySelector('.lk-install'); sec.outerHTML = install(cur); return; }
      var cp = x.closest('[data-cp]');
      if (cp) { PX.copy(cp.getAttribute('data-cp') === 'link' ? PX.link(cur) : view._code, cp.getAttribute('data-cp') === 'link' ? 'Link copied' : 'Code copied'); return; }
      if (x.closest('[data-cancel]')) { UI.go('links'); return; }
      var il = x.closest('[data-invlink]');
      if (il) { PX.copy(PX.base() + '#join/' + il.getAttribute('data-invlink'), 'Invite link copied'); return; }
      var rm = x.closest('[data-remove]');
      if (rm) {
        var leave = rm.hasAttribute('data-leave');
        UI.confirm({ title: leave ? 'Leave "' + cur.name + '"?' : 'Remove ' + rm.getAttribute('data-name') + '?',
          text: leave ? 'You lose access to its feedback and stories. The owner can invite you again.' : 'They lose access to this link\'s feedback and stories. Their comments stay.',
          ok: leave ? 'Leave' : 'Remove', danger: true }).then(function (yes) {
          if (!yes) return;
          UI.api('remove_member', cur.id, rm.getAttribute('data-remove')).then(function (r) {
            if (r.left) { UI.toast('You left the team', 'ok'); UI.go('links'); } else { UI.toast('Removed', 'ok'); team(); }
          });
        });
        return;
      }
      if (x.closest('[data-inbox]')) { e.preventDefault(); var fl = UI.store.get('inbox.filters', {}) || {}; fl.board = cur.id; fl.status = 'open'; UI.store.set('inbox.filters', fl); UI.go('inbox'); return; }
      if (x.closest('[data-newcode]')) {
        UI.confirm({ title: 'Make a new code?', text: 'The current link and snippet stop working right away. You\'ll need to update your site with the new code.', ok: 'New code', danger: true }).then(function (yes) {
          if (yes) UI.api('new_board_code', cur.id).then(function (r) { UI.toast('New code: ' + r.board.slug, 'ok'); load(); });
        });
        return;
      }
      if (x.closest('[data-reanalyze]')) { UI.busy(x.closest('button'), UI.api('reanalyze_board', cur.id)).then(function (r) { UI.toast('Insights updated for ' + UI.plural(r.count, 'message'), 'ok'); }); return; }
      if (x.closest('[data-delete]')) {
        UI.confirm({ title: 'Delete "' + cur.name + '"?', text: 'Its ' + UI.plural(cur.total, 'message') + ', stories and comments are deleted for good, and the link stops working.', ok: 'Delete link', danger: true }).then(function (yes) {
          if (yes) UI.api('delete_board', cur.id).then(function () { UI.toast('Link deleted', 'ok'); UI.go('links'); });
        });
      }
    });
    view.addEventListener('submit', function (e) {
      if (e.target.matches('[data-inviteform]')) {
        e.preventDefault();
        var f = e.target;
        UI.busy(f.querySelector('button'), UI.api('invite_member', cur.id, UI.formData(f).email)).then(function (r) {
          PX.copy(PX.base() + '#join/' + r.member.token, 'Invited ' + r.member.email + '. Invite link copied');
          team();
        });
        return;
      }
      if (!e.target.matches('[data-form]')) return;
      e.preventDefault();
      var isNew = !cur.id;
      UI.busy(e.target.querySelector('[type=submit]'), UI.api('save_board', cur.id || null, values())).then(function (r) {
        UI.toast(isNew ? 'Link created. Now put it on your site!' : 'Saved', 'ok');
        if (isNew) { tab = 'script'; UI.go('links', r.board.id); } else load();
      });
    });
    return load();
  });
})();

/* ===== profile.html ===== */
(function () {
  var esc = UI.esc;
  UI.page('profile', { title: 'Your profile', auth: 'user' }, function (view, ctx) {
    var me = ctx.me;
    view.innerHTML = '<div class="ui-wrap ui-narrow"><div class="pf-head"><span class="ui-avatar">' + esc(UI.initials(me.name)) + '</span>' +
      '<div><h1>' + esc(me.name) + '</h1><div class="muted">' + esc(me.email) + (me.joined ? ' · member since ' + esc(UI.fmtDate(me.joined, { month: 'long', year: 'numeric' })) : '') + '</div></div></div>' +
      '<div class="pf-grid"><form class="ui-card ui-stack" data-name><h3>Your name</h3><label class="ui-field"><span>Shown to other people</span>' +
      '<input type="text" name="name" value="' + esc(me.name) + '" maxlength="60" required></label><button class="ui-btn primary" type="submit">Save</button></form>' +
      '<div class="ui-card ui-stack"><h3>Appearance</h3><p class="muted small">Follow your device, or pick one.</p><div data-theme-box></div>' +
      '<h3 style="margin-top:22px">Password</h3><p class="muted small">We\'ll email you a link to choose a new one.</p>' +
      '<button class="ui-btn" data-reset>' + UI.icon('mail') + 'Email me a reset link</button></div></div>' +
      '<div class="ui-card" style="margin-top:16px"><div class="pf-links">' +
      (me.is_admin ? '<a href="#admin" data-go="admin">' + UI.icon('shield') + 'Admin</a>' : '') +
      '<button data-feedback>' + UI.icon('chat') + 'Send feedback</button>' +
      '<button data-lk-open="overview">' + UI.icon('lock') + 'Privacy &amp; Terms, and your data</button>' +
      '<button data-signout-here>' + UI.icon('logout') + 'Sign out</button></div></div></div>';
    function themeBox() {
      var t = UI.theme();
      view.querySelector('[data-theme-box]').innerHTML = '<div class="ui-seg">' + [['auto', 'Auto'], ['light', 'Light'], ['dark', 'Dark']].map(function (o) {
        return '<button type="button" data-theme-pick="' + o[0] + '" class="' + (t === o[0] ? 'on' : '') + '">' + o[1] + '</button>';
      }).join('') + '</div>';
    }
    themeBox();
    view.addEventListener('click', function (e) {
      var t = e.target.closest('[data-theme-pick]');
      if (t) { UI.setTheme(t.getAttribute('data-theme-pick')); themeBox(); UI.renderChrome(); return; }
      if (e.target.closest('[data-reset]')) {
        UI.busy(e.target.closest('[data-reset]'), UI.auth('reset', { email: me.email })).then(function (r) { UI.toast(r.message, 'ok'); });
      }
      if (e.target.closest('[data-signout-here]')) UI.auth('logout');
    });
    view.querySelector('[data-name]').addEventListener('submit', function (e) {
      e.preventDefault();
      var v = UI.formData(e.target);
      UI.busy(e.target.querySelector('[type=submit]'), UI.api('update_profile', v.name)).then(function (r) {
        UI.setMe(r.me); ctx.me = r.me; UI.toast('Saved', 'ok');
        view.querySelector('.pf-head h1').textContent = r.me.name;
      });
    });
  });
})();

/* ===== stories.html ===== */
(function () {
  var esc = UI.esc;
  PX.storyState = function (s) { return '<span class="st-state ' + esc(s) + '">' + esc(PX.label(PX.STORY_STATUSES, s)) + '</span>'; };

  UI.page('stories', { title: 'Stories', nav: 'Stories', icon: 'story', auth: 'user', order: 30 }, function (view, ctx) {
    var status = UI.store.get('stories.status', ''), boardId = UI.store.get('stories.board', '');
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:300px"></div></div>';
    function card(s) {
      return '<a class="ui-card hover st-card" href="#story/' + esc(s.id) + '"><div class="ui-row">' + PX.storyState(s.status) + PX.prio(s.priority) +
        '<span class="ui-spacer"></span>' + (s.points != null ? '<span class="st-pts">' + s.points + ' pts</span>' : '') + '</div>' +
        '<h3>' + esc(s.title) + '</h3>' +
        (s.persona || s.goal ? '<p class="as">As a <b>' + esc(s.persona || '…') + '</b>, I want <b>' + esc(s.goal || '…') + '</b>' + (s.benefit ? ', so that ' + esc(s.benefit) : '') + '.</p>' : '<p class="as faint">No story text yet.</p>') +
        '<div class="foot"><span class="mono small muted">' + UI.icon('chat') + ' ' + s.feedback_count + ' client · ' + s.comment_count + ' team</span>' +
        s.kinds.map(function (k) { return PX.kind(k); }).join('') + '<span class="ui-spacer"></span><span class="mono small faint">' + esc(s.board) + '</span></div></a>';
    }
    function draw(d) {
      var total = Object.keys(d.counts).reduce(function (a, k) { return a + d.counts[k]; }, 0);
      view.innerHTML = '<div class="ui-wrap"><div class="ui-page-head"><div><div class="eyebrow">// user stories</div><h1>Stories</h1>' +
        '<p class="muted">Feedback turned into "As a…, I want…, so that…", with acceptance criteria, comments and the client\'s own words. Export to your tracker.</p></div>' +
        '<button class="ui-btn primary" data-new>' + UI.icon('plus') + 'New story</button></div>' +
        '<div class="st-filters"><div class="ui-seg">' + [['', 'All']].concat(PX.STORY_STATUSES).map(function (s) {
          return '<button data-st="' + s[0] + '" class="' + (status === s[0] ? 'on' : '') + '">' + s[1] + ' <span class="faint">' + (s[0] ? d.counts[s[0]] || 0 : total) + '</span></button>';
        }).join('') + '</div>' +
        (d.boards.length > 1 ? '<select data-board aria-label="Link"><option value="">All links</option>' + d.boards.map(function (b) {
          return '<option value="' + esc(b.id) + '"' + (b.id === boardId ? ' selected' : '') + '>' + esc(b.name) + '</option>'; }).join('') + '</select>' : '') + '</div>' +
        (d.stories.length ? '<div class="st-grid">' + d.stories.map(card).join('') + '</div>'
          : '<div class="ui-empty">' + UI.icon('story') + '<h3>No stories ' + (status ? 'here' : 'yet') + '</h3><p>Select feedback in the Inbox and choose "Draft a story", or start a blank one.</p>' +
            '<a class="ui-btn primary" href="#inbox">Go to the inbox</a></div>') + '</div>';
      view._boards = d.boards;
    }
    function load() { return UI.api('list_stories', boardId || null, status || null).then(draw); }
    view.addEventListener('click', function (e) {
      var s = e.target.closest('[data-st]');
      if (s) { status = s.getAttribute('data-st'); UI.store.set('stories.status', status); load(); return; }
      if (e.target.closest('[data-new]')) {
        var bs = view._boards;
        if (!bs.length) { UI.toast('Create a feedback link first.', 'error'); UI.go('links'); return; }
        var m = UI.modal('<h2>New story</h2><form class="ui-stack" data-newform><label class="ui-field"><span>Which link is it for?</span><select name="board">' +
          bs.map(function (b) { return '<option value="' + esc(b.id) + '"' + (b.id === boardId ? ' selected' : '') + '>' + esc(b.name) + '</option>'; }).join('') + '</select></label>' +
          '<p class="ui-hint">Tip: select feedback in the Inbox and choose "Draft a story" to have it drafted for you.</p>' +
          '<div class="ui-row end"><button type="button" class="ui-btn ghost" data-close>Cancel</button><button class="ui-btn primary">Create</button></div></form>');
        m.el.querySelector('form').addEventListener('submit', function (ev) {
          ev.preventDefault();
          UI.busy(ev.target.querySelector('.primary'), UI.api('create_story', UI.formData(ev.target).board, [])).then(function (r) { m.close(); UI.go('story', r.story.id); });
        });
      }
    });
    view.addEventListener('change', function (e) { if (e.target.matches('[data-board]')) { boardId = e.target.value; UI.store.set('stories.board', boardId); load(); } });
    return load();
  });
})();

/* ===== story.html ===== */
(function () {
  var esc = UI.esc;
  var POINTS = [null, 1, 2, 3, 5, 8, 13, 21];

  /* ------------------------------------------------------------------ exports (pure functions of a story) */
  function stars(n) { return n ? new Array(n + 1).join('★') + new Array(6 - n).join('☆') : ''; }
  function day(iso) { return iso ? iso.slice(0, 10) : ''; }
  function sentence(s) { return 'As a ' + (s.persona || '…') + ', I want ' + (s.goal || '…') + (s.benefit ? ', so that ' + s.benefit : '') + '.'; }
  function meta(s) { return [PX.label(PX.STORY_STATUSES, s.status), s.priority ? 'priority ' + s.priority : '', s.points != null ? s.points + ' pts' : '', s.board].filter(Boolean); }
  var EXPORTS = {
    markdown: ['Markdown', 'md', function (s) {
      var L = ['# ' + s.title, '', '_' + meta(s).join(' · ') + '_', '', '## User story', '', 'As a **' + (s.persona || '…') + '**, I want **' + (s.goal || '…') + '**' + (s.benefit ? ', so that **' + s.benefit + '**' : '') + '.', ''];
      if (s.acceptance.length) L.push('## Acceptance criteria', '', s.acceptance.map(function (a) { return '- [ ] ' + a; }).join('\n'), '');
      if (s.notes) L.push('## Notes', '', s.notes, '');
      if (s.comments.length) L.push('## Supporting comments', '', s.comments.map(function (c) { return '- **' + c.author + '** (' + day(c.created) + '): ' + c.body.replace(/\n/g, ' '); }).join('\n'), '');
      if (s.entries.length) {
        L.push('## Client feedback (' + s.entries.length + ')', '');
        s.entries.forEach(function (e) {
          L.push('> ' + e.message.replace(/\n/g, '\n> '), '>', '> — ' + [PX.who(e), e.kind_label, stars(e.rating), day(e.created), e.page_url].filter(Boolean).join(' · '));
          (e.comments || []).forEach(function (c) { L.push('', '  - _' + c.author + ':_ ' + c.body.replace(/\n/g, ' ')); });
          L.push('');
        });
      }
      return L.join('\n').trim() + '\n';
    }],
    text: ['Plain text', 'txt', function (s) {
      var L = [s.title.toUpperCase(), meta(s).join(' | '), '', sentence(s), ''];
      if (s.acceptance.length) L.push('Acceptance criteria:', s.acceptance.map(function (a, i) { return '  ' + (i + 1) + '. ' + a; }).join('\n'), '');
      if (s.notes) L.push('Notes:', s.notes, '');
      if (s.comments.length) L.push('Supporting comments:', s.comments.map(function (c) { return '  - ' + c.author + ': ' + c.body; }).join('\n'), '');
      if (s.entries.length) L.push('Client feedback:', s.entries.map(function (e) { return '  "' + e.message + '"\n    - ' + [PX.who(e), e.kind_label, e.rating ? e.rating + '/5' : '', day(e.created)].filter(Boolean).join(', '); }).join('\n'));
      return L.join('\n').trim() + '\n';
    }],
    gherkin: ['Gherkin', 'feature', function (s) {
      var L = ['Feature: ' + s.title, '  As a ' + (s.persona || '…'), '  I want ' + (s.goal || '…'), s.benefit ? '  So that ' + s.benefit : null, ''].filter(function (x) { return x !== null; });
      L.push('  # Based on ' + s.entries.length + ' piece' + (s.entries.length === 1 ? '' : 's') + ' of client feedback', '');
      s.acceptance.forEach(function (a) {
        var g = /given (.+?),? when (.+?),? then (.+)/i.exec(a);
        L.push('  Scenario: ' + (g ? a.split(/,? when /i)[0].replace(/^given /i, '') : a));
        if (g) L.push('    Given ' + g[1], '    When ' + g[2], '    Then ' + g[3]);
        else L.push('    Then ' + a.charAt(0).toLowerCase() + a.slice(1));
        L.push('');
      });
      return L.join('\n').trim() + '\n';
    }],
    jira: ['Jira', 'txt', function (s) {
      var L = ['h2. ' + s.title, '', '*As a* ' + (s.persona || '…') + ', *I want* ' + (s.goal || '…') + (s.benefit ? ', *so that* ' + s.benefit : '') + '.', ''];
      if (s.acceptance.length) L.push('h3. Acceptance criteria', s.acceptance.map(function (a) { return '* ' + a; }).join('\n'), '');
      if (s.notes) L.push('h3. Notes', s.notes, '');
      if (s.comments.length) L.push('h3. Supporting comments', s.comments.map(function (c) { return '* *' + c.author + ':* ' + c.body.replace(/\n/g, ' '); }).join('\n'), '');
      if (s.entries.length) { L.push('h3. Client feedback (' + s.entries.length + ')'); s.entries.forEach(function (e) { L.push('{quote}' + e.message + '{quote}', '_' + [PX.who(e), e.kind_label, e.rating ? e.rating + '/5' : '', day(e.created)].filter(Boolean).join(' · ') + '_', ''); }); }
      return L.join('\n').trim() + '\n';
    }],
    csv: ['CSV', 'csv', function (s) {
      function q(v) { v = v == null ? '' : String(v); return '"' + v.replace(/"/g, '""') + '"'; }
      var desc = sentence(s) + '\n\nAcceptance criteria:\n' + s.acceptance.map(function (a) { return '- ' + a; }).join('\n') +
        (s.notes ? '\n\nNotes:\n' + s.notes : '') + (s.entries.length ? '\n\nClient feedback:\n' + s.entries.map(function (e) { return '"' + e.message + '" (' + PX.who(e) + ')'; }).join('\n') : '');
      var labels = {}; s.entries.forEach(function (e) { e.tags.concat((e.ai || {}).tags || []).forEach(function (t) { labels[t.replace(/\s+/g, '-')] = 1; }); });
      return ['Summary,Description,Issue Type,Priority,Story Points,Labels,Status', [q(s.title), q(desc), q('Story'), q(s.priority), q(s.points), q(Object.keys(labels).join(' ')), q(PX.label(PX.STORY_STATUSES, s.status))].join(',')].join('\n') + '\n';
    }],
    json: ['AI-ready JSON', 'json', function (s, bundle) {
      var b = JSON.parse(JSON.stringify(bundle));
      b.story = { title: s.title, persona: s.persona, goal: s.goal, benefit: s.benefit, acceptance: s.acceptance, notes: s.notes, priority: s.priority, status: s.status, points: s.points };
      b.supporting_comments = s.comments.map(function (c) { return { author: c.author, body: c.body }; });
      return JSON.stringify(b, null, 2) + '\n';
    }]
  };
  PX.EXPORTS = EXPORTS;

  UI.page('story', { title: 'Story', auth: 'user' }, function (view, ctx) {
    var id = ctx.args[0], S = null, bundle = null, pool = [], team = [], provider = 'rules', timer = null, saving = null, dirty = false;
    view.innerHTML = '<div class="ui-wrap"><div class="ui-skel" style="height:480px"></div></div>';

    function opt(v, label, cur) { return '<option value="' + esc(v == null ? '' : v) + '"' + (String(v == null ? '' : v) === String(cur == null ? '' : cur) ? ' selected' : '') + '>' + esc(label) + '</option>'; }
    function acRow(a) { return '<div class="sy-ac-row"><input type="text" data-ac value="' + esc(a) + '" maxlength="300" placeholder="Given…, when…, then…"><button class="ui-btn ghost icon" data-ac-del aria-label="Remove">' + UI.icon('x') + '</button></div>'; }
    function quote(e) {
      return '<div class="sy-q"><div class="ui-row">' + PX.kind(e.kind) + PX.stars(e.rating) + '<span class="small muted">' + esc(PX.who(e)) + ' · ' + esc(UI.ago(e.created)) + '</span>' +
        '<span class="ui-spacer"></span><button class="ui-btn ghost icon" data-unlink="' + esc(e.id) + '" title="Unlink from this story" aria-label="Unlink">' + UI.icon('x') + '</button></div>' +
        '<blockquote>' + esc(e.message) + '</blockquote>' +
        (e.comments || []).map(function (c) { return '<p class="sub">' + UI.icon('chat') + ' <b>' + esc(c.author) + ':</b> ' + esc(c.body) + '</p>'; }).join('') + '</div>';
    }
    function draw() {
      var s = S;
      view.innerHTML = '<div class="ui-wrap">' +
        '<div class="sy-top"><a class="ui-btn ghost sm" href="#stories">' + UI.icon('back') + 'Stories</a><span class="mono small faint">' + esc(s.board) + ' · by ' + esc(s.author || '') + '</span><span class="ui-spacer"></span>' +
          '<span class="saved" data-saved>Saved</span>' +
          '<select data-k="status" aria-label="Status">' + PX.STORY_STATUSES.map(function (x) { return opt(x[0], x[1], s.status); }).join('') + '</select>' +
          '<button class="ui-btn primary" data-export>' + UI.icon('download') + 'Export</button>' +
          '<button class="ui-btn icon" data-more aria-label="More">' + UI.icon('more') + '</button></div>' +
        '<div class="sy-grid"><div>' +
          '<section class="ui-card"><textarea class="sy-title" data-k="title" rows="1" maxlength="140" aria-label="Title" placeholder="Story title">' + esc(s.title) + '</textarea>' +
            '<p class="mono small faint" style="margin:6px 0 18px">' + (s.source === 'manual' ? 'written by hand' : 'drafted by the ' + (s.source === 'ai' ? 'AI' : 'rules engine')) + ' · updated ' + esc(UI.ago(s.updated)) + '</p>' +
            '<div class="sy-sentence"><label><span>As a</span><input type="text" data-k="persona" value="' + esc(s.persona) + '" maxlength="120" placeholder="who? e.g. returning customer"></label>' +
            '<label><span>I want</span><textarea data-k="goal" rows="2" maxlength="400" placeholder="what do they want to do?" style="min-height:64px">' + esc(s.goal) + '</textarea></label>' +
            '<label><span>So that</span><textarea data-k="benefit" rows="2" maxlength="400" placeholder="why does it matter to them?" style="min-height:64px">' + esc(s.benefit) + '</textarea></label></div>' +
            '<p class="sy-preview" data-sentence></p></section>' +
          '<section class="ui-card"><h3 class="sy-h">' + UI.icon('check') + 'Acceptance criteria <button class="ui-btn sm" data-ac-add>' + UI.icon('plus') + 'Add</button></h3>' +
            '<div class="sy-ac" data-aclist>' + (s.acceptance.length ? s.acceptance : ['']).map(acRow).join('') + '</div>' +
            '<p class="ui-hint">Write each one so it can be tested: "Given…, when…, then…" becomes a Gherkin scenario on export.</p></section>' +
          '<section class="ui-card"><h3 class="sy-h">' + UI.icon('sliders') + 'Details</h3><div class="sy-details">' +
            '<label class="ui-field"><span>Priority</span><select data-k="priority">' + PX.PRIORITIES.map(function (p) { return opt(p[0], p[1], s.priority); }).join('') + '</select></label>' +
            '<label class="ui-field"><span>Estimate</span><select data-k="points">' + POINTS.map(function (p) { return opt(p, p == null ? 'Not estimated' : p + ' points', s.points); }).join('') + '</select></label></div>' +
            '<label class="ui-field" style="margin-top:12px"><span>Notes</span><textarea data-k="notes" maxlength="4000" placeholder="Context, links, open questions">' + esc(s.notes) + '</textarea></label></section>' +
        '</div><div>' +
          '<section class="ui-card"><h3 class="sy-h">' + UI.icon('chat') + 'Client feedback · ' + s.entries.length + ' <button class="ui-btn sm" data-addfb>' + UI.icon('plus') + 'Add</button></h3>' +
            (s.entries.length ? '<div class="sy-fb">' + s.entries.map(quote).join('') + '</div>' : '<p class="muted small" style="margin:0">No feedback linked yet. Add some to ground the story in what customers said.</p>') + '</section>' +
          '<section class="ui-card"><h3 class="sy-h">' + UI.icon('users') + 'Supporting comments · ' + s.comments.length + '</h3><div class="px-comments">' +
            (s.comments.length ? s.comments.map(PX.comment).join('') : '<p class="muted small" style="margin:0">Decisions, findings and context from your team.</p>') + '</div>' +
            '<form class="px-addc" data-commentform><textarea name="body" placeholder="Add a comment. Type @ to mention" maxlength="2000"></textarea><button class="ui-btn sm primary" type="submit">Post</button></form></section>' +
          '<section class="ui-card sy-ai"><h3 class="sy-h">' + UI.icon('sparkle') + 'Assist <span class="ui-badge">' + (provider === 'ai' ? 'AI' : 'rules engine') + '</span></h3>' +
            '<p class="muted">Redraft the story from its linked feedback. Today this uses Prepsto\'s built-in rules; it\'s built so an AI model can take over the same job.</p>' +
            '<div class="ui-row"><button class="ui-btn sm" data-redraft' + (s.entries.length ? '' : ' disabled') + '>' + UI.icon('wand') + 'Redraft from feedback</button>' +
            '<button class="ui-btn sm ghost" data-export-ai>' + UI.icon('code') + 'AI-ready JSON</button></div></section>' +
        '</div></div></div>';
      sentenceNow(); fit();
      PX.mentions(view.querySelector('[data-commentform] textarea'), team);
    }
    function collect() {
      var v = {};
      view.querySelectorAll('[data-k]').forEach(function (el) { v[el.getAttribute('data-k')] = el.value; });
      v.points = v.points === '' ? null : +v.points;
      v.acceptance = Array.prototype.map.call(view.querySelectorAll('[data-ac]'), function (i) { return i.value.trim(); }).filter(Boolean);
      return v;
    }
    function current() { var v = collect(); var s = Object.assign({}, S, v); return s; }
    function sentenceNow() { var el = view.querySelector('[data-sentence]'); if (!el) return; var v = collect(); el.innerHTML = 'As a <b>' + esc(v.persona || '…') + '</b>, I want <b>' + esc(v.goal || '…') + '</b>' + (v.benefit ? ', so that <b>' + esc(v.benefit) + '</b>' : '') + '.'; }
    function fit() { var t = view.querySelector('.sy-title'); if (t) { t.style.height = 'auto'; t.style.height = t.scrollHeight + 'px'; } }
    function mark(state) { var el = view.querySelector('[data-saved]'); if (el) { el.textContent = state; el.classList.toggle('dirty', state !== 'Saved'); } }
    function save() {
      clearTimeout(timer); timer = null;
      if (!dirty) return Promise.resolve();
      var v = collect();
      if ((v.title || '').trim().length < 2) { mark('Title needed'); return Promise.resolve(); }
      dirty = false; mark('Saving…');
      saving = UI.apiQuiet('save_story', id, v).then(function (r) { Object.assign(S, v, { updated: r.story.updated }); mark('Saved'); }, function (e) { dirty = true; mark('Not saved'); UI.toast(e.message, 'error'); });
      return saving;
    }
    function changed() { dirty = true; mark('Editing…'); clearTimeout(timer); timer = setTimeout(save, 900); sentenceNow(); }
    function load() {
      return UI.api('get_story', id).then(function (r) { S = r.story; bundle = r.bundle; pool = r.pool; provider = r.provider; team = r.team || []; document.title = S.title + ' · Prepsto'; draw(); });
    }
    function reloadKeep() { return save().then(load); }

    function exportModal(fmt) {
      save();
      var s = current(), cur = fmt || UI.store.get('export.fmt', 'markdown');
      var m = UI.modal('<h2>Export story</h2><p class="muted small">Story, acceptance criteria, supporting comments and client feedback, ready for your tracker or an AI model.</p>' +
        '<div class="ex-tabs" role="tablist">' + Object.keys(EXPORTS).map(function (k) { return '<button data-fmt="' + k + '">' + EXPORTS[k][0] + '</button>'; }).join('') + '</div>' +
        '<pre class="px-code ex-out" data-out></pre><div class="ui-row end" style="margin-top:14px"><button class="ui-btn" data-dl>' + UI.icon('download') + 'Download</button>' +
        '<button class="ui-btn primary" data-cp>' + UI.icon('copy') + 'Copy</button></div>', { wide: true });
      function show() {
        m.el.querySelectorAll('[data-fmt]').forEach(function (b) { b.classList.toggle('on', b.getAttribute('data-fmt') === cur); });
        m.el.querySelector('[data-out]').textContent = EXPORTS[cur][2](s, bundle);
      }
      m.el.addEventListener('click', function (e) {
        var b = e.target.closest('[data-fmt]');
        if (b) { cur = b.getAttribute('data-fmt'); UI.store.set('export.fmt', cur); show(); }
        var slugName = (s.title || 'story').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50) || 'story';
        if (e.target.closest('[data-cp]')) PX.copy(EXPORTS[cur][2](s, bundle), EXPORTS[cur][0] + ' copied');
        if (e.target.closest('[data-dl]')) PX.download(slugName + '.' + EXPORTS[cur][1], EXPORTS[cur][2](s, bundle), cur === 'json' ? 'application/json' : cur === 'csv' ? 'text/csv' : 'text/plain');
      });
      show();
    }

    view.addEventListener('input', function (e) {
      if (e.target.matches('[data-k], [data-ac]')) { if (e.target.matches('.sy-title')) fit(); changed(); }
    });
    view.addEventListener('change', function (e) { if (e.target.matches('select[data-k]')) { changed(); save(); } });
    view.addEventListener('click', function (e) {
      var t = e.target;
      if (t.closest('[data-ac-add]')) { var l = view.querySelector('[data-aclist]'); l.insertAdjacentHTML('beforeend', acRow('')); l.lastElementChild.querySelector('input').focus(); return; }
      var d = t.closest('[data-ac-del]');
      if (d) { var row = d.closest('.sy-ac-row'); if (view.querySelectorAll('.sy-ac-row').length > 1) row.remove(); else row.querySelector('input').value = ''; changed(); return; }
      if (t.closest('[data-export]')) return exportModal();
      if (t.closest('[data-export-ai]')) return exportModal('json');
      var un = t.closest('[data-unlink]');
      if (un) { save().then(function () { return UI.api('unlink_entry', id, un.getAttribute('data-unlink')); }).then(function () { UI.toast('Unlinked', 'ok'); load(); }); return; }
      var dc = t.closest('[data-delc]');
      if (dc) { UI.api('delete_comment', dc.getAttribute('data-delc')).then(reloadKeep); return; }
      if (t.closest('[data-redraft]')) {
        UI.confirm({ title: 'Redraft from the feedback?', text: 'The title, story sentence and acceptance criteria are replaced with a fresh draft. Notes and comments stay. You can still edit it all.', ok: 'Redraft' }).then(function (yes) {
          if (!yes) return;
          UI.api('redraft_story', id).then(function (r) {
            var dr = r.draft;
            Object.assign(S, collect(), { title: dr.title, persona: dr.persona, goal: dr.goal, benefit: dr.benefit, acceptance: dr.acceptance });
            draw(); dirty = true; save(); UI.toast('Redrafted', 'ok');
          });
        });
        return;
      }
      if (t.closest('[data-addfb]')) {
        if (!pool.length) { UI.toast('All feedback on this link is already in a story.', 'error'); return; }
        var m = UI.modal('<h2>Add client feedback</h2><p class="muted small">Feedback from ' + esc(S.board) + ' that isn\'t in a story yet.</p><form data-pickform><div class="ex-pick">' +
          pool.map(function (e) { return '<label><input type="checkbox" name="e" value="' + esc(e.id) + '"><span>' + PX.kind(e.kind) + ' ' + esc(e.message) + '</span></label>'; }).join('') +
          '</div><div class="ui-row end"><button type="button" class="ui-btn ghost" data-close>Cancel</button><button class="ui-btn primary">Add selected</button></div></form>', { wide: true });
        m.el.querySelector('form').addEventListener('submit', function (ev) {
          ev.preventDefault();
          var ids = Array.prototype.map.call(ev.target.querySelectorAll('input:checked'), function (i) { return i.value; });
          if (!ids.length) { m.close(); return; }
          save().then(function () { return UI.api('link_entries', id, ids); }).then(function (r) { m.close(); UI.toast('Added ' + UI.plural(r.count, 'piece') + ' of feedback', 'ok'); load(); });
        });
        return;
      }
      if (t.closest('[data-more]')) {
        var mm = UI.modal('<h2>Story</h2><div class="ui-stack"><button class="ui-btn block" data-dup>' + UI.icon('copy') + 'Copy as Markdown</button>' +
          '<button class="ui-btn block danger" data-delstory>' + UI.icon('trash') + 'Delete this story</button></div>');
        mm.el.addEventListener('click', function (ev) {
          if (ev.target.closest('[data-dup]')) { PX.copy(EXPORTS.markdown[2](current(), bundle), 'Markdown copied'); mm.close(); }
          if (ev.target.closest('[data-delstory]')) {
            mm.close();
            UI.confirm({ title: 'Delete this story?', text: 'Its comments are deleted. The linked feedback stays in your inbox.', ok: 'Delete', danger: true }).then(function (yes) {
              if (yes) { dirty = false; UI.api('delete_story', id).then(function () { UI.toast('Story deleted', 'ok'); UI.go('stories'); }); }
            });
          }
        });
      }
    });
    view.addEventListener('submit', function (e) {
      if (!e.target.matches('[data-commentform]')) return;
      e.preventDefault();
      var v = UI.formData(e.target);
      if (!v.body.trim()) return;
      UI.busy(e.target.querySelector('button'), save().then(function () { return UI.api('add_comment', 'story', id, v.body, PX.mentionIds(e.target.querySelector('textarea'))); })).then(load);
    });
    view.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); dirty = true; save(); }
      if (e.key === 'Enter' && e.target.matches('[data-ac]')) { e.preventDefault(); view.querySelector('[data-ac-add]').click(); }
    });
    return { ready: load(), destroy: function () { if (dirty) save(); } };
  });
})();
