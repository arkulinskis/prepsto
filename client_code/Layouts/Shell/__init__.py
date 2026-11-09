import datetime

from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import ShellTemplate
from ... import auth, router, state

THEMES = ["auto", "light", "dark"]
BELL: dict = {"at": 0, "data": None}  # notifications, fetched quietly at most every 20 s (kept across pages)


class Shell(ShellTemplate):
    """The frame around every member and visitor page: header (menu for members, Sign in / Get started for visitors),
    the notification bell (mentions, assignments, invitations, people joining, sender replies), the account menu, the
    footer and the phone tab bar. Pages use it with <anvil-form layout="Prepsto.Layouts.Shell">.

    Anvil keeps ONE Shell while pages come and go (open_form only swaps the "content" slot when the layout matches),
    so everything that depends on who is signed in or which page is open is drawn in refresh(), which router.show()
    calls after every page change. Never only in __init__."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.copyright_label.text = "© %d Prepsto" % datetime.date.today().year
        self._outside = anvil.js.report_exceptions(self._close_menu_outside)
        self._keys = anvil.js.report_exceptions(self._key)
        self.notif_panel.add_event_handler("x-read", self._notif_read)
        self.bell_panel.visible = False
        self.refresh("")

    def refresh(self, page):
        me = state.me()
        self.classes.update({"signed-in": bool(me), "signed-out": not me})
        for name in router.PAGES:
            self.classes["page-" + name] = name == page
        self.member_actions.visible = bool(me)
        self.guest_actions.visible = not me and page != "auth"
        self.tabbar.visible = bool(me)
        self.menu.visible = False
        self.bell_panel.visible = False
        state.set_attr(self.brand, "href", "#home" if me else "#landing")
        links = [{"page": p, "label": label, "icon": icon, "on": p == page} for p, label, icon in router.NAV] if me else []
        self.nav_panel.items = links
        self.tab_panel.items = links
        self.tab_profile.classes["on"] = page == "profile"
        if me:
            self.avatar_button.text = state.initials(me.get("name"))
            self.menu_name.text = me.get("name") or ""
            self.menu_email.text = me.get("email") or ""
            self.admin_link.visible = bool(me.get("is_admin"))
            self._paint_bell()
            state.later(self.refresh_bell, 60)
        self._show_theme()

    # ---- the bell
    def refresh_bell(self, force=False):
        if not state.me() or (not force and window.Date.now() - BELL["at"] < 20000):
            return
        d = state.call_quiet("get_notifications")
        if d is not None:
            BELL["data"], BELL["at"] = d, window.Date.now()
            self._paint_bell()

    def _paint_bell(self):
        d: dict = BELL["data"] or {"unread": 0, "items": []}
        n = d.get("unread") or 0
        self.bell_count.visible = n > 0
        self.bell_count.text = "9+" if n > 9 else str(n)
        state.set_control_attr(self.bell_button, "aria-label", "Notifications" + (" (%d new)" % n if n else ""))
        self.read_all_button.visible = n > 0
        if self.bell_panel.visible:
            self.notif_panel.items = d.get("items") or []
            self.notif_empty.visible = not d.get("items")

    @handle("bell_button", "click")
    def bell_button_click(self, **event_args):
        self.menu.visible = False
        self.bell_panel.visible = not self.bell_panel.visible
        if self.bell_panel.visible:
            self._paint_bell()
            self.refresh_bell(force=True)

    @handle("read_all_button", "click")
    def read_all_button_click(self, **event_args):
        state.call_quiet("mark_notifications_read")
        self.refresh_bell(force=True)

    def _notif_read(self, notif_id=None, **event_args):
        state.call_quiet("mark_notifications_read", [notif_id])
        BELL["at"] = 0

    # ---- account menu
    @handle("avatar_button", "click")
    def avatar_button_click(self, **event_args):
        self.bell_panel.visible = False
        self.menu.visible = not self.menu.visible

    def _close_menu_outside(self, event):
        t = event.target
        if self.menu.visible and not t.closest(".anvil-role-avatar, .ui-menu .ui-seg"):
            self.menu.visible = False
        if self.bell_panel.visible and not t.closest(".anvil-role-px-bell, .px-notifs-head"):
            self.bell_panel.visible = False

    def _key(self, event):
        if getattr(event, "key", None) == "Escape":
            self.menu.visible = False
            self.bell_panel.visible = False

    @handle("", "show")
    def form_show(self, **event_args):
        window.document.addEventListener("click", self._outside, True)
        window.document.addEventListener("keydown", self._keys)

    @handle("", "hide")
    def form_hide(self, **event_args):
        window.document.removeEventListener("click", self._outside, True)
        window.document.removeEventListener("keydown", self._keys)

    def theme_click(self, event):
        state.set_theme(event.currentTarget.getAttribute("data-theme-set"))
        self._show_theme()

    def _show_theme(self):
        t = state.theme()
        for name, el in zip(THEMES, [self.theme_auto, self.theme_light, self.theme_dark]):
            el.classes["on"] = name == t

    def feedback_click(self, event):
        self.menu.visible = False
        state.feedback()

    def sign_out_click(self, event):
        auth.sign_out()
        BELL["data"], BELL["at"] = None, 0
        state.toast("Signed out. See you soon!")
        router.go("landing")
