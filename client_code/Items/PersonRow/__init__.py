from anvil import *

from ._anvil_designer import PersonRowTemplate
from ... import px, state


class PersonRow(PersonRowTemplate):
    """Someone on a link's team, or an invitation not accepted yet (Team.list_team). item has _owner (the viewer
    owns the link). Copy invite link (owner, pending ones); Remove / Cancel / Leave raise x-remove."""

    def __init__(self, **properties):
        super().__init__(**properties)
        p = self.item
        pending = p.get("status") == "invited"
        self.classes["pending"] = pending
        self.avatar.text = "" if pending else state.initials(p.get("name"))
        self.avatar.role = ["px-av", "ic-mail"] if pending else ["px-av"]
        self.name.text = (p.get("email") if pending else p.get("name")) or ""
        if p.get("me"):
            self.name.text += " (you)"
        if pending:
            self.meta.text = "invited %s · not joined yet" % state.ago(p.get("created"))
        else:
            self.meta.text = (p.get("role") or "") + ((" · " + p["email"]) if p.get("email") and not p.get("me") else "")
        self.link_button.visible = pending and bool(p.get("_owner")) and bool(p.get("token"))
        can_remove = p.get("role") != "owner" and (p.get("_owner") or p.get("me"))
        self.remove_button.visible = bool(can_remove)
        self.remove_button.text = "Leave" if p.get("me") else "Cancel" if pending else "Remove"

    @handle("link_button", "click")
    def link_button_click(self, **event_args):
        state.copy(px.base() + "#join/" + self.item["token"], "Invite link copied")

    @handle("remove_button", "click")
    def remove_button_click(self, **event_args):
        p = self.item
        self.parent.raise_event("x-remove", member_id=p.get("id"), leave=bool(p.get("me")),
                                who=p.get("email") if p.get("status") == "invited" else p.get("name"))
