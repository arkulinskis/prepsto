"""Feedback links ("boards"): create and configure them, and the two PUBLIC calls the panel uses.

A board's slug is its public code: https://prepsto.com/#f/<slug> opens the panel, and
<script src="https://prepsto.com/_/theme/widget.js" data-prepsto="<slug>"> adds a floating button that opens
the same panel in a slide-in frame (assets/widget.js). Only the owner sees a board's feedback.
"""
import random
import re

import anvil.server
from anvil.tables import app_tables
import anvil.tables as tables

from . import common as C
from . import Insights, Samples, DemoData

KINDS = {"bug": "Bug", "idea": "Idea", "praise": "Praise", "question": "Question", "other": "Other"}
DEFAULT_KINDS = ["bug", "idea", "praise", "question"]
DEFAULTS = {"prompt": "How can we make this better?", "thanks": "Thank you! We read every message.",
            "label": "Feedback", "color": "#2b59ff", "position": "right"}
SLUG_CHARS = "abcdefghjkmnpqrstuvwxyz23456789"
MAX_BOARDS = 60
SUBMITS_PER_HOUR = 12


def new_slug():
    for _ in range(50):
        s = "".join(random.choice(SLUG_CHARS) for _ in range(7))
        if app_tables.boards.get(slug=s) is None:
            return s
    raise Exception("Could not make a unique code")


def role_in(b, me):
    """"owner", "member" (active teammate) or None."""
    if b is None or me is None:
        return None
    if b["owner"] == me:
        return "owner"
    return "member" if len(app_tables.members.search(board=b, user=me, status="active")) else None


def team_board(board_id, me):
    """The board if the caller is its owner or an active teammate."""
    b = C.row_by_id(app_tables.boards, board_id)
    return b if role_in(b, me) else None


def board_dict(b, counts=True, me=None):
    d = {"id": b.get_id(), "name": b["name"], "slug": b["slug"], "site_url": b["site_url"] or "",
         "prompt": b["prompt"] or DEFAULTS["prompt"], "thanks": b["thanks"] or DEFAULTS["thanks"],
         "label": b["label"] or DEFAULTS["label"], "color": b["color"] or DEFAULTS["color"],
         "position": b["position"] or "right", "kinds": list(b["kinds"] or DEFAULT_KINDS),
         "ask_email": b["ask_email"] is not False, "ask_rating": b["ask_rating"] is not False,
         "is_open": b["is_open"] is not False, "is_sample": bool(b["is_sample"]), "created": C.iso(b["created"])}
    if counts:
        rows = app_tables.entries.search(board=b)
        d["total"] = len(rows)
        d["new"] = len([r for r in rows if r["status"] == "new"])
        d["last"] = C.iso(max([r["created"] for r in rows])) if len(rows) else None
    if me is not None:
        d["role"] = role_in(b, me)
        d["owner_name"] = C.name_of(b["owner"])
        d["team"] = 1 + len(app_tables.members.search(board=b, status="active"))
        d["pending"] = len(app_tables.members.search(board=b, status="invited")) if d["role"] == "owner" else 0
    return d


def owned_board(board_id, me):
    b = C.row_by_id(app_tables.boards, board_id)
    if b is None or b["owner"] != me:
        return None
    return b


def my_boards(me, owned_only=False):
    """Boards the caller owns, then the ones they're an active teammate on."""
    own = list(app_tables.boards.search(tables.order_by("created", ascending=True), owner=me))
    if owned_only:
        return own
    shared = [m["board"] for m in app_tables.members.search(user=me, status="active") if m["board"] is not None]
    shared.sort(key=lambda b: b["created"])
    return own + [b for b in shared if b not in own]


def ensure_starter(me):
    """A new member's first visit: give them a sample link full of feedback to explore (once)."""
    if me is None or me["starter_done"]:
        return
    me["starter_done"] = True
    if my_boards(me):
        return
    b = app_tables.boards.add_row(owner=me, name="Sample: Lumen Notes", slug=new_slug(), site_url=Samples.SITE,
                                  prompt="What would make Lumen Notes better for you?", thanks=DEFAULTS["thanks"],
                                  label="Feedback", color="#2b59ff", position="right", kinds=DEFAULT_KINDS + ["other"],
                                  ask_email=True, ask_rating=True, is_open=True, is_sample=True, created=C.now(), is_demo=False)
    Samples.fill(b, me, is_demo=False)


def _clean(data):
    data = data if isinstance(data, dict) else {}
    out = {"name": C.text(data.get("name"), 60), "site_url": C.text(data.get("site_url"), 200),
           "prompt": C.text(data.get("prompt"), 140) or DEFAULTS["prompt"],
           "thanks": C.text(data.get("thanks"), 200) or DEFAULTS["thanks"],
           "label": C.text(data.get("label"), 24) or DEFAULTS["label"]}
    color = C.text(data.get("color"), 7)
    out["color"] = color if re.match(r"^#[0-9a-fA-F]{6}$", color) else DEFAULTS["color"]
    out["position"] = "left" if data.get("position") == "left" else "right"
    out["kinds"] = []
    for k in (data.get("kinds") or []):  # the creator's order: the first kind is picked when the panel opens
        if k in KINDS and k not in out["kinds"]:
            out["kinds"].append(k)
    out["ask_email"] = bool(data.get("ask_email", True))
    out["ask_rating"] = bool(data.get("ask_rating", True))
    out["is_open"] = bool(data.get("is_open", True))
    if out["site_url"] and not re.match(r"^https?://", out["site_url"]):
        out["site_url"] = "https://" + out["site_url"]
    return out


@anvil.server.callable(require_user=True)
def list_boards():
    me = C.require_user()
    ensure_starter(me)
    return {"boards": [board_dict(b, me=me) for b in my_boards(me)], "kinds": KINDS}


@anvil.server.callable(require_user=True)
def save_board(board_id, data):
    me = C.require_user()
    d = _clean(data)
    if len(d["name"]) < 2:
        return C.fail("Give the link a name (at least 2 characters).")
    if not d["kinds"]:
        return C.fail("Choose at least one kind of feedback.")
    if board_id:
        b = owned_board(board_id, me)
        if b is None:
            return C.fail("That link doesn't exist, or it isn't yours.")
        b.update(**d)
    else:
        if len(my_boards(me, owned_only=True)) >= MAX_BOARDS:
            return C.fail("You can have up to %d links. Delete one you no longer use." % MAX_BOARDS)
        b = app_tables.boards.add_row(owner=me, slug=new_slug(), created=C.now(), is_demo=False, is_sample=False, **d)
    return C.ok(board=board_dict(b, me=me))


@anvil.server.callable(require_user=True)
def new_board_code(board_id):
    """A fresh public code (the old link and snippet stop working: useful if a link gets spammed)."""
    me = C.require_user()
    b = owned_board(board_id, me)
    if b is None:
        return C.fail("That link doesn't exist, or it isn't yours.")
    b["slug"] = new_slug()
    return C.ok(board=board_dict(b, me=me))


@anvil.server.callable(require_user=True)
def delete_board(board_id):
    me = C.require_user()
    b = owned_board(board_id, me)
    if b is None:
        return C.fail("That link doesn't exist, or it isn't yours.")
    delete_board_rows(b)
    return C.ok()


def delete_board_rows(b):
    for n in app_tables.notifications.search(board=b):
        n.delete()
    for m in app_tables.members.search(board=b):
        m.delete()
    for s in app_tables.stories.search(board=b):
        for c in app_tables.comments.search(story=s):
            c.delete()
    for e in app_tables.entries.search(board=b):
        for c in app_tables.comments.search(entry=e):
            c.delete()
        e.delete()
    for s in app_tables.stories.search(board=b):
        s.delete()
    b.delete()


# ------------------------------------------------------------------------------------------- public: the panel
@anvil.server.callable
def widget_config(slug):
    """What the panel needs to draw itself. Anyone can call it with a code."""
    DemoData.ensure_loaded()
    b = app_tables.boards.get(slug=C.text(slug, 20).lower()) if slug else None
    if b is None:
        return C.fail("This feedback link doesn't exist (any more).")
    d = board_dict(b, counts=False)
    return C.ok(board={k: d[k] for k in ("name", "slug", "site_url", "prompt", "thanks", "label", "color", "kinds",
                                         "ask_email", "ask_rating", "is_open")}, kinds=KINDS)


@anvil.server.callable
def widget_submit(slug, data):
    """Someone sends feedback through a panel. Anyone can call it; rate-limited per browser session."""
    data = data if isinstance(data, dict) else {}
    b = app_tables.boards.get(slug=C.text(slug, 20).lower()) if slug else None
    if b is None:
        return C.fail("This feedback link doesn't exist (any more).")
    if b["is_open"] is False:
        return C.fail("This feedback panel is closed for now.")
    if data.get("website"):  # honeypot field: people never fill it in, bots do
        return C.ok(thanks=b["thanks"] or DEFAULTS["thanks"])
    message = C.text(data.get("message"), 4000, multiline=True)
    if len(message) < 3:
        return C.fail("Please write a few words.")
    kinds = list(b["kinds"] or DEFAULT_KINDS)
    kind = data.get("kind") if data.get("kind") in kinds else ("other" if "other" in kinds else kinds[0])
    rating = data.get("rating")
    rating = int(rating) if isinstance(rating, (int, float)) and not isinstance(rating, bool) and 1 <= rating <= 5 else None
    email = C.text(data.get("email"), 120).replace(" ", "")
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return C.fail("That email address doesn't look right (or leave it empty).")
    if C.rate_limited("widget", SUBMITS_PER_HOUR, 3600):
        return C.fail("Thanks! You've sent a lot this hour. Please try again a bit later.")
    ctx = data.get("context") if isinstance(data.get("context"), dict) else {}
    context = {k: C.text(ctx.get(k), 200) for k in ("screen", "browser", "lang", "referrer") if ctx.get(k)}
    ai = Insights.analyze(message, kind, rating)
    prio = "high" if ai["urgency"] == "high" else ""
    app_tables.entries.add_row(board=b, kind=kind, message=message, rating=rating, email=email or None,
                               name=C.text(data.get("name"), 60) or None, page_url=C.text(data.get("page"), 300) or None,
                               context=context, status="new", priority=prio, tags=[], starred=False, story=None, ai=ai,
                               created=C.now(), updated=C.now(), is_demo=bool(b["is_demo"]))
    return C.ok(thanks=b["thanks"] or DEFAULTS["thanks"])
