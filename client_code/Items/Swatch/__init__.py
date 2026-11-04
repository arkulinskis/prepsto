from anvil import *
import anvil.js

from ._anvil_designer import SwatchTemplate


class Swatch(SwatchTemplate):
    """A colour choice for a link's panel. item = {color, on, enabled}; pressing it raises x-color."""

    def __init__(self, **properties):
        super().__init__(**properties)
        node = anvil.js.get_dom_node(self)
        node.style.background = self.item["color"]
        node.setAttribute("aria-label", "Colour " + self.item["color"])
        node.setAttribute("aria-pressed", "true" if self.item.get("on") else "false")
        if not self.item.get("enabled", True):
            node.setAttribute("disabled", "")
        self.classes["on"] = bool(self.item.get("on"))
        node.addEventListener("click", anvil.js.report_exceptions(self.pick_click))

    def pick_click(self, event):
        self.parent.raise_event("x-color", color=self.item["color"])
