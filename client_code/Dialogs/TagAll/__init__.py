from anvil import *

from ._anvil_designer import TagAllTemplate
from ... import state


class TagAll(TagAllTemplate):
    """Inbox bulk action: one tag for every selected piece of feedback. Closes with the tag, or None."""

    def __init__(self, count=0, **properties):
        super().__init__(**properties)
        self.title.text = "Tag %s of feedback" % state.plural(count, "piece")
        state.heading(self.title, 2)
        state.set_control_attr(self.tag_box, "maxlength", "24")

    @handle("", "show")
    def form_show(self, **event_args):
        self.tag_box.focus()

    @handle("tag_box", "pressed_enter")
    def tag_box_pressed_enter(self, **event_args):
        self.ok_button_click()

    @handle("ok_button", "click")
    def ok_button_click(self, **event_args):
        tag = (self.tag_box.text or "").strip()
        if tag:
            self.raise_event("x-close-alert", value=tag)

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
