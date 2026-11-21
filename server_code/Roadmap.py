"""The public roadmap + changelog of a feedback link: https://prepsto.com/#r/<code> (Pages/Roadmap).

A link's owner switches it on in Links (boards.roadmap, default off) and ticks "Show on public roadmap" on the stories
visitors may see (stories.public + an optional stories.public_note, 280 characters). The roadmap updates itself from the
stories' statuses: Considering (draft), Planned (ready), Building (in_progress), Shipped (the changelog, newest first,
dated by stories.shipped_at). No target dates are ever shown.

"+1 me too": a visitor supports a public story with one tap (roadmap card, or "Already on the roadmap" in the panel).
A vote is a normal `entries` row (kind idea, tag "+1", context {"vote": True, "note": bool}) linked to the story, with
its own tracking token, so the voter's tracking link, "Asked for by You and N others" and the story_status timeline lines
all just work, and "Update everyone who asked" reaches voters too. Note-less votes stay out of the Inbox's Open list
(Inbox.inbox_view) and collapse into one line on the Story page.

PUBLIC calls (anyone with the code): roadmap_get, roadmap_vote. They never return personas, notes, acceptance
criteria, comments, feedback messages or anyone's email. The new columns are read with C.col / guarded searches, so the
panel and story saving keep working before the Schema Mismatch is accepted in Anvil.
"""
import re

import anvil.server
from anvil.tables import app_tables

from . import common as C
from . import Insights, Tracking

SEGMENTS = [("draft", "Considering"), ("ready", "Planned"), ("in_progress", "Building"), ("shipped", "Shipped")]
VOTES_PER_HOUR = 20
NOTE_LIMIT = 280
MAX_IDEAS = 30  # public unshipped stories the panel gets for "Already on the roadmap"
VOTE_PREFIX = '+1 for "'


def available():
    """True once the database has the roadmap columns (the Schema Mismatch was accepted in Anvil)."""
    try:
        len(app_tables.boards.search(roadmap=True))
        len(app_tables.stories.search(public=True))
        len(app_tables.stories.search(public_note="-"))
        len(app_tables.stories.search(shipped_at=None))
        return True
    except Exception:
        return False


def roadmap_on(b):
    return b is not None and C.col(b, "roadmap") is True


def public_stories(b):
    """The board's stories marked public ([] before the column exists)."""
    try:
        return list(app_tables.stories.search(board=b, public=True))
    except Exception:
        return []


def is_vote(r):
    ctx = r["context"] if isinstance(r["context"], dict) else {}
    return bool(ctx.get("vote"))


def is_silent_vote(r):
    """A +1 without a note: counted, but kept out of the Open list (it says nothing new)."""
    ctx = r["context"] if isinstance(r["context"], dict) else {}
    return bool(ctx.get("vote")) and not ctx.get("note")


def asked(s):
    return len(app_tables.entries.search(story=s))


def _shipped_at(s):
    return C.col(s, "shipped_at") or s["updated"] or s["created"]


def card(s):
    """What a visitor sees of one story: nothing private."""
    status = s["status"] if s["status"] in dict(SEGMENTS) else "draft"
    return {"id": s.get_id(), "title": s["title"] or "", "note": C.col(s, "public_note") or "", "status": status,
            "asked": asked(s), "shipped": C.iso(_shipped_at(s)) if status == "shipped" else None}


def ideas(b):
    """The panel's "Already on the roadmap" list: public stories not shipped yet, {id, title} only."""
    if not roadmap_on(b):
        return []
    rows = [s for s in public_stories(b) if (s["status"] or "draft") != "shipped"]
    rows.sort(key=lambda s: s["updated"] or s["created"], reverse=True)
    return [{"id": s.get_id(), "title": s["title"] or ""} for s in rows[:MAX_IDEAS]]


def _board(slug):
    return app_tables.boards.get(slug=C.text(slug, 20).lower()) if slug else None


# ------------------------------------------------------------------------------------------- public
@anvil.server.callable
def roadmap_get(slug):
    """The public roadmap of a link. Anyone with the code; fails when the link's roadmap is off."""
    from . import DemoData  # here, not at the top: DemoData imports this module
    try:
        DemoData.ensure_loaded()  # #r/demo works on a fresh database too (the landing page links to it)
    except Exception as ex:
        print("demo load failed:", ex)
    b = _board(slug)
    if b is None:
        return C.fail("This roadmap doesn't exist (any more).")
    if not roadmap_on(b):
        return C.fail("This roadmap isn't public. The team may have switched it off.")
    rows = public_stories(b)
    cards = [card(s) for s in rows]
    cards.sort(key=lambda c: c["shipped"] or "", reverse=True)  # shipped: newest first (the others keep this order too)
    stamps = [s["updated"] for s in rows if s["updated"] is not None]
    return C.ok(board={"name": b["name"], "color": b["color"] or "#2b59ff", "site_url": b["site_url"] or "",
                       "is_open": b["is_open"] is not False, "slug": b["slug"], "ask_email": b["ask_email"] is not False,
                       "tracking": Tracking.tracking_on(b)},
                stories=cards, updated=C.iso(max(stamps)) if stamps else None,
                segments=[{"key": k, "label": label} for k, label in SEGMENTS])


@anvil.server.callable
def roadmap_vote(slug, story_id, note="", email="", website=""):
    """"+1 me too" on a public story: a normal piece of feedback linked to it (see the module docstring)."""
    b = _board(slug)
    if b is None:
        return C.fail("This roadmap doesn't exist (any more).")
    if b["is_open"] is False:
        return C.fail("This feedback panel is closed for now, so +1s are off.")
    if not roadmap_on(b):
        return C.fail("This roadmap isn't public any more.")
    s = C.row_by_id(app_tables.stories, story_id)
    if s is None or s["board"] != b or C.col(s, "public") is not True:
        return C.fail("That isn't on this roadmap (any more). Reload the page.")
    if (s["status"] or "draft") == "shipped":
        return C.fail("This one has already shipped.")
    if website:  # honeypot: people never fill it in, bots do
        return C.ok(track=None, asked=asked(s), already=False)
    voted = dict(anvil.server.session.get("votes") or {})
    sid = s.get_id()
    if sid in voted:  # this browser session already +1'd it: don't count it twice
        return C.ok(track=voted[sid] or None, asked=asked(s), already=True)
    note = C.text(note, NOTE_LIMIT)
    email = C.text(email, 120).replace(" ", "") if b["ask_email"] is not False else ""
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return C.fail("That email address doesn't look right (or leave it empty).")
    if C.rate_limited("vote", VOTES_PER_HOUR, 3600):
        return C.fail("Thanks! That's a lot of +1s this hour. Please try again a bit later.")
    message = note or (VOTE_PREFIX + (s["title"] or "") + '"')
    status = "planned" if (s["status"] or "draft") in ("ready", "in_progress") else "reviewing"
    row: dict = dict(board=b, kind="idea", message=message, rating=None, email=email or None, name=None, page_url=None,
                     context={"vote": True, "note": bool(note)}, status=status, priority="", tags=["+1"], starred=False,
                     story=s, ai=Insights.analyze(message, "idea", None), created=C.now(), updated=C.now(),
                     is_demo=bool(b["is_demo"]))
    track = None
    try:
        e = app_tables.entries.add_row(track=Tracking.new_token(), reply_waiting=False, **row)
        Tracking.log(e, "received")
        Tracking.log(e, "story", s["title"])
        track = e["track"] if Tracking.tracking_on(b) else None
    except Exception as ex:  # the tracking columns aren't in the database yet: still count it
        print("tracking unavailable:", ex)
        app_tables.entries.add_row(**row)
    voted[sid] = track or ""
    getattr(anvil.server, "session")["votes"] = voted
    return C.ok(track=track, asked=asked(s), already=False)
