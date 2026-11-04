from anvil import *

from ._anvil_designer import SimilarItemTemplate
from ... import px


class SimilarItem(SimilarItemTemplate):
    """Similar feedback in the drawer: "82%  the message". Pressing it raises x-open (that entry)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.button.text = "%d%%  %s" % (round(self.item.get("score", 0) * 100), px.short(self.item.get("message"), 140))

    @handle("button", "click")
    def button_click(self, **event_args):
        self.parent.raise_event("x-open", entry_id=self.item["id"])
