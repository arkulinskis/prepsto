from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import DrawerTemplate
from ... import px, router, state


LAST = {"changed": False}  # also read by the pages when the drawer is closed with Escape or a click outside


class Drawer(DrawerTemplate):
    """One piece of feedback in a side drawer (Overview + Inbox): opened with
    alert(Drawer(entry_id=...), buttons=[], role="px-drawer", large=True, dismissible=True).

    Triage (status, priority, assignee, star, tags, archive, delete), Insights, the story it belongs to, the sender's
    public timeline with a reply box, team comments with @mentions, and similar feedback (opens in place).
    Closes with True when something changed (the page reloads), or {"go": (page, arg)} to open a page."""

    def __init__(self, entry_id=None, **properties):
        super().__init__(**properties)
        self.entry_id, self._track = entry_id, ""
        self.d: dict = {}
        LAST["changed"] = False
        self.status_box.items = [(label, key) for key, label in px.STATUSES]
        self.prio_box.items = [(label, key) for key, label in px.PRIORITIES]
        for box, name in ((self.status_box, "Status"), (self.prio_box, "Priority"), (self.assign_box, "Assigned to"),
                          (self.add_story_box, "Add to a story")):
            state.set_control_attr(box, "aria-label", name)
        state.set_control_attr(self.tag_box, "maxlength", "24")
        state.set_control_attr(self.tag_box, "aria-label", "Add a tag")
        state.set_control_attr(self.reply_box, "maxlength", "2000")
        state.set_control_attr(self.comment_box, "maxlength", "2000")
        self.tags_panel.add_event_handler("x-untag", self._untag)
        self.suggest_panel.add_event_handler("x-addtag", self._addtag)
        self.comments_panel.add_event_handler("x-delete", self._delete_comment)
        self.timeline_panel.add_event_handler("x-remove", self._remove_update)
        self.similar_panel.add_event_handler("x-open", self._open_similar)
        self._load()

    @handle("", "show")
    def form_show(self, **event_args):
        px.DIALOG["form"] = self

    @handle("", "hide")
    def form_hide(self, **event_args):
        if px.DIALOG["form"] is self:
            px.DIALOG["form"] = None

    # ------------------------------------------------------------------ drawing
    def _load(self):
        r = anvil.server.call("get_entry", self.entry_id)
        ok = bool(r.get("ok"))
        self.missing.visible, self.body.visible = not ok, ok
        if not ok:
            self.missing_text.text = r.get("error") or ""
            return
        self.d = r
        self._draw()

    def _draw(self):
        d = self.d
        e, ai, c = d["entry"], d["entry"].get("ai") or {}, d["entry"].get("context") or {}
        me = state.me() or {}
        px.kind(self.kind_badge, e["kind"])
        px.status(self.status_badge, e["status"])
        px.prio(self.prio_badge, e.get("priority"))
        self.star_button.role = ["btn", "btn-ghost", "btn-icon", "ic-star"] + (["starred"] if e.get("starred") else [])
        state.set_control_attr(self.star_button, "aria-pressed", "true" if e.get("starred") else "false")
        self.quote.text = e.get("message") or ""
        self.who.text = px.who(e)
        self.email_box.visible = bool(e.get("email"))
        self.email.text = e.get("email") or ""
        state.set_attr(self.email_link, "href", "mailto:" + (e.get("email") or ""))
        self.when.text = state.fmt_datetime(e.get("created"))
        self.ago.text = "(%s)" % state.ago(e.get("created"))
        self.board.text = e.get("board") or ""
        px.stars(self.stars_badge, e.get("rating"))
        self.rating_dt.visible = self.rating_dd.visible = bool(e.get("rating"))
        self.page.text = e.get("page_url") or ""
        self.page_dt.visible = self.page_dd.visible = bool(e.get("page_url"))
        device = " · ".join(x for x in (px.ua(c.get("browser")), c.get("screen"), c.get("lang")) if x)
        self.device.text, self.device.tooltip = device, c.get("browser") or ""
        self.device_dt.visible = self.device_dd.visible = bool(c.get("screen") or c.get("browser"))
        self.status_box.selected_value = e["status"]
        self.prio_box.selected_value = e.get("priority") or ""
        self.assign_box.items = [("Nobody", "")] + [(p["name"] + (" (me)" if p["name"] == me.get("name") else ""), p["id"]) for p in d.get("team") or []]
        self.assign_box.selected_value = (e.get("assignee") or {}).get("id") or ""
        state.set_control_attr(self.assign_box, "aria-label", "Assigned to")
        self.tags_panel.items = [{"tag": t} for t in e.get("tags") or []]
        suggested = [t for t in ai.get("tags") or [] if t not in (e.get("tags") or [])]
        self.suggest_part.visible = bool(suggested)
        self.suggest_panel.items = [{"tag": t, "suggested": True} for t in suggested]
        self.provider.text = "AI" if ai.get("provider") == "ai" else "rules engine"
        px.senti(self.senti_badge, ai)
        self.urgency.text = "urgency: " + (ai.get("urgency") or "-")
        self.urgency.role = ["px-prio", "urgent" if ai.get("urgency") == "high" else "none"]
        self.theme.visible = bool(ai.get("theme"))
        self.theme.text = "theme: " + (ai.get("theme") or "")
        self.summary.visible = bool(ai.get("summary"))
        self.summary.text = "Summary: " + (ai.get("summary") or "")
        st = e.get("story")
        self.story_part.visible, self.nostory_part.visible = bool(st), not st
        if st:
            self.story_button.text = st["title"]
        self.add_story_box.visible = bool(d.get("stories"))
        self.add_story_box.items = [("Add to a story…", "")] + [(s["title"], s["id"]) for s in d.get("stories") or []]
        self.add_story_box.selected_value = ""
        state.set_control_attr(self.add_story_box, "aria-label", "Add to a story")
        self._public()
        self.comments_panel.items = d.get("comments") or []
        self.no_comments.visible = not d.get("comments")
        self.similar_part.visible = bool(d.get("similar"))
        self.similar_panel.items = d.get("similar") or []
        self.archive_button.text = "Unarchive" if e["status"] == "archived" else "Archive"
        self.delete_button.visible = d.get("role") == "owner"
        window.PX.mentions(state.control(self.comment_box), [{"id": p["id"], "name": p["name"]} for p in d.get("team") or []])

    def _public(self):
        d, e = self.d, self.d["entry"]
        t = d.get("tracking") or {}
        on = bool(t.get("on"))
        self.track_off.visible, self.track_on.visible, self.public_badge.visible = not on, on, on
        if not on:
            owner = d.get("role") == "owner"
            self.off_text.text = "Tracking is off for this link, so the sender can't follow it. " + \
                ("" if owner else "The link's owner can turn it on.")
            self.links_button.visible = owner
            return
        px.stage(self.stage_badge, t.get("stage"))
        self.seen.text = ("They last checked " + state.ago(t["seen"])) if t.get("seen") else "They haven't opened their tracking page yet"
        self.waiting.visible = bool(t.get("waiting"))
        ups = [dict(u, _team=True) for u in reversed(t.get("updates") or [])]
        self.timeline_panel.items = ups
        self.no_timeline.visible = not ups
        self._track = px.track_link(t.get("token") or "")
        self.mail_link.visible = bool(e.get("email"))
        if e.get("email"):
            body = "Hi %s,\n\nThank you for your feedback. You can follow it, read our replies and answer them here:\n%s\n" % (e.get("name") or "", self._track)
            state.set_attr(self.mail_link, "href", "mailto:%s?subject=%s&body=%s" % (
                window.encodeURIComponent(e["email"]), window.encodeURIComponent("About your feedback on " + (e.get("board") or "")),
                window.encodeURIComponent(body)))

    # ------------------------------------------------------------------ changes
    def _update(self, changes, toast=None):
        r = state.call("update_entry", self.entry_id, changes)
        if r is None:
            self._load()
            return False
        LAST["changed"] = True
        self._load()
        if toast:
            state.toast(toast, "ok")
        return True

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=LAST["changed"])

    @handle("star_button", "click")
    def star_button_click(self, **event_args):
        self._update({"starred": not self.d["entry"].get("starred")})

    @handle("status_box", "change")
    def status_box_change(self, **event_args):
        self._update({"status": self.status_box.selected_value})

    @handle("prio_box", "change")
    def prio_box_change(self, **event_args):
        self._update({"priority": self.prio_box.selected_value})

    @handle("assign_box", "change")
    def assign_box_change(self, **event_args):
        v = self.assign_box.selected_value
        self._update({"assignee_id": v}, "Assigned" if v else "Unassigned")

    @handle("tag_box", "pressed_enter")
    def tag_box_pressed_enter(self, **event_args):
        tag = (self.tag_box.text or "").strip()
        if tag:
            self.tag_box.text = ""
            self._update({"add_tag": tag})
            state.focus(self.tag_box)

    def _untag(self, tag=None, **event_args):
        self._update({"tags": [t for t in self.d["entry"].get("tags") or [] if t != tag]})

    def _addtag(self, tag=None, **event_args):
        self._update({"add_tag": tag})

    @handle("story_button", "click")
    def story_button_click(self, **event_args):
        self.raise_event("x-close-alert", value={"go": ("story", self.d["entry"]["story"]["id"])})

    @handle("unstory_button", "click")
    def unstory_button_click(self, **event_args):
        self._update({"story_id": ""})

    @handle("add_story_box", "change")
    def add_story_box_change(self, **event_args):
        if self.add_story_box.selected_value:
            self._update({"story_id": self.add_story_box.selected_value}, "Added to the story")

    @handle("draft_button", "click")
    def draft_button_click(self, **event_args):
        r = state.call("create_story", None, [self.entry_id])
        if r:
            state.toast("Story drafted", "ok")
            self.raise_event("x-close-alert", value={"go": ("story", r["story"]["id"])})

    @handle("links_button", "click")
    def links_button_click(self, **event_args):
        self.raise_event("x-close-alert", value={"go": ("links", self.d["entry"]["board_id"])})

    @handle("archive_button", "click")
    def archive_button_click(self, **event_args):
        was = self.d["entry"]["status"] == "archived"
        self._update({"status": "new" if was else "archived"}, "Back in the inbox" if was else "Archived")

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        if confirm("It and its comments are gone for good. Archive it instead if you might need it.", title="Delete this feedback?",
                   buttons=[("Cancel", False), ("Delete", True)], role="app-dialog"):
            if state.call("delete_entry", self.entry_id) is not None:
                state.toast("Deleted", "ok")
                self.raise_event("x-close-alert", value=True)

    # ---- the sender's side
    @handle("reply_button", "click")
    def reply_button_click(self, **event_args):
        text = (self.reply_box.text or "").strip()
        if not text:
            return
        if state.call("post_update", self.entry_id, text) is not None:
            self.reply_box.text = ""
            LAST["changed"] = True
            state.toast("Sent: they'll see it on their tracking page", "ok")
            self._load()

    def _remove_update(self, update_id=None, **event_args):
        if state.call("delete_update", update_id) is not None:
            LAST["changed"] = True
            self._load()

    @handle("copy_track_button", "click")
    def copy_track_button_click(self, **event_args):
        state.copy(self._track, "Tracking link copied")

    # ---- team comments
    @handle("comment_button", "click")
    def comment_button_click(self, **event_args):
        text = (self.comment_box.text or "").strip()
        if not text:
            return
        ids = list(window.PX.mentionIds(state.control(self.comment_box)))
        if state.call("add_comment", "entry", self.entry_id, text, ids) is not None:
            self.comment_box.text = ""
            LAST["changed"] = True
            self._load()

    def _delete_comment(self, comment_id=None, **event_args):
        if state.call("delete_comment", comment_id) is not None:
            self._load()

    def _open_similar(self, entry_id=None, **event_args):
        self.entry_id = entry_id
        self._load()
        body = anvil.js.get_dom_node(self).querySelector(".px-drawer-body")
        if body:
            body.scrollTop = 0
