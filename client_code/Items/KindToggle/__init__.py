from anvil import *

from ._anvil_designer import KindToggleTemplate
from ... import px


class KindToggle(KindToggleTemplate):
    """A kind of feedback the panel offers (Links settings). item = {kind, on, enabled}; a change sets item["on"]
    and raises x-changed so the live preview redraws."""

    def __init__(self, **properties):
        super().__init__(**properties)
        name, icon = px.KINDS.get(self.item["kind"]) or px.KINDS["other"]
        self.box.text = name
        self.box.checked = bool(self.item.get("on"))
        self.box.enabled = self.item.get("enabled", True)
        self.classes["ic-" + icon] = True
        self.classes["on"] = self.box.checked

    @handle("box", "change")
    def box_change(self, **event_args):
        self.item["on"] = self.box.checked
        self.classes["on"] = self.box.checked
        self.parent.raise_event("x-changed")
