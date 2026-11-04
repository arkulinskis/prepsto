from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import PanelTemplate


class Panel(PanelTemplate):
    """#f/<code> and #f/<code>/embed/<page url>: the PUBLIC feedback panel, no header or footer.
    Opened from a creator's plain link, or inside the slide-in frame that theme/assets/widget.js adds to their site
    ("embed": the panel fills the frame, its close button tells the host page to close it, and the host page's
    address is sent with the message)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.slug = args[0] if args else ""
        self.embed = len(args) > 1 and args[1] == "embed"
        page = args[2] if len(args) > 2 else ""
        self.missing.visible = False
        r = anvil.server.call("widget_config", self.slug)
        if not r.get("ok"):
            self.panel.visible = False
            self.missing.visible = True
            self.missing_text.text = (r.get("error") or "") + " Check the link with the person who shared it."
            return
        b = dict(r["board"])
        window.document.title = b["name"] + " · Feedback"
        self.panel.setup(b, embed=self.embed, page=page or window.document.referrer or "",
                         on_close=(lambda: self._tell("close")) if self.embed else None, on_sent=lambda: self._tell("sent"))

    def opened(self):
        self.layout.refresh("f", embed=self.embed)

    def _tell(self, msg):
        try:  # the widget's host page listens for {prepsto: "close" | "sent"}; on its own the panel just talks to itself
            window.parent.postMessage({"prepsto": msg, "slug": self.slug}, "*")
        except Exception:
            pass
