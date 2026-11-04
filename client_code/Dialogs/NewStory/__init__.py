from anvil import *

from ._anvil_designer import NewStoryTemplate
from ... import state


class NewStory(NewStoryTemplate):
    """Stories → New story: pick the link, then create a blank story. Closes with the new story's id, or None."""

    def __init__(self, boards=(), selected="", **properties):
        super().__init__(**properties)
        self.board_box.items = [(b["name"], b["id"]) for b in boards]
        if selected and any(b["id"] == selected for b in boards):
            self.board_box.selected_value = selected

    @handle("ok_button", "click")
    def ok_button_click(self, **event_args):
        r = state.call("create_story", self.board_box.selected_value, [])
        if r:
            self.raise_event("x-close-alert", value=r["story"]["id"])

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
