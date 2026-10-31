"""Sample feedback for a fictional note-taking app ("Lumen Notes"). Used twice:
  - DemoData: the public demo link (#f/demo), owned by a demo account (is_demo=True rows)
  - Boards.ensure_starter: every new member gets a "Sample" link with this content, so their inbox,
    board and stories are alive on the first visit (is_sample=True on the board; delete it any time).
All names and emails are fictional (@example.com).
"""
import datetime as dt

from anvil.tables import app_tables

from . import common as C
from . import Insights, Tracking

SITE = "https://lumen-notes.example"

# (hours ago, kind, rating, name, email, page, message, status, priority, starred, story key)
ENTRIES = [
    (3, "bug", 2, "Priya N.", "priya@example.com", "/editor",
     "The editor freezes for a few seconds every time I paste a long table from Excel. On my laptop it even crashed once and I lost the last paragraph.",
     "new", "high", True, "paste"),
    (7, "idea", 5, "", "", "/notes",
     "Would love a dark mode for the editor, I write late at night and the white page is blinding.",
     "new", "medium", False, "dark"),
    (11, "praise", 5, "Marco", "marco@example.com", "/",
     "Honestly the cleanest notes app I've used. Search is instant and the keyboard shortcuts are perfect. Thank you!",
     "reviewing", "", False, None),
    (20, "question", 3, "", "", "/settings/billing",
     "Can I switch from the monthly plan to yearly without losing my discount? The billing page doesn't say.",
     "new", "low", False, None),
    (26, "bug", 1, "Jonas", "jonas@example.com", "/notes/shared",
     "Shared notes disappeared from my teammate's account after I renamed the folder. Data loss is scary, please fix asap.",
     "planned", "urgent", True, "share"),
    (38, "idea", 4, "Aiko", "aiko@example.com", "/export",
     "Export to PDF keeps the formatting but loses the images. A proper PDF export with pictures would save me a lot of time.",
     "reviewing", "medium", False, None),
    (52, "idea", 4, "", "", "/editor",
     "Please add a dark theme, my eyes hurt at night. Also a bigger font option would help.",
     "new", "", False, "dark"),
    (70, "bug", 2, "Sam", "sam@example.com", "/login",
     "On my iPhone the login button is hidden behind the keyboard, I have to rotate the phone to sign in.",
     "planned", "high", False, None),
    (95, "idea", 5, "Lea", "lea@example.com", "/notes/shared",
     "Let me invite my team to a shared notebook and comment on each other's notes. That's the only reason we still use another tool.",
     "planned", "medium", True, "share"),
    (130, "praise", 5, "", "", "/",
     "Switched from a big-name app last month. Love how fast everything feels.",
     "done", "", False, None),
    (170, "bug", 2, "Ravi", "ravi@example.com", "/editor",
     "Pasting from Google Docs makes the page lag badly and the cursor jumps to the top.",
     "new", "medium", False, "paste"),
    (220, "question", 3, "", "", "/integrations",
     "Is there an integration with Slack or Zapier? I'd like new notes to post to a channel.",
     "reviewing", "low", False, None),
    (300, "idea", 3, "Noor", "noor@example.com", "/search",
     "Search is great but I'd love filters by tag and date, and to sort results by last edited.",
     "done", "low", False, None),
    (410, "other", 4, "", "", "/",
     "The onboarding tutorial was a bit confusing at first, but once I got it everything clicked.",
     "done", "", False, None),
]

STORIES = {
    "paste": {
        "title": "Pasting large tables never freezes the editor",
        "persona": "writer who works with spreadsheets",
        "goal": "to paste large tables from Excel or Google Docs without the editor freezing",
        "benefit": "I don't lose work or my place in the note",
        "acceptance": ["Pasting a 500-row table takes under 1 second", "The cursor stays where the paste ended",
                       "If a paste is too big, a message offers to paste it as an attachment",
                       "No content is lost if the tab crashes (autosave every 5 seconds)"],
        "notes": "Two customers hit this in the same week. Likely the table parser running on the main thread.",
        "priority": "high", "status": "ready", "points": 5,
        "comments": ["Reproduced with a 300-row sheet: 4.2s freeze in Chrome.", "Let's move parsing to a worker and add autosave while we're there."],
    },
    "share": {
        "title": "Shared notebooks for teams",
        "persona": "team lead",
        "goal": "to invite my team to a shared notebook where we can comment on notes",
        "benefit": "we can keep all our work in one tool",
        "acceptance": ["I can invite people by email to a notebook", "Renaming or moving a folder never removes access",
                       "Team members can comment on a note", "The owner can remove someone's access"],
        "notes": "Includes the folder-rename bug: shared notes must survive renames.",
        "priority": "medium", "status": "draft", "points": 8,
        "comments": ["Jonas's data-loss report is part of this: fix the rename first."],
    },
}


def fill(board, owner, is_demo=False, tracking=True):
    """Add the sample entries, stories and comments to `board`. Returns the number of entries."""
    now = C.now()
    stories = {}
    for key, s in STORIES.items():
        stories[key] = app_tables.stories.add_row(
            board=board, owner=owner, title=s["title"], persona=s["persona"], goal=s["goal"], benefit=s["benefit"],
            acceptance=s["acceptance"], notes=s["notes"], priority=s["priority"], status=s["status"], points=s["points"],
            source="manual", created=now - dt.timedelta(hours=20), updated=now - dt.timedelta(hours=2), is_demo=is_demo)
        for i, body in enumerate(s["comments"]):
            app_tables.comments.add_row(author=owner, story=stories[key], body=body, is_demo=is_demo,
                                   created=now - dt.timedelta(hours=18 - i * 5))
    for hours, kind, rating, name, email, page, msg, status, prio, star, story in ENTRIES:
        when = now - dt.timedelta(hours=hours)
        ai = Insights.analyze(msg, kind, rating)
        e = app_tables.entries.add_row(
            board=board, kind=kind, message=msg, rating=rating, email=email or None, name=name or None,
            page_url=SITE + page, context={"screen": "1440x900" if hours % 2 else "390x844",
                                            "browser": "Chrome 129" if hours % 3 else "Safari 18", "lang": "en"},
            status=status, priority=prio, tags=list(ai["tags"][:2]), starred=star,
            story=stories.get(story), ai=ai, created=when, updated=when, is_demo=is_demo,
            **({"track": Tracking.new_token(), "reply_waiting": hours == 95} if tracking else {}))
        if tracking:
            _timeline(e, owner, hours, when, now)
        if hours == 26:
            app_tables.comments.add_row(author=owner, entry=e, body="Asked Jonas for the folder name. Happens only with nested folders.",
                                   created=when + dt.timedelta(hours=2), is_demo=is_demo)
    return len(ENTRIES)


# Public replies the team wrote to the sender (their tracking page), by "hours ago" of the entry.
REPLIES = {
    26: ("Sorry about this, Jonas. We found the cause (renaming a nested folder) and a fix is being built now. "
         "Your notes are safe in our backups: we'll restore them for your teammate today.", None),
    95: ("Thanks Lea! Shared notebooks are planned for the next release. We'll post here as soon as there's a beta.",
         "Amazing, happy to beta test with my team of 6!"),
    300: ("Tag and date filters are live! Open Search and look for the new Filters button.", None),
}


def _timeline(e, owner, hours, when, now):
    """A believable history for one sample message: received, triaged, planned, done, plus a few replies."""
    def at(h):
        t = when + dt.timedelta(hours=h)
        return t if t < now else now - dt.timedelta(minutes=5)
    Tracking.log(e, "received", when=when)
    status = e["status"]
    if e["priority"]:
        Tracking.log(e, "priority", e["priority"], author=owner, when=at(min(1, hours * .1)))
    if status in ("reviewing", "planned", "done"):
        Tracking.log(e, "status", "reviewing", author=owner, when=at(min(2, hours * .15)))
    if e["story"] is not None:
        Tracking.log(e, "story", e["story"]["title"], author=owner, when=at(min(3, hours * .2)))
    if status in ("planned", "done"):
        Tracking.log(e, "status", "planned", author=owner, when=at(min(4, hours * .25)))
    reply = REPLIES.get(hours)
    if reply:
        Tracking.log(e, "reply", text=reply[0], author=owner, when=at(hours * .4))
        if reply[1]:
            Tracking.log(e, "sender", text=reply[1], when=at(hours * .55))
    if status == "done":
        Tracking.log(e, "status", "done", author=owner, when=at(hours * .7))
