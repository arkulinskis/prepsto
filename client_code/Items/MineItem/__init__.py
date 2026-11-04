from anvil import *
import anvil.js

from ._anvil_designer import MineItemTemplate
from ... import px, state


class MineItem(MineItemTemplate):
    """One message this browser sent, under "Your feedback" in the panel (Tracking.track_list). Opens its tracking
    page in a new tab and marks it seen."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        state.set_attr(self, "href", px.track_link(it["token"]))
        px.stage(self.stage_badge, it.get("stage"))
        self.new_dot.visible = px.fresh(it)
        self.when.text = state.ago(it.get("last"))
        anvil.js.get_dom_node(self).addEventListener("click", anvil.js.report_exceptions(self._click))

    def _click(self, event):
        px.mark_seen(self.item["token"])
        self.new_dot.visible = False
