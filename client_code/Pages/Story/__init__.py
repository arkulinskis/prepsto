from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import StoryTemplate
from ... import exports, px, router, state

POINTS = [None, 1, 2, 3, 5, 8, 13, 21]


class Story(StoryTemplate):
    """#story/<id>: edit one user story (autosaves 0.9 s after typing; Ctrl+S saves now), its acceptance criteria,
    the client feedback behind it (add / unlink), supporting team comments with @mentions, "Redraft from feedback"
    (Insights rules today, AI later), and Export (Dialogs/Export). Leaving the page saves what's unsaved."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.story_id = args[0] if args else ""
        self.S: dict = {}
        self.bundle, self.pool, self.team = None, [], []
        self.dirty, self._timer = False, None
        self.status_box.items = [(label, key) for key, label in px.STORY_STATUSES]
        self.prio_box.items = [(label, key) for key, label in px.PRIORITIES]
        self.points_box.items = [("Not estimated" if p is None else "%d points" % p, "" if p is None else str(p)) for p in POINTS]
        for box, name in ((self.status_box, "Status"), (self.prio_box, "Priority"), (self.points_box, "Estimate")):
            state.set_control_attr(box, "aria-label", name)
        for box, n, name in ((self.title_box, 140, "Title"), (self.persona_box, 120, None), (self.goal_box, 400, None),
                             (self.benefit_box, 400, None), (self.notes_box, 4000, None), (self.comment_box, 2000, None)):
            el = state.control(box)
            el.setAttribute("maxlength", str(n))
            if name:
                el.setAttribute("aria-label", name)
            if box is not self.comment_box:
                el.addEventListener("input", anvil.js.report_exceptions(self._typed))
        state.control(self.title_box).setAttribute("rows", "1")
        state.set_control_attr(self.more_button, "aria-label", "More")
        self.ac_panel.add_event_handler("x-changed", self._ac_changed)
        self.ac_panel.add_event_handler("x-add", self._ac_add)
        self.ac_panel.add_event_handler("x-remove", self._ac_remove)
        self.quotes_panel.add_event_handler("x-unlink", self._unlink)
        self.comments_panel.add_event_handler("x-delete", self._delete_comment)
        self._keys = anvil.js.report_exceptions(self._key)
        self._load()

    # ------------------------------------------------------------------ loading + drawing
    def _load(self):
        r = state.call("get_story", self.story_id)
        if r is None:
            router.go("stories")
            return
        self.S, self.bundle, self.pool, self.team = r["story"], r["bundle"], r["pool"], r.get("team") or []
        self.provider_name = "AI" if r.get("provider") == "ai" else "rules engine"
        window.document.title = self.S["title"] + " · Prepsto"
        self._draw()

    def _draw(self):
        s = self.S
        self.meta.text = "%s · by %s" % (s.get("board") or "", s.get("author") or "")
        self.status_box.selected_value = s.get("status") or "draft"
        self.title_box.text = s.get("title") or ""
        src = s.get("source") or "manual"
        self.source.text = ("written by hand" if src == "manual" else "drafted by the " + ("AI" if src == "ai" else "rules engine")) + \
            " · updated " + state.ago(s.get("updated"))
        self.persona_box.text, self.goal_box.text, self.benefit_box.text = s.get("persona") or "", s.get("goal") or "", s.get("benefit") or ""
        self.ac_panel.items = [{"text": a} for a in (s.get("acceptance") or [""])] or [{"text": ""}]
        self.prio_box.selected_value = s.get("priority") or ""
        pts = s.get("points")
        self.points_box.selected_value = str(int(pts)) if pts is not None and int(pts) in POINTS else ""
        self.notes_box.text = s.get("notes") or ""
        entries = s.get("entries") or []
        self.fb_title.text = "Client feedback · %d" % len(entries)
        self.quotes_panel.items = entries
        self.no_fb.visible = not entries
        comments = s.get("comments") or []
        self.cm_title.text = "Supporting comments · %d" % len(comments)
        self.comments_panel.items = comments
        self.no_comments.visible = not comments
        self.provider.text = self.provider_name
        self.redraft_button.enabled = bool(entries)
        self._sentence()
        self._fit()
        window.PX.mentions(state.control(self.comment_box), [{"id": p["id"], "name": p["name"]} for p in self.team])

    def _sentence(self):
        self.p_persona.text = self.persona_box.text or "…"
        self.p_goal.text = self.goal_box.text or "…"
        has = bool((self.benefit_box.text or "").strip())
        self.p_so.visible = self.p_benefit.visible = has
        self.p_benefit.text = self.benefit_box.text or ""

    def _fit(self):
        el = state.control(self.title_box)
        el.style.height = "auto"
        if el.scrollHeight:  # 0 until the page is on screen: form_show measures again
            el.style.height = "%spx" % el.scrollHeight

    # ------------------------------------------------------------------ saving
    def _values(self):
        p = self.points_box.selected_value
        return {"title": self.title_box.text or "", "persona": self.persona_box.text or "", "goal": self.goal_box.text or "",
                "benefit": self.benefit_box.text or "", "notes": self.notes_box.text or "",
                "priority": self.prio_box.selected_value or "", "status": self.status_box.selected_value or "draft",
                "points": int(p) if p else None,
                "acceptance": [r["text"].strip() for r in self.ac_panel.items if (r.get("text") or "").strip()]}

    def _mark(self, text):
        self.saved.text = text
        self.saved.role = ["sy-saved"] + ([] if text == "Saved" else ["dirty"])

    def _changed(self):
        self.dirty = True
        self._mark("Editing…")
        state.cancel(self._timer)
        self._timer = state.later(self.save, 900)
        self._sentence()

    def _typed(self, event):
        self._fit()
        self._changed()

    def save(self):
        state.cancel(self._timer)
        self._timer = None
        if not self.dirty or not self.S:
            return True
        v = self._values()
        if len(v["title"].strip()) < 2:
            self._mark("Title needed")
            return False
        self.dirty = False
        self._mark("Saving…")
        r = anvil.server.call_s("save_story", self.story_id, v)
        if r.get("ok"):
            self.S.update(v)
            self.S["updated"] = r["story"]["updated"]
            self._mark("Saved")
            return True
        self.dirty = True
        self._mark("Not saved")
        state.toast(r.get("error") or "That didn't save.", "error")
        return False

    def leaving(self):
        if self.dirty:
            self.save()

    @handle("", "show")
    def form_show(self, **event_args):
        window.document.addEventListener("keydown", self._keys)
        state.later(self._fit, 30)

    @handle("", "hide")
    def form_hide(self, **event_args):
        window.document.removeEventListener("keydown", self._keys)

    def _key(self, event):
        if (event.ctrlKey or event.metaKey) and getattr(event, "key", None) == "s":
            event.preventDefault()
            self.dirty = True
            self.save()

    @handle("status_box", "change")
    def status_box_change(self, **event_args):
        self.dirty = True
        self.save()

    @handle("prio_box", "change")
    def prio_box_change(self, **event_args):
        self.dirty = True
        self.save()

    @handle("points_box", "change")
    def points_box_change(self, **event_args):
        self.dirty = True
        self.save()

    # ------------------------------------------------------------------ acceptance criteria
    def _ac_changed(self, **event_args):
        self._changed()

    @handle("ac_add_button", "click")
    def ac_add_button_click(self, **event_args):
        self._ac_add()

    def _ac_add(self, after=None, **event_args):
        rows = list(self.ac_panel.items)
        at = len(rows)
        for i, r in enumerate(rows):
            if r is after:
                at = i + 1
        rows.insert(at, {"text": ""})
        self.ac_panel.items = rows
        comps = self.ac_panel.get_components()
        if at < len(comps):
            getattr(comps[at], "focus_box")()

    def _ac_remove(self, row=None, **event_args):
        rows = [r for r in self.ac_panel.items if r is not row]
        if not rows:
            rows = [{"text": ""}]
        self.ac_panel.items = rows
        self._changed()

    # ------------------------------------------------------------------ feedback + comments
    @handle("add_fb_button", "click")
    def add_fb_button_click(self, **event_args):
        if not self.pool:
            state.toast("All feedback on this link is already in a story.", "error")
            return
        from ...Dialogs.AddFeedback import AddFeedback
        ids = alert(AddFeedback(pool=self.pool, board=self.S.get("board") or ""), buttons=[], role="app-dialog", large=True)
        if ids:
            self.save()
            r = state.call("link_entries", self.story_id, ids)
            if r:
                state.toast("Added " + state.plural(r["count"], "piece") + " of feedback", "ok")
                self._load()

    def _unlink(self, entry_id=None, **event_args):
        self.save()
        if state.call("unlink_entry", self.story_id, entry_id) is not None:
            state.toast("Unlinked", "ok")
            self._load()

    @handle("comment_button", "click")
    def comment_button_click(self, **event_args):
        text = (self.comment_box.text or "").strip()
        if not text:
            return
        self.save()
        ids = list(window.PX.mentionIds(state.control(self.comment_box)))
        if state.call("add_comment", "story", self.story_id, text, ids) is not None:
            self.comment_box.text = ""
            self._load()

    def _delete_comment(self, comment_id=None, **event_args):
        if state.call("delete_comment", comment_id) is not None:
            self.save()
            self._load()

    # ------------------------------------------------------------------ assist, export, more
    @handle("redraft_button", "click")
    def redraft_button_click(self, **event_args):
        if not confirm("The title, story sentence and acceptance criteria are replaced with a fresh draft. Notes and comments stay. "
                       "You can still edit it all.", title="Redraft from the feedback?", buttons=[("Cancel", False), ("Redraft", True)],
                       role="app-dialog"):
            return
        r = state.call("redraft_story", self.story_id)
        if r:
            dr = r["draft"]
            self.S.update(self._values())
            self.S.update(title=dr["title"], persona=dr["persona"], goal=dr["goal"], benefit=dr["benefit"], acceptance=dr["acceptance"])
            self._draw()
            self.dirty = True
            self.save()
            state.toast("Redrafted", "ok")

    def _current(self):
        s = dict(self.S)
        s.update(self._values())
        return s

    @handle("export_button", "click")
    def export_button_click(self, **event_args):
        self._export(None)

    @handle("json_button", "click")
    def json_button_click(self, **event_args):
        self._export("json")

    def _export(self, fmt):
        self.save()
        from ...Dialogs.Export import Export
        alert(Export(story=self._current(), bundle=self.bundle, fmt=fmt), buttons=[], role="app-dialog", large=True)

    @handle("more_button", "click")
    def more_button_click(self, **event_args):
        from ...Dialogs.StoryMore import StoryMore
        what = alert(StoryMore(), buttons=[], role="app-dialog")
        if what == "copy":
            state.copy(exports.markdown(self._current(), self.bundle), "Markdown copied")
        elif what == "delete":
            if confirm("Its comments are deleted. The linked feedback stays in your inbox.", title="Delete this story?",
                       buttons=[("Cancel", False), ("Delete", True)], role="app-dialog"):
                self.dirty = False
                if state.call("delete_story", self.story_id) is not None:
                    state.toast("Story deleted", "ok")
                    router.go("stories")
