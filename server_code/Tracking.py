"""Closing the loop: the person who sent feedback can follow it.

Every entry gets a secret tracking token (entries.track). https://prepsto.com/#t/<token> shows the sender:
the steps (Received -> Under review -> Planned -> In progress -> Done), the priority the team gave it, the story it
became and how many other people asked for the same thing, and a public timeline (`updates`) of status changes and
the team's replies. The sender can answer there (kind "sender"), which notifies the team.

Team comments stay private; only `updates` rows are public. A link's owner can turn tracking off (boards.public_track).
Anyone holding the token can see the page, like a parcel-tracking link: it never shows emails or other people's feedback.
"""
import random

import anvil.server
from anvil.tables import app_tables
import anvil.tables as tables

from . import common as C

TOKEN_CHARS = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
STEPS = [("received", "Received"), ("reviewing", "Under review"), ("planned", "Planned"),
         ("in_progress", "In progress"), ("done", "Done")]
REPLIES_PER_HOUR = 10
KINDS = ("received", "status", "priority", "story", "story_status", "reply", "sender")


def new_token():
    for _ in range(20):
        t = "".join(random.choice(TOKEN_CHARS) for _ in range(22))
        if app_tables.entries.get(track=t) is None:
            return t
    raise Exception("Could not make a unique tracking code")


def tracking_on(board):
    return board is not None and C.col(board, "public_track") is not False


def ensure_track(r):
    """Older entries (before tracking existed) get their token the first time the team opens them."""
    if not r["track"]:
        r["track"] = new_token()
    return r["track"]


def log(r, kind, value="", text="", author=None, when=None):
    """One public timeline line for entry r."""
    if r is None or kind not in KINDS:
        return None
    return app_tables.updates.add_row(entry=r, board=r["board"], kind=kind, value=C.text(value, 140),
                                      text=C.text(text, 2000, multiline=True), author=author,
                                      created=when or C.now(), is_demo=bool(r["is_demo"]))


def stage(r):
    """Where the sender's feedback stands, from its own status and its story's status."""
    s, story = r["status"] or "new", r["story"]
    st = (story["status"] or "draft") if story is not None else None
    if s == "archived":
        return "closed"
    if s == "done" or st == "shipped":
        return "done"
    if st == "in_progress":
        return "in_progress"
    if s == "planned" or st == "ready":
        return "planned"
    if s == "reviewing" or story is not None:
        return "reviewing"
    return "received"


STAGE_LABELS = dict(STEPS, closed="Closed")


def _who(u, board):
    if u is None:
        return "The %s team" % (board["name"] if board is not None else "")
    return u["display_name"] or ("The %s team" % board["name"])


def update_dict(u, board, for_team=False):
    d = {"id": u.get_id(), "kind": u["kind"], "value": u["value"] or "", "text": u["text"] or "",
         "created": C.iso(u["created"])}
    if u["kind"] == "reply":
        d["who"] = _who(u["author"], board)
    if for_team:
        d["who"] = C.name_of(u["author"]) if u["author"] is not None else ("Sender" if u["kind"] == "sender" else "")
        d["mine"] = False
    return d


def timeline(r, for_team=False, me=None):
    rows = app_tables.updates.search(tables.order_by("created", ascending=True), entry=r)
    out = []
    for u in rows:
        d = update_dict(u, r["board"], for_team)
        if for_team:
            d["can_delete"] = u["kind"] == "reply" and me is not None and (u["author"] == me or r["board"]["owner"] == me)
        out.append(d)
    return out


def supporters(r):
    """How many other pieces of feedback are in the same story (people asking for the same thing)."""
    if r["story"] is None:
        return 0
    return max(0, len(app_tables.entries.search(story=r["story"])) - 1)


def team_view(r, me):
    """What the drawer shows about the sender's side."""
    try:
        ensure_track(r)
    except Exception:  # tracking columns not in the database yet
        return {"on": False, "token": "", "seen": None, "stage": stage(r), "updates": [], "waiting": False}
    return {"on": tracking_on(r["board"]), "token": ensure_track(r), "seen": C.iso(r["track_seen"]),
            "stage": stage(r), "updates": timeline(r, for_team=True, me=me), "waiting": bool(r["reply_waiting"])}


def delete_rows(entry=None, board=None):
    for u in (app_tables.updates.search(entry=entry) if entry is not None else app_tables.updates.search(board=board)):
        u.delete()


def _entry(token):
    token = C.text(token, 40)
    if len(token) < 4:
        return None
    r = app_tables.entries.get(track=token)
    if r is None or r["board"] is None or not tracking_on(r["board"]):
        return None
    return r


# ------------------------------------------------------------------------------------------- public: the sender
@anvil.server.callable
def track_get(token):
    """The sender's tracking page. Anyone with the token (it was shown only to them)."""
    r = _entry(token)
    if r is None:
        return C.fail("This tracking link doesn't work (any more). The team may have removed the feedback or turned tracking off.")
    b, story = r["board"], r["story"]
    r["track_seen"] = C.now()
    current = stage(r)
    keys = [k for k, _ in STEPS]
    at = keys.index(current) if current in keys else -1
    from . import Boards  # here, not at the top: Boards imports this module
    return C.ok(
        board={"name": b["name"], "color": b["color"] or "#2b59ff", "site_url": b["site_url"] or "", "is_open": b["is_open"] is not False},
        entry={"kind": r["kind"], "kind_label": Boards.KINDS.get(r["kind"], "Other"), "message": r["message"],
               "created": C.iso(r["created"]), "updated": C.iso(r["updated"]), "priority": r["priority"] or ""},
        stage=current, stage_label=STAGE_LABELS.get(current, current),
        steps=[{"key": k, "label": l, "done": 0 <= i <= at, "current": i == at} for i, (k, l) in enumerate(STEPS)],
        story={"title": story["title"], "status": story["status"] or "draft"} if story is not None else None,
        supporters=supporters(r), updates=timeline(r))


@anvil.server.callable
def track_list(tokens):
    """Short status of several of one person's messages (the panel's "Your feedback" list, from their browser)."""
    out = []
    for t in (tokens if isinstance(tokens, list) else [])[:30]:
        r = _entry(t)
        if r is None:
            continue
        last = app_tables.updates.search(tables.order_by("created", ascending=False), entry=r)
        last = last[0] if len(last) else None
        cur = stage(r)
        out.append({"token": r["track"], "kind": r["kind"], "message": (r["message"] or "")[:120], "created": C.iso(r["created"]),
                    "stage": cur, "stage_label": STAGE_LABELS.get(cur, cur),
                    "last": C.iso(last["created"]) if last is not None else C.iso(r["created"]),
                    "last_kind": last["kind"] if last is not None else "received"})
    return C.ok(items=out)


@anvil.server.callable
def track_reply(token, text):
    """The sender adds a detail or answers the team, from their tracking page."""
    r = _entry(token)
    if r is None:
        return C.fail("This tracking link doesn't work (any more).")
    if r["board"]["is_open"] is False:
        return C.fail("This feedback panel is closed for now, so replies are off.")
    text = C.text(text, 2000, multiline=True)
    if len(text) < 2:
        return C.fail("Write a few words first.")
    if r["track"] == "demo":  # the landing page's sample tracking page is shared by everyone: no guestbook
        return C.fail("This is the demo, so replies are switched off here. On a real tracking page your reply goes straight to the team.")
    if C.rate_limited("track_reply", REPLIES_PER_HOUR, 3600):
        return C.fail("That's a lot of replies in one hour. Please try again a bit later.")
    log(r, "sender", text=text)
    r.update(reply_waiting=True, updated=C.now())
    from . import Team
    b = r["board"]
    for u in set([b["owner"]] + ([r["assignee"]] if r["assignee"] is not None else [])):
        Team.notify(u, None, "reply", b, entry=r, text=text[:140])
    return C.ok(updates=timeline(r))


# ------------------------------------------------------------------------------------------- the team
@anvil.server.callable(require_user=True)
def post_update(entry_id, text):
    """A public reply from the team: the sender sees it on their tracking page."""
    me = C.require_user()
    from . import Inbox
    r = Inbox.owned_entry(entry_id, me)
    if r is None:
        return C.fail("That feedback doesn't exist (any more).")
    if not tracking_on(r["board"]):
        return C.fail("Tracking is off for this link: turn it on in Links to reply publicly.")
    text = C.text(text, 2000, multiline=True)
    if len(text) < 2:
        return C.fail("Write something first.")
    if C.rate_limited("update", 120, 3600):
        return C.fail("That's a lot of updates in one hour. Please try again later.")
    ensure_track(r)
    log(r, "reply", text=text, author=me)
    r.update(reply_waiting=False, updated=C.now())
    if r["status"] == "new":
        r["status"] = "reviewing"
        log(r, "status", "reviewing", author=me)
    return C.ok(tracking=team_view(r, me))


@anvil.server.callable(require_user=True)
def delete_update(update_id):
    """Take back a public reply (its author or the link's owner). Status lines stay: they're history."""
    me = C.require_user()
    u = C.row_by_id(app_tables.updates, update_id)
    if u is None:
        return C.ok()
    from . import Boards
    r = u["entry"]
    if r is None or Boards.role_in(r["board"], me) is None or u["kind"] != "reply":
        return C.fail("You can only remove the team's replies.")
    if u["author"] != me and r["board"]["owner"] != me:
        return C.fail("Only its author or the link's owner can remove a reply.")
    u.delete()
    return C.ok(tracking=team_view(r, me))
