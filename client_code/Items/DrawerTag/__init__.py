from anvil import *

from ._anvil_designer import DrawerTagTemplate
from ... import state


class DrawerTag(DrawerTagTemplate):
    """A tag in the drawer. item = {tag, suggested}: a set tag has × (x-untag), a suggested one is "+ tag" (x-addtag)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        t = self.item["tag"]
        if self.item.get("suggested"):
            self.tag.visible = False
            self.remove_button.text = "+ " + t
            self.remove_button.role = ["px-tag-add"]
            state.set_control_attr(self.remove_button, "aria-label", "Add the tag " + t)
            self.classes["ai"] = True
        else:
            self.tag.text = "#" + t
            state.set_control_attr(self.remove_button, "aria-label", "Remove " + t)

    @handle("remove_button", "click")
    def remove_button_click(self, **event_args):
        self.parent.raise_event("x-addtag" if self.item.get("suggested") else "x-untag", tag=self.item["tag"])
