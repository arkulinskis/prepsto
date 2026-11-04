/* px.js: the few browser jobs Python leaves to JavaScript (client_code/px.py and state.py call them through window.PX):
   the clipboard, file downloads, short browser names, and the @mention autocomplete on comment boxes. */
(function () {
  'use strict';
  var PX = window.PX = window.PX || {};
  var esc = function (s) { return window.UI && UI.esc ? UI.esc(s) : String(s); };

  /* Copy text. Resolves to true when it worked (Python waits for the answer). */
  PX.copy = function (text) {
    function fallback() {
      var t = document.createElement('textarea');
      t.value = text; t.setAttribute('readonly', ''); t.style.position = 'fixed'; t.style.opacity = '0';
      document.body.appendChild(t); t.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      t.remove();
      return ok;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(function () { return true; }, function () { return fallback(); });
    }
    return Promise.resolve(fallback());
  };

  PX.download = function (name, text, type) {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type: type || 'text/plain' }));
    a.download = name; document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  };

  /* "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/141.0 ..." -> "Chrome 141 · Windows" */
  PX.ua = function (ua) {
    ua = ua || '';
    if (ua.indexOf('Mozilla/') !== 0) return ua;
    var m, b = '';
    if ((m = ua.match(/Edg(?:A|iOS)?\/(\d+)/))) b = 'Edge ' + m[1];
    else if ((m = ua.match(/OPR\/(\d+)/))) b = 'Opera ' + m[1];
    else if ((m = ua.match(/SamsungBrowser\/(\d+)/))) b = 'Samsung Internet ' + m[1];
    else if ((m = ua.match(/(?:Firefox|FxiOS)\/(\d+)/))) b = 'Firefox ' + m[1];
    else if ((m = ua.match(/(?:Chrome|CriOS)\/(\d+)/))) b = 'Chrome ' + m[1];
    else if ((m = ua.match(/Version\/(\d+)[.\d]* (?:Mobile\/\S+ )?Safari\//))) b = 'Safari ' + m[1];
    var os = /iPhone/.test(ua) ? 'iPhone' : /iPad/.test(ua) ? 'iPad' : /Android/.test(ua) ? 'Android' : /CrOS/.test(ua) ? 'ChromeOS'
      : /Windows/.test(ua) ? 'Windows' : /Macintosh|Mac OS X/.test(ua) ? 'Mac' : /Linux/.test(ua) ? 'Linux' : '';
    return [b, os].filter(Boolean).join(' · ') || 'Browser';
  };
  /* Board view: no column stays highlighted after a drag. */
  PX.clearOver = function () { document.querySelectorAll('.ib-col.over').forEach(function (x) { x.classList.remove('over'); }); };

  /* The landing page's video: the cover becomes YouTube's privacy-enhanced player only when pressed. */
  PX.playVideo = function (cover) {
    var f = document.createElement('iframe');
    f.src = 'https://www.youtube-nocookie.com/embed/' + cover.getAttribute('data-yt-film') + '?autoplay=1&rel=0&playsinline=1';
    f.title = cover.getAttribute('data-yt-title') || 'Video';
    f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    f.allowFullscreen = true;
    f.referrerPolicy = 'strict-origin-when-cross-origin';
    cover.parentNode.replaceChild(f, cover);
  };
  PX.host = function (url) { try { var u = new URL(url); return u.host + (u.pathname === '/' ? '' : u.pathname); } catch (e) { return url || ''; } };

  /* @mentions: PX.mentions(textarea, team) adds autocomplete (type @, pick with the arrows + Enter, or click);
     PX.mentionIds(textarea) = the ids of the people still named in the text. team = [{id, name}]. */
  PX.mentions = function (ta, team) {
    if (!ta) return;
    if (ta._mx) { ta._mx.team = team || []; return; }
    ta._mx = { team: team || [] };
    var wrap = ta.parentNode, list = document.createElement('div'), hits = [], sel = 0;
    wrap.classList.add('px-mx-wrap');
    list.className = 'px-mx'; list.hidden = true; list.setAttribute('role', 'listbox'); list.setAttribute('aria-label', 'Teammates');
    wrap.appendChild(list);
    function query() {
      var m = /(^|\s)@([^\s@]{0,30})$/.exec(ta.value.slice(0, ta.selectionStart));
      return m ? m[2] : null;
    }
    function show() {
      var q = query();
      if (q === null || !ta._mx.team.length) { list.hidden = true; return; }
      var lq = q.toLowerCase();
      hits = ta._mx.team.filter(function (p) { var n = p.name.toLowerCase(); return n.indexOf(lq) === 0 || n.indexOf(' ' + lq) > 0; }).slice(0, 6);
      if (!hits.length) { list.hidden = true; return; }
      sel = Math.min(sel, hits.length - 1);
      list.innerHTML = hits.map(function (p, i) {
        var ini = p.name.trim().split(/\s+/); ini = ((ini[0] || '?')[0] + (ini.length > 1 ? ini[ini.length - 1][0] : '')).toUpperCase();
        return '<button type="button" role="option" aria-selected="' + (i === sel) + '" data-mx="' + i + '" class="' + (i === sel ? 'on' : '') + '"><span class="ui-avatar">' + esc(ini) + '</span>' + esc(p.name) + '</button>';
      }).join('');
      list.hidden = false;
    }
    function pick(p) {
      var pos = ta.selectionStart, before = ta.value.slice(0, pos).replace(/@([^\s@]{0,30})$/, '@' + p.name + ' ');
      ta.value = before + ta.value.slice(pos);
      ta.selectionStart = ta.selectionEnd = before.length;
      list.hidden = true; ta.focus();
      ta.dispatchEvent(new Event('input', { bubbles: true }));  // Anvil's TextArea picks up the new text
    }
    ta.addEventListener('input', function (e) { if (e.isTrusted !== false) { sel = 0; show(); } });
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
})();
