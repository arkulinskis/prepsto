from anvil import *

from ._anvil_designer import StoryMoreTemplate


class StoryMore(StoryMoreTemplate):
    """The story editor's "more" menu. Closes with "copy", "delete" or None."""

    def __init__(self, **properties):
        super().__init__(**properties)

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        self.raise_event("x-close-alert", value="copy")

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        self.raise_event("x-close-alert", value="delete")
