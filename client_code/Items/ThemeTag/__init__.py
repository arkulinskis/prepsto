from anvil import *

from ._anvil_designer import ThemeTagTemplate
from ... import router, state


class ThemeTag(ThemeTagTemplate):
    """A theme (tag) on the Overview with how often it comes up; opens the inbox filtered by it. item = [tag, count]."""

    def __init__(self, **properties):
        super().__init__(**properties)
        self.tag.text = "#" + self.item[0]
        self.count.text = str(self.item[1])
        state.set_attr(self, "href", router.href("inbox", "tag", self.item[0]))
