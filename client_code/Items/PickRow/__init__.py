from anvil import *

from ._anvil_designer import PickRowTemplate
from ... import px


class PickRow(PickRowTemplate):
    """A piece of feedback to tick in "Add client feedback" (story editor). item = an entry dict; ticking sets
    item["_on"], which the dialog reads."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.box.text = "%s · %s" % ((px.KINDS.get(self.item["kind"]) or px.KINDS["other"])[0], self.item.get("message") or "")

    @handle("box", "change")
    def box_change(self, **event_args):
        self.item["_on"] = self.box.checked
        self.classes["on"] = self.box.checked
