from anvil import *
import anvil.js

from ._anvil_designer import NotifItemTemplate
from ... import router, state

VERB = {"mention": "mentioned you", "assign": "assigned you feedback", "invite": "invited you to", "joined": "joined",
        "reply": "replied on their tracking page"}


class NotifItem(NotifItemTemplate):
    """One notification in the bell's list (Team._notif). Opens what it's about; an unread one raises x-read first."""

    def __init__(self, **properties):
        super().__init__(**properties)
        n = self.item
        k = n.get("kind")
        if k == "invite":
            target = router.href("join", n["token"]) if n.get("token") else "#home"
        elif n.get("story_id"):
            target = router.href("story", n["story_id"])
        elif n.get("entry_id"):
            target = router.href("inbox", "entry", n["entry_id"])
        else:
            target = "#links"
        state.set_attr(self, "href", target)
        actor = "A sender" if k == "reply" else (n.get("actor") or "Someone")
        self.avatar.text = "" if k == "reply" else state.initials(actor)
        self.avatar.role = ["px-notif-av", "ic-chat"] if k == "reply" else ["px-notif-av"]
        self.actor.text = actor
        self.what.text = VERB.get(k, k or "")
        self.board.text = ("" if k in ("invite", "joined") else "in ") + (n.get("board") or "")
        self.board.role = ["px-inline", "strong"] if k in ("invite", "joined") else ["px-inline", "px-notif-board"]
        self.quote.visible = bool(n.get("text")) and k not in ("invite", "joined")
        self.quote.text = n.get("text") or ""
        self.when.text = state.ago(n.get("created"))
        self.classes["unread"] = not n.get("read")
        anvil.js.get_dom_node(self).addEventListener("click", anvil.js.report_exceptions(self._click))

    def _click(self, event):
        if not self.item.get("read"):
            self.parent.raise_event("x-read", notif_id=self.item["id"])
