from anvil import *

from ._anvil_designer import InviteRowTemplate
from ... import state


class InviteRow(InviteRowTemplate):
    """An invitation on the Overview (Team.my_invites). Join / Decline, then x-changed so the page reloads."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.avatar.text = state.initials(self.item.get("from"))
        self.when.text = state.ago(self.item.get("created"))

    @handle("accept_button", "click")
    def accept_button_click(self, **event_args):
        r = state.call("accept_invite", self.item["token"])
        if r:
            state.toast("You joined " + r["board"], "ok")
            self.parent.raise_event("x-changed")

    @handle("decline_button", "click")
    def decline_button_click(self, **event_args):
        if state.call("decline_invite", self.item["token"]):
            state.toast("Invitation declined")
            self.parent.raise_event("x-changed")
