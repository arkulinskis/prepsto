from anvil import *

from ._anvil_designer import KindChipTemplate
from ... import px, state


class KindChip(KindChipTemplate):
    """A kind of feedback to pick in the panel (Bug / Idea / ...). item = {kind, on}; pressing it raises x-kind."""

    def __init__(self, **properties):
        super().__init__(**properties)
        name, icon = px.KINDS.get(self.item["kind"]) or px.KINDS["other"]
        self.button.text = name
        self.button.role = ["px-kchip", "ic-" + icon] + (["on"] if self.item.get("on") else [])
        state.set_control_attr(self.button, "aria-pressed", "true" if self.item.get("on") else "false")
        state.set_control_attr(self.button, "data-key", self.item["kind"])

    @handle("button", "click")
    def button_click(self, **event_args):
        self.parent.raise_event("x-kind", kind=self.item["kind"])
