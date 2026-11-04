from anvil import *

from ._anvil_designer import KindBarTemplate
from ... import px


class KindBar(KindBarTemplate):
    """One bar of "By kind" on the Overview. item = {kind, n, max}."""

    def __init__(self, **properties):
        super().__init__(**properties)
        px.kind(self.kind_badge, self.item["kind"])
        self.count.text = str(self.item["n"])
        self.bar.style["width"] = "%d%%" % round(self.item["n"] * 100.0 / max(1, self.item["max"]))
