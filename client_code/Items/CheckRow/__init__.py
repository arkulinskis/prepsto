from anvil import *

from ._anvil_designer import CheckRowTemplate


class CheckRow(CheckRowTemplate):
    """A tick box in a list (the links a new API key may see). item = {label, _on, ...}; ticking sets item["_on"]."""

    def __init__(self, **properties):
        super().__init__(**properties)

    @handle("box", "change")
    def box_change(self, **event_args):
        self.item["_on"] = self.box.checked
