from anvil import *

from ._anvil_designer import StoryCardTemplate
from ... import px, router, state


class StoryCard(StoryCardTemplate):
    """A user story on the Stories page (Stories.story_dict). The whole card links to #story/<id>."""

    def __init__(self, **properties):
        super().__init__(**properties)
        s = self.item
        state.set_attr(self, "href", router.href("story", s["id"]))
        px.story_state(self.state_badge, s.get("status"))
        px.prio(self.prio_badge, s.get("priority"))
        self.points.visible = s.get("points") is not None
        self.points.text = "%s pts" % s.get("points")
        if s.get("persona") or s.get("goal"):
            self.sentence.text = "As a %s, I want %s%s." % (s.get("persona") or "…", s.get("goal") or "…",
                                                           (", so that " + s["benefit"]) if s.get("benefit") else "")
        else:
            self.sentence.text = "No story text yet."
            self.sentence.role = ["st-as", "faint"]
        self.counts.text = "%d client · %d team" % (s.get("feedback_count", 0), s.get("comment_count", 0))
        self.kinds_panel.items = [(px.KINDS.get(k) or px.KINDS["other"])[0] for k in s.get("kinds") or []]
