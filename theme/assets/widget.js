/* Prepsto feedback widget. Served at https://prepsto.com/_/theme/widget.js
   On any site:
     <script src="https://prepsto.com/_/theme/widget.js" data-prepsto="CODE" async></script>
   Options (attributes on the script tag):
     data-color="#2b59ff"   button colour          data-label="Feedback"  button text
     data-position="right"  right | left           data-button="false"    no floating button (use your own)
   Your own buttons: any element with data-prepsto-open opens the panel; or call Prepsto.open() / Prepsto.close().
   The panel is the Prepsto page #f/CODE/embed in a frame; it posts {prepsto: "close" | "sent"} back. */
(function () {
  'use strict';
  if (window.Prepsto && window.Prepsto.__v) return;
  var me = document.currentScript || (function () {
    var s = document.querySelectorAll('script[data-prepsto]'); return s[s.length - 1];
  })();
  if (!me) return;
  var slug = me.getAttribute('data-prepsto');
  if (!slug) { console.warn('Prepsto: add data-prepsto="YOUR CODE" to the script tag.'); return; }
  var origin = me.src.replace(/_\/theme\/widget\.js.*$/, '');
  var color = /^#[0-9a-f]{6}$/i.test(me.getAttribute('data-color') || '') ? me.getAttribute('data-color') : '#2b59ff';
  var label = (me.getAttribute('data-label') || 'Feedback').slice(0, 24);
  var left = me.getAttribute('data-position') === 'left';
  var showButton = me.getAttribute('data-button') !== 'false';
  var side = left ? 'left' : 'right';

  var css = '' +
    '.prepsto-btn{position:fixed;bottom:20px;' + side + ':20px;z-index:2147483000;display:inline-flex;align-items:center;gap:8px;padding:11px 16px 11px 13px;' +
      'border:0;border-radius:10px;background:' + color + ';color:#fff;font:600 14px/1 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;cursor:pointer;' +
      'box-shadow:0 10px 30px -8px rgba(0,0,0,.35),0 0 0 1px rgba(0,0,0,.06);transition:transform .15s,box-shadow .15s}' +
    '.prepsto-btn:hover{transform:translateY(-2px)}' +
    '.prepsto-btn:focus-visible{outline:3px solid ' + color + '55;outline-offset:3px}' +
    '.prepsto-btn svg{width:18px;height:18px}' +
    '.prepsto-veil{position:fixed;inset:0;z-index:2147483001;background:rgba(8,10,16,.35);opacity:0;transition:opacity .2s}' +
    '.prepsto-veil.on{opacity:1}' +
    '.prepsto-frame{position:fixed;top:0;bottom:0;' + side + ':0;z-index:2147483002;width:420px;max-width:100%;height:100%;border:0;background:#fff;' +
      'box-shadow:0 0 60px rgba(0,0,0,.25);transform:translateX(' + (left ? '-' : '') + '105%);transition:transform .25s cubic-bezier(.2,.8,.2,1)}' +
    '.prepsto-frame.on{transform:none}' +
    '@media (prefers-reduced-motion:reduce){.prepsto-frame,.prepsto-veil,.prepsto-btn{transition:none}}';
  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  var btn = null, frame = null, veil = null, lastFocus = null;
  if (showButton) {
    btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'prepsto-btn';
    btn.setAttribute('aria-haspopup', 'dialog');
    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-4.9A8 8 0 1 1 21 12z"/></svg><span></span>';
    btn.querySelector('span').textContent = label;
    btn.addEventListener('click', open);
    (document.body ? Promise.resolve() : new Promise(function (r) { document.addEventListener('DOMContentLoaded', r); }))
      .then(function () { document.body.appendChild(btn); });
  }

  function open() {
    if (frame) return;
    lastFocus = document.activeElement;
    veil = document.createElement('div');
    veil.className = 'prepsto-veil';
    veil.addEventListener('click', close);
    frame = document.createElement('iframe');
    frame.className = 'prepsto-frame';
    frame.title = label;
    frame.setAttribute('role', 'dialog');
    frame.src = origin + '#f/' + encodeURIComponent(slug) + '/embed/' + encodeURIComponent(location.href.split('#')[0]);
    document.body.appendChild(veil);
    document.body.appendChild(frame);
    requestAnimationFrame(function () { requestAnimationFrame(function () { veil.classList.add('on'); frame.classList.add('on'); }); });
    frame.addEventListener('load', function () { try { frame.focus(); } catch (e) {} });
    document.addEventListener('keydown', onKey);
  }
  function close() {
    if (!frame) return;
    var f = frame, v = veil;
    frame = veil = null;
    f.classList.remove('on'); v.classList.remove('on');
    setTimeout(function () { f.remove(); v.remove(); }, 260);
    document.removeEventListener('keydown', onKey);
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  function onKey(e) { if (e.key === 'Escape') close(); }
  window.addEventListener('message', function (e) {
    if (e.origin + '/' !== origin && e.origin !== origin.replace(/\/$/, '')) return;
    if (e.data && e.data.prepsto === 'close') close();
  });
  document.addEventListener('click', function (e) {
    var t = e.target.closest && e.target.closest('[data-prepsto-open]');
    if (t) { e.preventDefault(); open(); }
  });
  window.Prepsto = { __v: 1, open: open, close: close, slug: slug };
})();
