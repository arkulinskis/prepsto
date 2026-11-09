from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import BoardCardTemplate
from ... import px, state


class BoardCard(BoardCardTemplate):
    """A card on the Inbox board. Drag it to another column (BoardColumn handles the drop); click or Enter raises x-open."""

    def __init__(self, **properties):
        super().__init__(**properties)
        e = self.item
        px.kind(self.kind_badge, e["kind"])
        px.prio(self.prio_badge, e.get("priority"))
        px.senti(self.senti_badge, e.get("ai"))
        self.star_mark.visible = bool(e.get("starred"))
        a = e.get("assignee")
        self.assignee.visible = bool(a)
        if a:
            self.assignee.text = state.initials(a["name"])
            self.assignee.tooltip = "Assigned to " + a["name"]
        self.when.text = state.ago(e.get("created")).replace(" ago", "")
        self.tags_panel.items = ["#" + t for t in (e.get("tags") or [])[:2]]
        self.story_tag.visible = bool(e.get("story"))
        if e.get("story"):
            self.story_tag.tooltip = e["story"]["title"]
        node = anvil.js.get_dom_node(self)
        node.setAttribute("data-entry", e["id"])
        node.setAttribute("aria-label", "%s: %s" % ((px.KINDS.get(e["kind"]) or px.KINDS["other"])[0], px.short(e.get("message"), 80)))
        node.addEventListener("dragstart", anvil.js.report_exceptions(self._start))
        node.addEventListener("dragend", anvil.js.report_exceptions(self._end))
        node.addEventListener("click", anvil.js.report_exceptions(self._open))
        node.addEventListener("keydown", anvil.js.report_exceptions(self._key))

    def _start(self, event):
        px.DRAG["id"] = self.item["id"]
        self.classes["dragging"] = True
        event.dataTransfer.effectAllowed = "move"
        try:
            event.dataTransfer.setData("text/plain", self.item["id"])
        except Exception:
            pass

    def _end(self, event):
        self.classes["dragging"] = False
        window.PX.clearOver()

    def _open(self, event):
        self.parent.raise_event("x-open", entry_id=self.item["id"])

    def _key(self, event):
        if getattr(event, "key", None) == "Enter":
            self.parent.raise_event("x-open", entry_id=self.item["id"])
