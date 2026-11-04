from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import BoardColumnTemplate
from ... import px


class BoardColumn(BoardColumnTemplate):
    """One column of the Inbox board (New / Reviewing / Planned / Done). item = {status, entries}.
    Cards can be dragged here: a drop raises x-move (entry_id, status) on the board's panel. A card's click raises x-open."""

    def __init__(self, **properties):
        super().__init__(**properties)
        st, entries = self.item["status"], self.item["entries"]
        px.status(self.status_badge, st)
        self.count.text = str(len(entries))
        self.cards_panel.items = entries
        self.empty.visible = not entries
        self.cards_panel.add_event_handler("x-open", self._open)
        node = anvil.js.get_dom_node(self)
        node.setAttribute("data-col", st)
        node.addEventListener("dragover", anvil.js.report_exceptions(self._over))
        node.addEventListener("dragleave", anvil.js.report_exceptions(self._leave))
        node.addEventListener("drop", anvil.js.report_exceptions(self._drop))

    def _open(self, entry_id=None, **event_args):
        self.parent.raise_event("x-open", entry_id=entry_id)

    def _over(self, event):
        if px.DRAG["id"]:
            event.preventDefault()
            self.classes["over"] = True

    def _leave(self, event):
        node = anvil.js.get_dom_node(self)
        if not node.contains(event.relatedTarget):
            self.classes["over"] = False

    def _drop(self, event):
        event.preventDefault()
        self.classes["over"] = False
        entry_id, px.DRAG["id"] = px.DRAG["id"], None
        if entry_id:
            self.parent.raise_event("x-move", entry_id=entry_id, status=self.item["status"])
        window.PX.clearOver()
