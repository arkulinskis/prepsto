from anvil import *

from ._anvil_designer import IdeaMatchTemplate
from ... import state


class IdeaMatch(IdeaMatchTemplate):
    """A public roadmap story that looks like what someone is typing in the panel ("Already on the roadmap").
    item = {id, title}; "+1 this instead" raises x-vote (story_id, title) on the panel."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.title.text = self.item.get("title") or ""
        state.set_control_attr(self.vote_button, "aria-label", "+1 “%s” instead" % (self.item.get("title") or ""))

    @handle("vote_button", "click")
    def vote_button_click(self, **event_args):
        self.parent.raise_event("x-vote", story_id=self.item["id"], title=self.item.get("title") or "")
