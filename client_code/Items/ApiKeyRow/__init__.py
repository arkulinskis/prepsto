from anvil import *

from ._anvil_designer import ApiKeyRowTemplate
from ... import state

SCOPE_WORDS = {"read": "read tickets", "write": "update tickets and stories", "reply": "reply to senders"}


class ApiKeyRow(ApiKeyRowTemplate):
    """One API key on the Claude & API page (ApiKeys.key_dict). Only its first characters are shown: the full key was
    shown once, when it was made. Revoke raises x-revoke."""

    def __init__(self, **properties):
        super().__init__(**properties)
        k = self.item
        self.prefix.text = k["prefix"] + "…"
        st = k.get("state")
        self.state_badge.text = {"active": "active", "expired": "expired", "revoked": "revoked"}.get(st, st or "")
        self.state_badge.role = ["px-inline", "badge", "badge-good" if st == "active" else "badge-bad" if st == "revoked" else "badge-warn"]
        links = "all your links" if not k.get("links") else ", ".join(k.get("link_names") or []) or "chosen links"
        self.access.text = "Can %s · %s" % (", ".join(SCOPE_WORDS.get(s, s) for s in k.get("scopes") or ["read"]), links)
        bits = ["made " + state.short_date(k.get("created")),
                ("last used " + state.ago(k.get("last_used"))) if k.get("last_used") else "never used",
                ("expires " + state.short_date(k.get("expires"))) if k.get("expires") else "never expires"]
        if k.get("uses"):
            bits.append(state.plural(k["uses"], "request"))
        self.meta.text = " · ".join(bits)
        self.revoke_button.visible = st == "active"
        state.set_control_attr(self.revoke_button, "aria-label", "Revoke the key " + k["name"])
        self.classes["off"] = st != "active"

    @handle("revoke_button", "click")
    def revoke_button_click(self, **event_args):
        self.parent.raise_event("x-revoke", key=self.item)
