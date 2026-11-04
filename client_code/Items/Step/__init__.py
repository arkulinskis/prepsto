from anvil import *

from ._anvil_designer import StepTemplate
from ... import state


class Step(StepTemplate):
    """One step on the tracking page (Received → Done). item = {label, done, current, _closed}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        s, closed = self.item, bool(self.item.get("_closed"))
        self.classes.update({"done": bool(s.get("done")) and not closed, "current": bool(s.get("current")) and not closed})
        self.classes["first"] = bool(s.get("_first"))
        self.tick.visible = bool(s.get("done")) and not closed
        if s.get("current") and not closed:
            state.set_attr(self, "aria-current", "step")
