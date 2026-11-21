"""Prepsto's shared client pieces: the words for kinds, statuses, priorities, stages and story states, the badges (Labels
with roles: px-kind, px-status, px-prio, px-senti, px-stage, st-state, px-tag, px-stars), link and snippet builders,
the sender's timeline wording, and the list of feedback this browser sent (for the panel's "Your feedback").

Badges: a Label gets text + roles, the icon comes from the role ic-<name> (icons.css), the colour from the CSS in app.css.
    px.kind(label, "bug")   px.status(label, "planned")   px.prio(label, "high")   px.stars(label, 4)
"""
import anvil.js
from anvil.js import window

from . import state

KINDS = {"bug": ("Bug", "bug"), "idea": ("Idea", "bulb"), "praise": ("Praise", "praise"),
         "question": ("Question", "info"), "other": ("Other", "chat")}
KIND_ORDER = ["bug", "idea", "praise", "question", "other"]
STATUSES = [("new", "New"), ("reviewing", "Reviewing"), ("planned", "Planned"), ("done", "Done"), ("archived", "Archived")]
PRIORITIES = [("", "No priority"), ("low", "Low"), ("medium", "Medium"), ("high", "High"), ("urgent", "Urgent")]
STORY_STATUSES = [("draft", "Draft"), ("ready", "Ready"), ("in_progress", "In progress"), ("shipped", "Shipped")]
STAGES = [("received", "Received"), ("reviewing", "Under review"), ("planned", "Planned"), ("in_progress", "In progress"),
          ("done", "Done"), ("closed", "Closed")]
PLACEHOLDER = {"bug": "What went wrong? What did you expect to happen?", "idea": "What would you like to see?",
               "praise": "What do you like?", "question": "What would you like to know?", "other": "Tell us anything."}
DRAG: dict = {"id": None}  # the board card being dragged (Inbox board view)
DIALOG: dict = {"form": None}  # the open drawer: router.show closes it when the page changes (Back button, bell links)


def label_of(pairs, key):
    for k, v in pairs:
        if k == key:
            return v
    return key or ""


# ------------------------------------------------------------------ badges
def kind(lbl, k):
    name, icon = KINDS.get(k) or KINDS["other"]
    lbl.text = name
    lbl.role = ["px-kind", k if k in KINDS else "other", "ic-" + icon]


def status(lbl, s):
    lbl.text = label_of(STATUSES, s)
    lbl.role = ["px-status", s or "new"]


def prio(lbl, p):
    lbl.visible = bool(p)
    lbl.text = ("!! " if p == "urgent" else "! " if p == "high" else "") + (p or "")
    lbl.role = ["px-prio", p or "none"]


def senti(lbl, ai):
    s = (ai or {}).get("sentiment") or ""
    lbl.visible = bool(s)
    lbl.text = s
    lbl.role = ["px-senti", s or "neutral"]
    lbl.tooltip = "Sentiment (%s)" % ((ai or {}).get("provider") or "rules")


def stars(lbl, n):
    """Five stars, the first n filled (a gradient over the text, so it stays one Label)."""
    n = int(n or 0)
    lbl.visible = n > 0
    lbl.text = "★★★★★"
    lbl.role = ["px-stars"]
    lbl.tooltip = "%d out of 5" % n
    anvil.js.get_dom_node(lbl).style.setProperty("--n", str(n))


def stage(lbl, s):
    lbl.text = label_of(STAGES, s)
    lbl.role = ["px-stage", s or "received"]


def story_state(lbl, s):
    lbl.text = label_of(STORY_STATUSES, s)
    lbl.role = ["st-state", s or "draft"]


# ------------------------------------------------------------------ small text helpers
def who(e):
    if e.get("name"):
        return e["name"]
    return (e.get("email") or "").split("@")[0] if e.get("email") else "Anonymous"


def ua(text):
    """'Mozilla/5.0 (Windows NT 10.0; ...) Chrome/141.0 ...' -> 'Chrome 141 · Windows'."""
    return window.PX.ua(text or "")


def host(url):
    return window.PX.host(url or "")


def short(text, n):
    text = text or ""
    return text if len(text) <= n else text[:n - 2] + "…"


# ------------------------------------------------------------------ links, snippets
def base():
    """https://prepsto.com/ (or wherever the app runs)."""
    loc = window.location
    path = loc.pathname
    return loc.origin + path[:path.rfind("/") + 1]


def link(b):
    return base() + "#f/" + b["slug"]


def track_link(token):
    return base() + "#t/" + token


def roadmap_link(slug):
    return base() + "#r/" + slug


def silent_vote(e):
    """A roadmap "+1" without a note (Roadmap.is_silent_vote): counted, not quoted."""
    ctx = e.get("context") or {}
    return bool(ctx.get("vote")) and not ctx.get("note")


def snippet(b):
    return ('<script src="%s_/theme/widget.js" data-prepsto="%s" data-color="%s" data-label="%s" data-position="%s" async></scr'
            'ipt>') % (base(), b["slug"], b["color"], (b.get("label") or "").replace('"', ""), b["position"])


def anchor(b):
    return '<a href="%s" target="_blank" rel="noopener">%s</a>' % (link(b), window.UI.esc(b.get("label") or "Feedback"))


# ------------------------------------------------------------------ the sender's timeline (Tracking.py)
STATUS_WORDS = {"new": "Back to Received", "reviewing": "Under review", "planned": "Planned", "done": "Done",
                "archived": "Closed for now"}
STORY_WORDS = {"ready": "Ready to build", "in_progress": "Work started", "shipped": "Shipped"}


def update_parts(u, team=False):
    """One timeline line as (before, bold, after): the middle part is shown in bold."""
    k, v = u.get("kind"), u.get("value") or ""
    if k == "received":
        return ("Feedback received", "", "")
    if k == "status":
        return ("Status: ", STATUS_WORDS.get(v, v), "")
    if k == "priority":
        return ("Priority set to ", label_of(PRIORITIES, v), "") if v else ("Priority removed", "", "")
    if k == "story":
        return ("Added to the plan: ", v, "")
    if k == "story_status":
        return ("", STORY_WORDS.get(v, v), "")
    if k == "reply":
        return ("", u.get("who") or "The team", " replied")
    if k == "sender":
        if team:
            return ("", "Sender", " replied")
        w = u.get("who")
        return ("", w if w and w != "Sender" else "You", " added")
    return (k or "", "", "")


# ------------------------------------------------------------------ "Your feedback" in the panel (this browser only)
def mine_list(slug):
    everything = state.store_get("mine", {}) or {}
    return list(everything.get(slug) or [])[:30]


def mine_add(slug, item):
    """item = {"t": tracking token, "at": ISO time} (+ "s": the story id of a roadmap "+1"; MineItem ignores it)."""
    everything = dict(state.store_get("mine", {}) or {})
    rest = [x for x in (everything.get(slug) or []) if x.get("t") != item["t"]]
    everything[slug] = ([item] + rest)[:30]
    state.store_set("mine", everything)


def seen(token):
    return (state.store_get("seen", {}) or {}).get(token) or ""


def mark_seen(token):
    s = dict(state.store_get("seen", {}) or {})
    s[token] = anvil.js.new(window.Date).toISOString()
    state.store_set("seen", s)


def fresh(it):
    """An update the person hasn't looked at yet (from the team, not their own)."""
    return it.get("last_kind") not in ("received", "sender") and (it.get("last") or "") > seen(it.get("token"))


# ------------------------------------------------------------------ "+1 me too" (public roadmap + panel), this browser only
def voted(slug):
    """{story id: tracking token or ""} for the stories this browser +1'd on this link."""
    out = {}
    for x in mine_list(slug):
        if x.get("s"):
            out[x["s"]] = x.get("t") or ""
    for sid in ((state.store_get("votes", {}) or {}).get(slug) or []):
        out.setdefault(sid, "")
    return out


def vote_add(slug, story_id, track):
    """Remember a +1: in "Your feedback" when it has a tracking link, else in a plain list (tracking off)."""
    if track:
        mine_add(slug, {"t": track, "at": anvil.js.new(window.Date).toISOString(), "s": story_id})
        mark_seen(track)
        return
    everything = dict(state.store_get("votes", {}) or {})
    ids = [x for x in (everything.get(slug) or []) if x != story_id]
    everything[slug] = ([story_id] + ids)[:100]
    state.store_set("votes", everything)


STOP = set("a an and are as at be but by can could do for from get have i if in is it its just let like make me more my "
           "no not of on or our please so some than that the their them then there these they this to too us very want "
           "was we what when which while will with would you your yours also really much need needs".split())


def words(text):
    """The words that carry meaning in a text: lower case, 3+ letters, no common little words, a plural 's' dropped."""
    out, cur = set(), []
    for ch in (text or "").lower() + " ":
        if ch.isalnum():
            cur.append(ch)
            continue
        if cur:
            w = "".join(cur)
            cur = []
            if len(w) >= 3 and w not in STOP:
                out.add(w[:-1] if len(w) > 4 and w.endswith("s") else w)
    return out


def matches(text, ideas, limit=3):
    """Public roadmap stories that look like what someone is typing (word overlap), best first."""
    mine = words(text)
    if len(mine) < 2:
        return []
    scored = []
    for idea in ideas or []:
        theirs = words(idea.get("title"))
        if not theirs:
            continue
        common = len(mine & theirs)
        if common >= 2 or (common == 1 and len(theirs) <= 2):
            scored.append((common / float(len(theirs)), common, idea))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return [x[2] for x in scored[:limit]]
