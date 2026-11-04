from anvil import *

from ._anvil_designer import ApiLogRowTemplate
from ... import state


class ApiLogRow(ApiLogRowTemplate):
    """One request made with one of your keys (ApiKeys.list_api_keys "log"): when, which key, what, and the answer."""

    def __init__(self, **properties):
        super().__init__(**properties)
        r = self.item
        self.when.text = state.ago(r.get("created"))
        self.when.tooltip = state.fmt_datetime(r.get("created"))
        code = r.get("status") or 0
        self.status.text = str(code)
        self.status.role = ["ak-log-status", "ok" if code < 400 else "bad"]
