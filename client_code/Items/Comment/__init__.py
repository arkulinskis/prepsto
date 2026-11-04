from anvil import *

from ._anvil_designer import CommentTemplate
from ... import state


class Comment(CommentTemplate):
    """A team comment (drawer + story editor). Inbox.comment_dict. A comment that mentions you has a blue edge.
    Delete (its author or the link's owner) raises x-delete."""

    def __init__(self, **properties):
        super().__init__(**properties)
        c = self.item
        self.avatar.text = state.initials(c.get("author"))
        self.when.text = state.ago(c.get("created"))
        self.delete_button.visible = bool(c.get("can_delete") or c.get("mine"))
        state.set_control_attr(self.delete_button, "aria-label", "Delete comment")
        self.classes["to-me"] = bool(c.get("me_mentioned"))

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        self.parent.raise_event("x-delete", comment_id=self.item["id"])
