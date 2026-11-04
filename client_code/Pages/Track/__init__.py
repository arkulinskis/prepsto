from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import TrackTemplate
from ... import px, state

PRIO = {"low": (1, "Low"), "medium": (2, "Medium"), "high": (3, "High"), "urgent": (4, "Urgent")}
STORY = {"draft": "Being written up", "ready": "Ready to build", "in_progress": "Being built", "shipped": "Shipped"}


class Track(TrackTemplate):
    """#t/<token>: the PUBLIC tracking page for one piece of feedback (server_code/Tracking.py). The sender got the
    link on the panel's thank-you screen. Steps (Received → Done), the priority, the story it became, the team's
    public replies, and a reply box. No header or footer: it carries the creator's colour, like the panel."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.token = args[0] if args else ""
        self.missing.visible = False
        state.set_attr(self.home_link, "href", px.base())
        state.heading(self.done_title, 2)
        state.set_control_attr(self.reply_box, "maxlength", "2000")
        r = anvil.server.call("track_get", self.token)
        if not r.get("ok"):
            self.page.visible = False
            self.missing.visible = True
            self.missing_text.text = r.get("error") or ""
            return
        self.d = r
        px.mark_seen(self.token)
        self._draw()

    def _draw(self):
        d = self.d
        b, e, closed = d["board"], d["entry"], d["stage"] == "closed"
        window.document.title = "Your feedback · " + b["name"]
        anvil.js.get_dom_node(self.page).style.setProperty("--pc", b.get("color") or "#2b59ff")
        self.board_name.text = b["name"]
        self.back_link.visible = bool(b.get("site_url"))
        if b.get("site_url"):
            state.set_attr(self.back_link, "href", b["site_url"])
            self.back_label.text = "Back to " + px.host(b["site_url"]).split("/")[0]
        self.done_card.visible = d["stage"] == "done"
        self.done_title.text = "Fixed!" if e["kind"] == "bug" else "Done!"
        self.done_text.text = "Thank you for helping make %s better." % b["name"]
        px.kind(self.kind_badge, e["kind"])
        self.sent.text = "sent " + state.fmt_date(e.get("created"))
        px.stage(self.stage_badge, d["stage"])
        self.quote.text = e.get("message") or ""
        self.steps_panel.items = [dict(s, _closed=closed, _first=i == 0) for i, s in enumerate(d["steps"])]
        state.set_attr(self.steps_box, "aria-label", "Progress: " + d.get("stage_label", ""))
        state.set_attr(self.steps_box, "role", "group")
        self.closed_note.visible = closed
        p = e.get("priority") or ""
        level = PRIO[p][0] if p in PRIO else 0
        self.meter.visible = bool(p)
        for i, m in enumerate([self.m1, self.m2, self.m3, self.m4]):
            m.classes["on"] = i < level
        self.meter.classes["urgent"] = p == "urgent"
        self.prio_text.text = PRIO[p][1] if p in PRIO else (p or "Not set yet")
        self.prio_text.role = ["px-inline"] if p else ["px-inline", "muted"]
        st = d.get("story")
        self.story_text.text = st["title"] if st else "Not yet"
        self.story_text.role = ["px-inline"] if st else ["px-inline", "muted"]
        self.story_state.visible = bool(st)
        if st:
            self.story_state.text = "· " + STORY.get(st["status"], st["status"])
        n = d.get("supporters") or 0
        self.supporters.text = ("You and " + state.plural(n, "other person", "other people")) if n else "You"
        self._timeline()
        self.reply_card.visible = bool(b.get("is_open"))

    def _timeline(self):
        ups = list(reversed(self.d.get("updates") or []))
        self.timeline_panel.items = ups
        self.no_updates.visible = not ups

    @handle("reply_button", "click")
    def reply_button_click(self, **event_args):
        self.reply_error.visible = False
        text = (self.reply_box.text or "").strip()
        if len(text) < 2:
            self.reply_error.text, self.reply_error.visible = "Write a few words first.", True
            return
        self.reply_button.enabled = False
        try:
            r = anvil.server.call("track_reply", self.token, text)
        finally:
            self.reply_button.enabled = True
        if not r.get("ok"):
            self.reply_error.text, self.reply_error.visible = r.get("error") or "That didn't work.", True
            return
        self.d["updates"] = r["updates"]
        self._timeline()
        self.reply_box.text = ""
        state.toast("Sent to the team", "ok")
