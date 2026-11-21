from anvil import *

from ._anvil_designer import BareTemplate


class Bare(BareTemplate):
    """The frame for pages people reach from other sites: the feedback panel (#f), the tracking page (#t) and the
    public roadmap (#r).
    No header, footer or tab bar; refresh() puts page-<name> on the root (and f-embed inside the widget's frame)."""

    def __init__(self, **properties):
        super().__init__(**properties)

    def refresh(self, page, embed=False):
        for name in ("f", "t", "r"):
            self.classes["page-" + name] = name == page
        self.classes["f-embed"] = bool(embed)
