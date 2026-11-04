from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import FeedbackPanelTemplate
from ... import px, state

RATE_WORDS = ["", "Poor", "Meh", "OK", "Good", "Great"]


def _nothing():
    pass


class FeedbackPanel(FeedbackPanelTemplate):
    """The feedback panel: kind chips, message, optional stars and email, a honeypot, the thank-you screen with the
    private tracking link, and "Your feedback" (what this browser sent before, with new-update dots).

        panel.setup(board, preview=False, embed=False, page="", on_close=None, on_sent=None)
        panel.update(board)          a preview redraw (Links page) that keeps what was typed

    board = Boards.widget_config's board (or the Links form's values). Preview mode sends nothing."""

    def __init__(self, **properties):
        self.b, self.opts = {}, {}
        self._on_close, self._on_sent = _nothing, _nothing
        self.kind, self.rating, self.items, self.mine, self._track = "", 0, None, [], ""
        super().__init__(**properties)
        self._stars = [self.s1, self.s2, self.s3, self.s4, self.s5]
        self.kinds_panel.add_event_handler("x-kind", self._pick_kind)
        state.set_control_attr(self.message_box, "maxlength", "4000")
        state.set_control_attr(self.email_box, "autocomplete", "email")
        hp = state.control(self.hp_box)
        hp.setAttribute("tabindex", "-1")
        hp.setAttribute("autocomplete", "off")
        hp.setAttribute("aria-label", "Website")
        state.heading(self.prompt, 2)
        for part in (self.closed_part, self.thanks_part, self.mine_part):
            part.visible = False

    # ------------------------------------------------------------------ drawing
    def setup(self, board, preview=False, embed=False, page="", on_close=None, on_sent=None):
        self.opts = {"preview": preview, "embed": embed, "page": page, "close": bool(on_close)}
        self._on_close, self._on_sent = on_close or _nothing, on_sent or _nothing
        self.mine = [] if preview or not board.get("slug") else px.mine_list(board["slug"])
        self.items = None
        state.set_attr(self.home_link, "href", px.base())
        self.update(board)
        if self.mine:
            state.later(self._load_mine, 30)

    def update(self, board):
        b = self.b = dict(board)
        kinds = list(b.get("kinds") or []) or ["idea"]
        if self.kind not in kinds:
            self.kind = kinds[0]
        anvil.js.get_dom_node(self).style.setProperty("--pc", b.get("color") or "#2b59ff")
        self.prompt.text = b.get("prompt") or "How can we make this better?"
        self.board_name.text = b.get("name") or ""
        self.close_button.visible = bool(self.opts.get("embed") or self.opts.get("close"))
        self.foot_text.text = "Preview" if self.opts.get("preview") else "Private: only the team reads this"
        self.kinds_part.visible = len(kinds) > 1
        self.kinds_panel.items = [{"kind": k, "on": k == self.kind} for k in kinds]
        self.message_box.placeholder = px.PLACEHOLDER.get(self.kind, "Tell us anything.")
        self.rate_part.visible = bool(b.get("ask_rating"))
        self.email_part.visible = bool(b.get("ask_email"))
        self._paint_stars()
        self._mine_bar()
        if not (self.thanks_part.visible or self.mine_part.visible):
            self._show("form" if b.get("is_open", True) else "closed")

    def _show(self, part):
        self.form_part.visible = part == "form"
        self.closed_part.visible = part == "closed"
        self.thanks_part.visible = part == "thanks"
        self.mine_part.visible = part == "mine"
        self.mine_bar.visible = part in ("form", "closed") and bool(self.mine)

    def _mine_bar(self):
        n = len(self.mine or [])
        fresh = len([it for it in (self.items or []) if px.fresh(it)])
        self.mine_bar.text = "Your feedback · %d%s" % (n, ("  ·  %s" % state.plural(fresh, "new update")) if fresh else "")
        self.mine_bar.visible = bool(n) and (self.form_part.visible or self.closed_part.visible)

    def _paint_stars(self):
        for i, s in enumerate(self._stars):
            s.classes["on"] = i < self.rating
            anvil.js.get_dom_node(s).setAttribute("aria-pressed", "true" if i < self.rating else "false")
        self.rate_label.text = RATE_WORDS[self.rating]

    def _load_mine(self):
        r = state.call_quiet("track_list", [x["t"] for x in self.mine])
        if r and r.get("ok"):
            self.items = r["items"]
            self._mine_bar()
            if self.mine_part.visible:
                self._paint_mine()

    def _paint_mine(self):
        self.mine_panel.items = self.items or []
        self.mine_empty.visible = self.items is not None and not self.items

    # ------------------------------------------------------------------ choices
    def _pick_kind(self, kind=None, **event_args):
        key = state.focus_key()
        self.kind = kind
        self.kinds_panel.items = [{"kind": k, "on": k == kind} for k in (self.b.get("kinds") or ["idea"])]
        self.message_box.placeholder = px.PLACEHOLDER.get(kind, "Tell us anything.")
        state.refocus(self.kinds_panel, key)

    def star_click(self, event):
        n = int(event.currentTarget.getAttribute("data-n"))
        self.rating = 0 if n == self.rating else n
        self._paint_stars()

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self._on_close()

    @handle("mine_bar", "click")
    def mine_bar_click(self, **event_args):
        self._show("mine")
        self._paint_mine()
        if self.items is None:
            self._load_mine()

    @handle("write_button", "click")
    def write_button_click(self, **event_args):
        self._again()

    @handle("again_button", "click")
    def again_button_click(self, **event_args):
        self._again()

    def _again(self):
        self.rating = 0
        self.message_box.text = ""
        self.email_box.text = ""
        self.error.visible = False
        self._paint_stars()
        self._show("form" if self.b.get("is_open", True) else "closed")
        self._mine_bar()

    # ------------------------------------------------------------------ sending
    @handle("send_button", "click")
    def send_button_click(self, **event_args):
        self.error.visible = False
        message = (self.message_box.text or "").strip()
        if len(message) < 3:
            self.error.text, self.error.visible = "Please write a few words.", True
            return
        if self.opts.get("preview"):
            self._thanks(self.b.get("thanks"), None)
            return
        scr = window.screen
        data = {"kind": self.kind, "message": message, "rating": self.rating or None, "email": self.email_box.text or "",
                "website": self.hp_box.text or "", "page": self.opts.get("page") or window.document.referrer or "",
                "context": {"screen": "%sx%s" % (scr.width, scr.height), "browser": str(window.navigator.userAgent)[:160],
                            "lang": window.navigator.language or ""}}
        self.send_button.enabled = False
        try:
            r = anvil.server.call("widget_submit", self.b["slug"], data)
        finally:
            self.send_button.enabled = True
        if not r.get("ok"):
            self.error.text, self.error.visible = r.get("error") or "That didn't work.", True
            return
        if r.get("track"):
            px.mine_add(self.b["slug"], {"t": r["track"], "at": anvil.js.new(window.Date).toISOString()})
            self.mine, self.items = px.mine_list(self.b["slug"]), None
        self._thanks(r.get("thanks"), r.get("track"))
        self._on_sent()

    def _thanks(self, message, track):
        self.thanks_text.text = message or self.b.get("thanks") or "Thank you!"
        follow = bool(track) or (bool(self.opts.get("preview")) and self.b.get("public_track") is not False)
        self.follow_part.visible = follow
        self.copy_track_button.visible = bool(track)
        self._track = px.track_link(track) if track else ""
        state.set_attr(self.track_link, "href", self._track or None)
        if track:
            px.mark_seen(track)
        self._show("thanks")

    @handle("copy_track_button", "click")
    def copy_track_button_click(self, **event_args):
        state.copy(self._track, "Tracking link copied")
