from anvil import *
import anvil.js

from ._anvil_designer import EntryRowTemplate
from ... import px, state


class EntryRow(EntryRowTemplate):
    """One piece of feedback in a list (Overview + Inbox). item = Inbox.entry_dict plus the page's extras:
    _select (show the tick box), _picked (ticked), _board (show the link's name).
    Clicking (or Enter) raises x-open; the tick box raises x-pick (entry_id, on)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        e = self.item
        px.kind(self.kind_badge, e["kind"])
        px.prio(self.prio_badge, e.get("priority"))
        px.status(self.status_badge, e.get("status"))
        px.senti(self.senti_badge, e.get("ai"))
        px.stars(self.stars_badge, e.get("rating"))
        self.star_mark.visible = bool(e.get("starred"))
        self.who.text = px.who(e)
        a = e.get("assignee")
        self.assignee.visible = bool(a)
        if a:
            self.assignee.text = state.initials(a["name"])
            self.assignee.tooltip = "Assigned to " + a["name"]
        self.when.text = state.ago(e.get("created"))
        self.replied.visible = bool(e.get("reply_waiting"))
        self.tags_panel.items = ["#" + t for t in e.get("tags") or []]
        st = e.get("story")
        self.story_tag.visible = bool(st)
        if st:
            self.story_tag.text = px.short(st["title"], 30)
        self.board.visible = bool(e.get("_board"))
        self.board.text = e.get("board") or ""
        self.sel_box.visible = bool(e.get("_select"))
        self.dom_nodes["pick"].checked = bool(e.get("_picked"))
        self.classes["is-new"] = e.get("status") == "new"
        self.classes["picked"] = bool(e.get("_picked"))
        node = anvil.js.get_dom_node(self)
        node.setAttribute("data-entry", e["id"])
        kind_name = (px.KINDS.get(e["kind"]) or px.KINDS["other"])[0]
        node.setAttribute("aria-label", "%s from %s: %s" % (kind_name, px.who(e), px.short(e.get("message"), 80)))
        node.addEventListener("click", anvil.js.report_exceptions(self._click))
        node.addEventListener("keydown", anvil.js.report_exceptions(self._key))

    def _click(self, event):
        if event.target.closest(".px-sel"):
            if str(event.target.tagName) == "INPUT":
                self.parent.raise_event("x-pick", entry_id=self.item["id"], on=bool(self.dom_nodes["pick"].checked))
            return
        self.parent.raise_event("x-open", entry_id=self.item["id"])

    def _key(self, event):
        if event.key == "Enter" and str(getattr(event.target, "tagName", "")) != "INPUT":
            self.parent.raise_event("x-open", entry_id=self.item["id"])
