"""Demo content, so the app never looks empty. Loaded automatically the first time anyone opens the app
(ensure_loaded), removed or reloaded from Admin -> Demo data. Removing it is remembered: it doesn't come back.

The demo is one public feedback link, code "demo" (#f/demo, used by the landing page's "Try the panel"),
owned by a demo account, filled with Samples. Feedback sent through it is flagged is_demo too.
Demo users have is_demo=True and @example.com emails; they can't sign in (no password).
(New members get their own starter sample: Boards.ensure_starter.)
"""
import datetime as dt

from anvil.tables import app_tables

from . import common as C
from . import Samples, Tracking

DEMO_SLUG = "demo"
DEMO_TRACK = "demo"
DEMO_VERSION = 2  # bump to reload the demo everywhere once (2: tracking timelines + #t/demo)
DEMO_USERS = [
    ("Prepsto Team", "team.demo@example.com"),
    ("Maya Chen", "maya.demo@example.com"),     # teammates on the demo link
    ("Theo Martin", "theo.demo@example.com"),
]

# Tables that hold demo rows (each has an is_demo column). Children before parents.
DEMO_TABLES = ["notifications", "updates", "comments", "entries", "stories", "members", "boards"]


def state():
    return C.get_setting("demo", "never")  # "never" | "loaded" | "removed"


def ensure_loaded():
    """Called by the public panel and the landing page: loads the demo once, unless an admin removed it."""
    st = state()
    if st == "never":
        load()
    elif st == "loaded":
        if app_tables.boards.get(slug=DEMO_SLUG) is None:  # lost (e.g. a reload that failed half-way): bring it back
            load()
        elif C.get_setting("demo_version", 1) != DEMO_VERSION and Tracking.available():
            load()  # upgrade once, only when the database has the new columns


def load():
    remove(remember=False)
    users = []
    for name, email in DEMO_USERS:
        u = app_tables.users.get(email=email) or app_tables.users.add_row(email=email, enabled=False)
        u.update(display_name=name, is_demo=True, starter_done=True, signed_up=C.now() - dt.timedelta(days=30))
        users.append(u)
    b = app_tables.boards.add_row(owner=users[0], name="Lumen Notes (demo)", slug=DEMO_SLUG, site_url=Samples.SITE,
                                  prompt="What would make Lumen Notes better for you?",
                                  thanks="Thank you! This is the Prepsto demo, so nothing will happen with it, but now you know how it feels.",
                                  label="Feedback", color="#2b59ff", position="right",
                                  kinds=["bug", "idea", "praise", "question", "other"], ask_email=True, ask_rating=True,
                                  is_open=True, is_sample=False, created=C.now() - dt.timedelta(days=20), is_demo=True)
    tracking = Tracking.available()
    Samples.fill(b, users[0], is_demo=True, tracking=tracking)
    for u in users[1:]:
        app_tables.members.add_row(board=b, user=u, email=u["email"], role="member", status="active", token=None,
                                   invited_by=users[0], created=C.now() - dt.timedelta(days=18),
                                   joined=C.now() - dt.timedelta(days=17), is_demo=True)
    urgent = app_tables.entries.get(board=b, priority="urgent")
    if urgent is not None:
        urgent["assignee"] = users[1]
        app_tables.comments.add_row(author=users[2], entry=urgent, body="@Maya Chen can you check the rename code path?",
                                    mentions=[users[1].get_id()], created=C.now() - dt.timedelta(hours=20), is_demo=True)
    lea = [e for e in app_tables.entries.search(board=b) if (e["message"] or "").startswith("Let me invite")]
    if lea and tracking:
        lea[0]["track"] = DEMO_TRACK  # the landing page's "See what the sender sees" (#t/demo)
    C.set_setting("demo", "loaded")
    if tracking:
        C.set_setting("demo_version", DEMO_VERSION)
    return counts()


def remove(remember=True):
    for name in DEMO_TABLES:
        try:
            rows = list(getattr(app_tables, name).search(is_demo=True))
        except Exception:  # a table that isn't in the database yet (new schema not accepted)
            continue
        for r in rows:
            r.delete()
    for u in app_tables.users.search(is_demo=True):
        u.delete()
    if remember:
        C.set_setting("demo", "removed")
    return counts()


def counts():
    out = {"users": len(app_tables.users.search(is_demo=True))}
    for name in DEMO_TABLES:
        try:
            out[name] = len(getattr(app_tables, name).search(is_demo=True))
        except Exception:
            out[name] = 0
    return out
