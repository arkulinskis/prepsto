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
from . import Samples

DEMO_SLUG = "demo"
DEMO_USERS = [
    ("Prepsto Team", "team.demo@example.com"),
    ("Maya Chen", "maya.demo@example.com"),     # teammates on the demo link
    ("Theo Martin", "theo.demo@example.com"),
]

# Tables that hold demo rows (each has an is_demo column). Children before parents.
DEMO_TABLES = ["notifications", "comments", "entries", "stories", "members", "boards"]


def state():
    return C.get_setting("demo", "never")  # "never" | "loaded" | "removed"


def ensure_loaded():
    """Called by the public panel and the landing page: loads the demo once, unless an admin removed it."""
    if state() == "never":
        load()


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
    Samples.fill(b, users[0], is_demo=True)
    for u in users[1:]:
        app_tables.members.add_row(board=b, user=u, email=u["email"], role="member", status="active", token=None,
                                   invited_by=users[0], created=C.now() - dt.timedelta(days=18),
                                   joined=C.now() - dt.timedelta(days=17), is_demo=True)
    urgent = app_tables.entries.get(board=b, priority="urgent")
    if urgent is not None:
        urgent["assignee"] = users[1]
        app_tables.comments.add_row(author=users[2], entry=urgent, body="@Maya Chen can you check the rename code path?",
                                    mentions=[users[1].get_id()], created=C.now() - dt.timedelta(hours=20), is_demo=True)
    C.set_setting("demo", "loaded")
    return counts()


def remove(remember=True):
    for name in DEMO_TABLES:
        for r in getattr(app_tables, name).search(is_demo=True):
            r.delete()
    for u in app_tables.users.search(is_demo=True):
        u.delete()
    if remember:
        C.set_setting("demo", "removed")
    return counts()


def counts():
    out = {"users": len(app_tables.users.search(is_demo=True))}
    for name in DEMO_TABLES:
        out[name] = len(getattr(app_tables, name).search(is_demo=True))
    return out
