from anvil import *
import anvil.js

from ... import state
from ._anvil_designer import AcRowTemplate


class AcRow(AcRowTemplate):
    """One acceptance criterion in the story editor. item = {"text": ...} (a dict the page keeps: typing updates it).
    Typing raises x-changed, Enter raises x-add (a new row below), Remove raises x-remove."""

    def __init__(self, **properties):
        super().__init__(**properties)
        box = state.control(self.box)
        box.setAttribute("maxlength", "300")
        box.setAttribute("aria-label", "Acceptance criterion")
        box.addEventListener("input", anvil.js.report_exceptions(self._input))

    def _input(self, event):
        self.item["text"] = self.box.text or ""
        self.parent.raise_event("x-changed")

    def focus_box(self):
        self.box.focus()

    @handle("box", "pressed_enter")
    def box_pressed_enter(self, **event_args):
        self.parent.raise_event("x-add", after=self.item)

    @handle("remove_button", "click")
    def remove_button_click(self, **event_args):
        self.parent.raise_event("x-remove", row=self.item)
