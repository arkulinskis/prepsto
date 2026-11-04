from anvil import *

from ._anvil_designer import LinkPickTemplate
from ... import router, state


class LinkPick(LinkPickTemplate):
    """One link in the Links page's picker row (or "New link"). item = a board dict + on, or {_new: True, on} ("New link")."""

    def __init__(self, **properties):
        super().__init__(**properties)
        b = self.item
        self.classes["on"] = bool(b.get("on"))
        if b.get("_new"):
            self.classes["add"] = True
            self.dot.visible = False
            self.name.text = "+ New link"
            self.meta.visible = False
            state.set_attr(self, "href", router.href("links", "new"))
            return
        state.set_attr(self, "href", router.href("links", b["id"]))
        self.dot.style["background"] = b.get("color") or "#2b59ff"
        self.name.text = b["name"]
        bits = [str(b.get("total", 0))]
        if b.get("new"):
            bits.append("%d new" % b["new"])
        if not b.get("is_open"):
            bits.append("closed")
        if b.get("role") == "member":
            bits.append("shared")
        elif (b.get("team") or 1) > 1:
            bits.append("team of %d" % b["team"])
        self.meta.text = " · ".join(bits)
        if b.get("on"):
            state.set_attr(self, "aria-current", "page")
