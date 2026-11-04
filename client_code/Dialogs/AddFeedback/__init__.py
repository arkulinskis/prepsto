from anvil import *

from ._anvil_designer import AddFeedbackTemplate


class AddFeedback(AddFeedbackTemplate):
    """Story editor → Add client feedback: tick feedback from the same link that isn't in a story yet.
    Closes with the ticked entry ids (maybe empty), or None."""

    def __init__(self, pool=(), board="", **properties):
        super().__init__(**properties)
        self.intro.text = "Feedback from %s that isn't in a story yet." % board
        self.pick_panel.items = [dict(e, _on=False) for e in pool]

    @handle("ok_button", "click")
    def ok_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=[e["id"] for e in self.pick_panel.items if e.get("_on")])

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
