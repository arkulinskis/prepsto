from anvil import *

from ._anvil_designer import TabButtonTemplate
from ... import state


class TabButton(TabButtonTemplate):
    """A tab or a segmented-control choice. item = {key, label, count (optional), on, icon (optional)}.
    Pressing it raises x-pick (key) on the panel. The panel's role decides the look (tabs, seg, ex-tabs)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        self.button.text = it["label"] + (" %s" % it["count"] if it.get("count") is not None else "")
        roles = ["px-tab"] + (["on"] if it.get("on") else []) + (["ic-" + it["icon"]] if it.get("icon") else [])
        self.button.role = roles
        state.set_control_attr(self.button, "aria-pressed", "true" if it.get("on") else "false")
        state.set_control_attr(self.button, "data-key", it["key"])

    @handle("button", "click")
    def button_click(self, **event_args):
        self.parent.raise_event("x-pick", key=self.item["key"])
