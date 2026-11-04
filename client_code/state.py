"""App-wide client state and small helpers every form uses.

    state.me()                 the signed-in person as a dict {id, email, name, is_admin, joined}, or None
    state.set_me(me)           after sign in / sign out / a profile change
    state.call(fn, *args)      anvil.server.call that turns an expected {"ok": False, "error": ...} reply into a toast
                               and returns None; any other reply comes back unchanged. Unexpected errors still raise.
    state.toast(msg, kind)     a short notification; kind "ok" or "error" picks the colour (theme roles)
    state.store_get/store_set  this browser's storage (same keys as the JavaScript version, so drafts carry over)
    state.set_theme(t)         "auto", "light" or "dark"
    state.set_attr(c, name, v) an HTML attribute on a component's root (href on a named <a>, aria-label ...)
    state.set_control_attr     the same on the real <input>/<button> inside (autocomplete, aria-pressed)
    state.heading(label, 1)    a Label that screen readers treat as a heading; state.live(label) reads it out on change
    state.focus_key/refocus    keep the keyboard focus on the same choice after a RepeatingPanel redraw (data-key)
"""
import json

import anvil.js
import anvil.server
from anvil import Notification
from anvil.js import window

_state = {"me": None}


def me():
    return _state["me"]


def set_me(value):
    _state["me"] = value or None


def is_admin():
    m = _state["me"]
    return bool(m and m.get("is_admin"))


def toast(message, kind=None):
    timeout = 6.5 if kind == "error" else 3.2
    try:
        n = Notification(message, timeout=timeout, role=kind)
    except TypeError:  # the open-source App Server 1.18 has no `role` yet: its older `style` gives the same classes
        n = Notification(message, timeout=timeout, style={"ok": "success", "error": "danger"}.get(kind or "", "info"))
    n.show()


def call(fn, *args):
    """Server call for the normal "do something" flows. {"ok": False, "error"} replies are expected problems
    (a missing name, something private): show them and return None."""
    r = anvil.server.call(fn, *args)
    if isinstance(r, dict) and r.get("ok") is False:
        toast(r.get("error") or "That didn't work.", "error")
        return None
    return r


def call_quiet(fn, *args):
    """No spinner, nothing shown if it fails (reading counters and other background calls)."""
    try:
        return anvil.server.call_s(fn, *args)
    except anvil.server.AppOfflineError:
        return None


def set_attr(component, name, value):
    """Set an HTML attribute (href, aria-label, title) on a component's root element.
    (HtmlComponent.attrs does this on hosted Anvil, but the open-source App Server 1.18 doesn't have it yet.)"""
    node = anvil.js.get_dom_node(component)
    if value is None:
        node.removeAttribute(name)
    else:
        node.setAttribute(name, str(value))


def store_get(key, default=None):
    """A saved value as plain Python (dicts and lists, not JavaScript objects)."""
    raw = window.localStorage.getItem(window.UI.config.key + "." + key) if _storage_ok() else None
    if raw is None:
        return default
    try:
        v = json.loads(raw)
    except Exception:
        return default
    return default if v is None else v


def _storage_ok():
    try:
        return window.localStorage is not None
    except Exception:
        return False


def store_set(key, value):
    try:
        window.localStorage.setItem(window.UI.config.key + "." + key, json.dumps(value))
    except Exception:
        pass  # private mode / storage full: settings just aren't remembered


def theme():
    return window.UI.theme()


def set_theme(value):
    window.UI.setTheme(value)


def plural(n, one, many=None):
    return "%d %s" % (n, one if n == 1 else (many or one + "s"))


def initials(name):
    parts = (name or "?").split()
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December"]


def short_date(iso):
    """'2026-11-02T...' -> '2 Nov'."""
    if not iso:
        return ""
    y, m, d = iso[:10].split("-")
    return "%d %s" % (int(d), MONTHS[int(m) - 1])


def month_year(iso):
    if not iso:
        return ""
    y, m = iso[:7].split("-")
    return "%s %s" % (MONTHS_LONG[int(m) - 1], y)


def ago(iso):
    """'3 days ago' from an ISO time, using the browser clock."""
    if not iso:
        return ""
    secs = (window.Date.now() - window.Date.parse(iso)) / 1000
    if secs < 60:
        return "just now"
    n = secs / 60
    for size, unit in [(60, "minute"), (24, "hour"), (7, "day"), (4.35, "week"), (12, "month"), (10 ** 9, "year")]:
        if n < size:
            return plural(int(n), unit) + " ago"
        n = n / size
    return ""


def fmt_date(iso):
    """'2026-11-02...' -> '2 Nov 2026' (the browser's own date words)."""
    if not iso:
        return ""
    d = anvil.js.new(window.Date, iso + "T12:00:00" if len(iso) <= 10 else iso)
    return d.toLocaleDateString([], {"day": "numeric", "month": "short", "year": "numeric"})


def fmt_datetime(iso):
    if not iso:
        return ""
    return anvil.js.new(window.Date, iso).toLocaleString([], {"day": "numeric", "month": "short", "hour": "2-digit", "minute": "2-digit"})


def copy(text, what="Copied"):
    """Put text on the clipboard (with a fallback for old browsers) and say so."""
    if window.PX.copy(text):
        toast(what + " to the clipboard", "ok")
    else:
        toast("Copy didn't work: select the text and copy it.", "error")


def download(name, text, kind="text/plain"):
    window.PX.download(name, text, kind)


def later(fn, ms=0):
    """Run fn after the current page has finished drawing (alerts and focus need the page on screen)."""
    return window.setTimeout(anvil.js.report_exceptions(lambda *a: fn()), ms)


def cancel(timer):
    if timer is not None:
        window.clearTimeout(timer)


def feedback():
    """Open the Prepsto feedback panel (the app's only feedback channel)."""
    if window.get("Prepsto") and window.Prepsto.open:
        window.Prepsto.open()
    else:
        window.open("https://prepsto.com/#f/938ktjj", "_blank", "noopener")


# ---------------------------------------------------------------- accessibility (WCAG AA)
# app-kit.js already makes msg-error/msg-note Labels speak and .ui-seg toggles say which one is on.
def control(component):
    """The real <input>, <textarea>, <select> or <button> inside an Anvil component (for ARIA attributes and focus)."""
    node = anvil.js.get_dom_node(component)
    if str(node.tagName) in ("INPUT", "TEXTAREA", "SELECT", "BUTTON"):
        return node
    return node.querySelector("input, textarea, select, button") or node


def focus(component):
    """Keyboard focus on a component's real control (Anvil's Button has no focus())."""
    getattr(control(component), "focus")()


def set_control_attr(component, name, value):
    """An HTML attribute on the component's real control: autocomplete on a TextBox, aria-pressed on a Button."""
    el = control(component)
    if value is None:
        el.removeAttribute(name)
    else:
        el.setAttribute(name, str(value))


def heading(component, level=1):
    """Make a Label a real heading for screen readers (an Anvil Label renders as a <div>)."""
    set_attr(component, "role", "heading")
    set_attr(component, "aria-level", level)


def live(component, urgent=False):
    """Have screen readers read a Label out whenever its text changes ("Loading...", "No tables left")."""
    set_attr(component, "role", "alert" if urgent else "status")


def focus_key():
    """The data-key of the focused element, so a redraw can put the keyboard focus back (see refocus)."""
    el = window.document.activeElement
    hit = el.closest("[data-key]") if el and getattr(el, "closest", None) else None
    return hit.getAttribute("data-key") if hit else None


def refocus(component, key, fallback=None):
    """After a RepeatingPanel redraw replaced the focused button: focus the new one with the same data-key
    inside component (else fallback), so keyboard users keep their place instead of landing at the top of the page."""
    if not key:
        return
    el = anvil.js.get_dom_node(component).querySelector('[data-key="%s"]' % window.CSS.escape(str(key)))
    if el and not getattr(el, "disabled", False):
        getattr(el, "focus")()
    elif fallback is not None:
        focus(fallback)
