from anvil import *

from ._anvil_designer import AdminLinkRowTemplate
from ... import state


class AdminLinkRow(AdminLinkRowTemplate):
    """Admin → Links: one feedback link with its owner and message count. Admins can close an abused link
    (owners can reopen it); they never see the feedback itself."""

    def __init__(self, **properties):
        super().__init__(**properties)
        b = self.item
        flags = [x for x, on in (("demo", b.get("demo")), ("sample", b.get("is_sample"))) if on]
        self.flags.visible = bool(flags)
        self.flags.text = " · ".join(flags)
        self.owner.text = "%s  %s" % (b.get("owner") or "", b.get("owner_email") or "")
        self.created.text = state.short_date(b.get("created"))
        self.total.text = str(b.get("total", 0))

    @handle("open_box", "change")
    def open_box_change(self, **event_args):
        if state.call("admin_set_board_open", self.item["id"], self.open_box.checked):
            state.toast("Link reopened" if self.open_box.checked else "Link closed", "ok")
        else:
            self.open_box.checked = not self.open_box.checked
