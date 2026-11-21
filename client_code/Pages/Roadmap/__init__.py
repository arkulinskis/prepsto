from anvil import *
import anvil.js
import anvil.server
from anvil.js import window

from ._anvil_designer import RoadmapTemplate
from ... import px, state

LABELS = {"draft": "Considering", "ready": "Planned", "in_progress": "Building", "shipped": "Shipped"}
ORDER = ["draft", "ready", "in_progress", "shipped"]
FIRST = ["ready", "in_progress", "draft", "shipped"]  # the stage a phone opens on: the first of these with cards


class Roadmap(RoadmapTemplate):
    """#r/<code>: the PUBLIC roadmap + changelog of a feedback link (server_code/Roadmap.py). Stories the team marked
    public, in four stages: Considering, Planned, Building, Shipped (the changelog, dated, newest first). No target dates.
    Visitors +1 a card (Items/RoadmapCard) and get a tracking link. Columns on desktop; on a phone one stage at a time,
    picked with the segmented control (CSS hides the other columns). No header or footer: it carries the creator's
    colour, like the panel and the tracking page."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.slug = args[0] if args else ""
        self.seg = ""
        self.d: dict = {}
        self.missing.visible = False
        self.cols = [("draft", self.col_draft, self.draft_panel, self.empty_draft, self.n_draft),
                     ("ready", self.col_ready, self.ready_panel, self.empty_ready, self.n_ready),
                     ("in_progress", self.col_building, self.building_panel, self.empty_building, self.n_building),
                     ("shipped", self.col_shipped, self.shipped_panel, self.empty_shipped, self.n_shipped)]
        state.set_attr(self.home_link, "href", px.base())
        state.heading(self.board_name, 1)
        self.tabs_panel.add_event_handler("x-pick", self._pick)
        r = anvil.server.call("roadmap_get", self.slug)
        if not r.get("ok"):
            self.page.visible = False
            self.missing.visible = True
            self.missing_text.text = r.get("error") or "This roadmap doesn't exist."
            return
        self.d = r
        self._draw()

    def _draw(self):
        d, b = self.d, self.d["board"]
        window.document.title = "Roadmap · " + b["name"]
        anvil.js.get_dom_node(self.page).style.setProperty("--pc", b.get("color") or "#2b59ff")
        self.board_name.text = b["name"]
        self.updated.text = ("Roadmap · updated " + state.ago(d["updated"])) if d.get("updated") else "Roadmap"
        self.back_link.visible = bool(b.get("site_url"))
        if b.get("site_url"):
            state.set_attr(self.back_link, "href", b["site_url"])
            self.back_label.text = "Back to " + px.host(b["site_url"]).split("/")[0]
        is_open = bool(b.get("is_open"))
        self.lead.text = "What the team is considering, planning, building and has shipped." + \
            (" Want something here too? Press +1 on it." if is_open else "")
        voted = px.voted(b["slug"])
        by: dict = {k: [] for k in ORDER}
        for c in d.get("stories") or []:
            key = c["status"] if c["status"] in by else "draft"
            by[key].append(dict(c, _slug=b["slug"], _ask_email=bool(b.get("ask_email")), _open=is_open,
                                _track=voted.get(c["id"])))  # _track None = not +1'd here; "" = +1'd, no tracking link
        total = 0
        for key, col, panel, empty, count in self.cols:
            panel.items = by[key]
            empty.visible = not by[key]
            count.text = str(len(by[key]))
            total += len(by[key])
        self.board_box.visible = self.tabs_box.visible = total > 0
        self.nothing.visible = total == 0
        self.ask_card.visible = is_open
        state.set_attr(self.ask_link, "href", "#f/" + b["slug"])
        if not self.seg:
            self.seg = ([k for k in FIRST if by[k]] or ["draft"])[0]
        self._segments()

    def _segments(self):
        self.tabs_panel.items = [{"key": k, "label": LABELS[k], "on": k == self.seg} for k in ORDER]
        for key, col, panel, empty, count in self.cols:
            col.classes.update({"on": key == self.seg})

    def _pick(self, key=None, **event_args):
        k = state.focus_key()
        self.seg = key or "draft"
        self._segments()
        state.refocus(self.tabs_panel, k)
