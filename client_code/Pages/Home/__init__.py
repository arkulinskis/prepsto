from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import HomeTemplate
from ... import router, state


class Home(HomeTemplate):
    """#home, the Overview: numbers for the last weeks, a 14-day chart, kinds + sentiment, top themes, invitations,
    "assigned to you", "needs attention" (new + urgent), the latest feedback, and the member's links with a quick copy.
    Clicking feedback opens the drawer (Dialogs/Drawer); when something changed there, the page reloads."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        for panel in (self.assigned_panel, self.attention_panel, self.recent_panel):
            panel.add_event_handler("x-open", self._open)
        self.invites_panel.add_event_handler("x-changed", self._invites_changed)
        state.heading(self.hello, 1)
        self._load()

    def _load(self, **event_args):
        d = state.call("get_overview")
        if d is None:
            return
        hour = anvil.js.new(window.Date).getHours()
        hi = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
        self.hello.text = "%s, %s" % (hi, (d.get("name") or "there").split(" ")[0])
        self.waiting.text = (state.plural(d["new"], "new piece", "new pieces") + " of feedback waiting for you.") if d["new"] \
            else "Inbox zero. Nicely done."
        self.s_new.text, self.s_open.text = str(d["new"]), "%d open in total" % d["open"]
        self.s_week.text = str(d["week"])
        self._trend(d["week"], d["prev_week"])
        self.s_rating.text = "–" if d.get("avg_rating") is None else "%s/5" % d["avg_rating"]
        self.s_rated.text = state.plural(d["rated"], "rating") + ", 30 days"
        self.s_stories.text, self.s_ready.text = str(d["stories"]), "%d ready to build" % d["stories_ready"]
        self.invites_panel.items = d.get("invites") or []
        self.invites_panel.visible = bool(d.get("invites"))
        top = max([x["count"] for x in d["daily"]] + [1])
        self.days_panel.items = [dict(x, max=top) for x in d["daily"]]
        self.axis_from.text = state.short_date(d["daily"][0]["date"]) if d["daily"] else ""
        rows = lambda xs: [dict(e, _board=True) for e in xs]  # noqa: E731
        self.assigned_part.visible = bool(d["assigned"])
        self.assigned_panel.items = rows(d["assigned"])
        self.attention_part.visible = bool(d["attention"])
        self.attention_panel.items = rows(d["attention"])
        self.recent_panel.items = rows(d["recent"])
        self.recent_panel.visible = bool(d["recent"])
        self.no_recent.visible = not d["recent"]
        s = d["sentiment"]
        total = s["positive"] + s["neutral"] + s["negative"]
        self.senti_part.visible, self.no_senti.visible = bool(total), not total
        for el, k in ((self.sb_pos, "positive"), (self.sb_neu, "neutral"), (self.sb_neg, "negative")):
            el.style["flex"] = str(s[k])
            el.visible = bool(s[k])
        for lbl, k in ((self.lg_pos, "positive"), (self.lg_neu, "neutral"), (self.lg_neg, "negative")):
            lbl.text = "%s %d" % (k, s[k])
        state.set_attr(self.senti_bar, "aria-label", "%d positive, %d neutral, %d negative" % (s["positive"], s["neutral"], s["negative"]))
        self.provider.text = "Read by the %s. Ready for AI analysis." % ("AI" if d.get("provider") == "ai" else "built-in rules engine")
        kinds = sorted(d["kinds"].items(), key=lambda kv: -kv[1])
        top_kind = max([n for _, n in kinds] + [1])
        self.kinds_panel.items = [{"kind": k, "n": n, "max": top_kind} for k, n in kinds]
        self.no_kinds.visible = not kinds
        self.tags_panel.items = d["tags"]
        self.no_tags.visible = not d["tags"]
        self.links_panel.items = d["boards"]
        self.first_link.visible = not d["boards"]

    def _trend(self, now, before):
        if not before and not now:
            self.s_trend.text, self.s_trend.role = "no feedback yet", ["hm-small"]
        elif not before:
            self.s_trend.text, self.s_trend.role = "new this week", ["hm-small", "up"]
        else:
            p = round((now - before) * 100.0 / before)
            self.s_trend.text = "%s%d%% vs last week" % ("+" if p > 0 else "", p)
            self.s_trend.role = ["hm-small", "up" if p > 0 else "down" if p < 0 else "flat"]

    def _invites_changed(self, **event_args):
        shell = getattr(self, "layout", None)
        if shell is not None:
            shell.refresh_bell(force=True)
        self._load()

    def mine_click(self, event):
        event.preventDefault()
        f = dict(state.store_get("inbox.filters", {}) or {})
        f.update(mine=True, board="", status="open")
        state.store_set("inbox.filters", f)
        router.go("inbox")

    def _open(self, entry_id=None, **event_args):
        from ...Dialogs.Drawer import LAST, Drawer
        r = alert(Drawer(entry_id=entry_id), buttons=[], role="px-drawer", large=True, dismissible=True)
        if isinstance(r, dict) and r.get("go"):
            router.go(*r["go"])
        elif r or LAST["changed"]:
            self._load()
