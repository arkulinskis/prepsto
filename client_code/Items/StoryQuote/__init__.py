from anvil import *

from ._anvil_designer import StoryQuoteTemplate
from ... import px, state


class StoryQuote(StoryQuoteTemplate):
    """A piece of client feedback linked to the story (with its team comments under it). Unlink raises x-unlink."""

    def __init__(self, **properties):
        super().__init__(**properties)
        e = self.item
        px.kind(self.kind_badge, e["kind"])
        px.stars(self.stars_badge, e.get("rating"))
        self.meta.text = "%s · %s" % (px.who(e), state.ago(e.get("created")))
        self.sub_panel.items = ["%s: %s" % (c["author"], c["body"]) for c in e.get("comments") or []]
        self.sub_panel.visible = bool(e.get("comments"))

    @handle("unlink_button", "click")
    def unlink_button_click(self, **event_args):
        self.parent.raise_event("x-unlink", entry_id=self.item["id"])
