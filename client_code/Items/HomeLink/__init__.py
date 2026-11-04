from anvil import *

from ._anvil_designer import HomeLinkTemplate
from ... import px, state


class HomeLink(HomeLinkTemplate):
    """One of the member's feedback links on the Overview, with a copy button for its public link."""

    def __init__(self, **properties):
        super().__init__(**properties)
        b = self.item
        self.dot.style["background"] = b.get("color") or "#2b59ff"
        bits = ["shared by " + b.get("owner_name", "") if b.get("role") == "member" else b["slug"],
                "%d total" % b.get("total", 0), "%d new" % b.get("new", 0)]
        if (b.get("team") or 1) > 1:
            bits.append(state.plural(b["team"], "person", "people"))
        self.meta.text = " · ".join(bits)
        state.set_control_attr(self.copy_button, "aria-label", "Copy the link of " + b["name"])

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        state.copy(px.link(self.item), "Link copied")
