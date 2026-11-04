from anvil import *

from ._anvil_designer import KeyCreatedTemplate
from ... import state


class KeyCreated(KeyCreatedTemplate):
    """Shows a new API key once, with a copy button and the commands that connect Claude Code."""

    def __init__(self, key="", setup="", **properties):
        super().__init__(**properties)
        self._key = key
        self.key.text = key
        self.setup.text = setup

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        state.copy(self._key, "Key copied")

    @handle("done_button", "click")
    def done_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
