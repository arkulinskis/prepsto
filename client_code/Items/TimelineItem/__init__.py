from anvil import *

from ._anvil_designer import TimelineItemTemplate
from ... import px, state


class TimelineItem(TimelineItemTemplate):
    """One line of the sender's public timeline (Tracking.update_dict): the drawer (_team=True) and the tracking page.
    The team can remove its own replies (x-remove)."""

    def __init__(self, **properties):
        super().__init__(**properties)
        u = self.item
        a, b, c = px.update_parts(u, team=bool(u.get("_team")))
        self.before.text, self.bold.text, self.after.text = a, b, c
        self.before.visible, self.bold.visible, self.after.visible = bool(a), bool(b), bool(c)
        self.when.text = state.ago(u.get("created"))
        self.when.tooltip = state.fmt_datetime(u.get("created"))
        self.bubble.visible = bool(u.get("text"))
        self.remove_button.visible = bool(u.get("_team") and u.get("can_delete"))
        k = u.get("kind") or ""
        done = (k == "status" and u.get("value") == "done") or (k == "story_status" and u.get("value") == "shipped")
        self.classes.update({k: True, "done": done})

    @handle("remove_button", "click")
    def remove_button_click(self, **event_args):
        self.parent.raise_event("x-remove", update_id=self.item["id"])
