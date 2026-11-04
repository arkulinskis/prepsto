from anvil import *

from ._anvil_designer import DayBarTemplate
from ... import state


class DayBar(DayBarTemplate):
    """One day of the Overview's 14-day chart. item = {date, count, max}; hovering (or focusing) shows the exact count."""

    def __init__(self, **properties):
        super().__init__(**properties)
        n, top = self.item["count"], max(1, self.item["max"])
        self.bar.style["height"] = "%d%%" % max(2, round(n * 100.0 / top))
        self.classes["zero"] = not n
        self.tip.text = "%s: %d" % (state.short_date(self.item["date"]), n)
