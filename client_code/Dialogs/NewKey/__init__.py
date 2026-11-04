from anvil import *
import anvil.server

from ._anvil_designer import NewKeyTemplate
from ... import state

DAYS = [("30 days", 30), ("90 days", 90), ("1 year", 365), ("Never", 0)]


class NewKey(NewKeyTemplate):
    """Make an API key: a name, what it may do (read always; update; reply to senders), which links, when it expires.
    Closes with create_api_key's reply ({key, api_key}) or None. The key itself is shown next, once (KeyCreated)."""

    def __init__(self, links=(), **properties):
        super().__init__(**properties)
        self.links_box.items = [("All my links (and ones I join later)", "all"), ("Only the links I pick", "some")]
        self.links_panel.items = [{"label": b["name"] + (" (shared)" if b.get("role") == "member" else ""), "id": b["id"], "_on": False}
                                  for b in links]
        self.links_part.visible = False
        self.days_box.items = DAYS
        self.days_box.selected_value = 90
        state.set_control_attr(self.links_box, "aria-label", "Which links")
        state.set_control_attr(self.days_box, "aria-label", "Expires")
        state.set_control_attr(self.name_box, "maxlength", "60")

    @handle("", "show")
    def form_show(self, **event_args):
        self.name_box.focus()

    @handle("links_box", "change")
    def links_box_change(self, **event_args):
        self.links_part.visible = self.links_box.selected_value == "some"

    @handle("reply_box", "change")
    def reply_box_change(self, **event_args):
        if self.reply_box.checked:
            self.write_box.checked = True  # replying moves New feedback to Reviewing, which is an update

    @handle("write_box", "change")
    def write_box_change(self, **event_args):
        if not self.write_box.checked:
            self.reply_box.checked = False

    @handle("create_button", "click")
    def create_button_click(self, **event_args):
        self.error.visible = False
        scopes = ["read"] + (["write"] if self.write_box.checked else []) + (["reply"] if self.reply_box.checked else [])
        ids = []
        if self.links_box.selected_value == "some":
            ids = [it["id"] for it in self.links_panel.items if it.get("_on")]
            if not ids:
                self.error.text, self.error.visible = "Tick at least one link, or choose \"All my links\".", True
                return
        self.create_button.enabled = False
        try:
            r = anvil.server.call("create_api_key", self.name_box.text or "", scopes, ids, self.days_box.selected_value)
        finally:
            self.create_button.enabled = True
        if not r.get("ok"):
            self.error.text, self.error.visible = r.get("error") or "That didn't work.", True
            return
        self.raise_event("x-close-alert", value=r)

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
