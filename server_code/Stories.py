"""User stories made from feedback: "As a <persona>, I want <goal>, so that <benefit>", acceptance criteria,
notes, supporting comments, and the client feedback they came from (entries.story links back here).
Exports are drawn in the browser (web/pages/story.html) from get_story; the AI-ready JSON comes from
Insights.ai_bundle so the shape lives in one place."""
import anvil.server
from anvil.tables import app_tables
import anvil.tables as tables

from . import common as C
from . import Boards, Inbox, Insights, Roadmap, Team, Tracking

STATUSES = ["draft", "ready", "in_progress", "shipped"]
PRIORITIES = ["", "low", "medium", "high", "urgent"]
ANNOUNCE_MAX = 500  # linked feedback one "Update everyone who asked" reaches
ANNOUNCES_PER_HOUR = 10


def owned_story(story_id, me):
    s = C.row_by_id(app_tables.stories, story_id)
    if s is None or Boards.role_in(s["board"], me) is None:
        return None
    return s


def story_dict(s, me, full=False):
    linked = list(app_tables.entries.search(tables.order_by("created", ascending=False), story=s))
    d = {"id": s.get_id(), "board_id": s["board"].get_id(), "board": s["board"]["name"], "title": s["title"],
         "persona": s["persona"] or "", "goal": s["goal"] or "", "benefit": s["benefit"] or "",
         "acceptance": list(s["acceptance"] or []), "notes": s["notes"] or "", "priority": s["priority"] or "",
         "status": s["status"] or "draft", "points": s["points"], "source": s["source"] or "manual",
         "created": C.iso(s["created"]), "updated": C.iso(s["updated"]), "feedback_count": len(linked),
         "kinds": sorted(set(e["kind"] for e in linked)),
         "comment_count": len(app_tables.comments.search(story=s)), "author": C.name_of(s["owner"]),
         "public": C.col(s, "public") is True, "public_note": C.col(s, "public_note") or "",
         "shipped_at": C.iso(C.col(s, "shipped_at"))}
    if full:
        entries = []
        for e in linked:
            ed = Inbox.entry_dict(e)
            ed["comments"] = [Inbox.comment_dict(c, me) for c in app_tables.comments.search(tables.order_by("created"), entry=e)]
            entries.append(ed)
        d["entries"] = entries
        d["comments"] = [Inbox.comment_dict(c, me) for c in app_tables.comments.search(tables.order_by("created"), story=s)]
    return d


def _clean(data):
    data = data if isinstance(data, dict) else {}
    raw_acc = data.get("acceptance")
    acc = [C.text(a, 300) for a in (raw_acc if isinstance(raw_acc, list) else [])]
    pts = data.get("points")
    pts = pts if isinstance(pts, (int, float)) and not isinstance(pts, bool) and 0 <= pts <= 100 else None
    return {"title": C.text(data.get("title"), 140), "persona": C.text(data.get("persona"), 120),
            "goal": C.text(data.get("goal"), 400), "benefit": C.text(data.get("benefit"), 400),
            "acceptance": [a for a in acc if a][:20], "notes": C.text(data.get("notes"), 4000, multiline=True),
            "priority": data.get("priority") if data.get("priority") in PRIORITIES else "",
            "status": data.get("status") if data.get("status") in STATUSES else "draft", "points": pts}


@anvil.server.callable(require_user=True)
def list_stories(board_id=None, status=None):
    me = C.require_user()
    Boards.ensure_starter(me)
    return stories_view(me, board_id, status)


def stories_view(me, board_id=None, status=None):
    rows = []
    for b in Boards.my_boards(me):
        rows.extend(app_tables.stories.search(board=b))
    rows.sort(key=lambda s: s["updated"], reverse=True)
    if board_id:
        rows = [s for s in rows if s["board"].get_id() == board_id]
    counts = {st: len([s for s in rows if (s["status"] or "draft") == st]) for st in STATUSES}
    if status in STATUSES:
        rows = [s for s in rows if (s["status"] or "draft") == status]
    return {"stories": [story_dict(s, me) for s in rows], "counts": counts,
            "boards": [{"id": b.get_id(), "name": b["name"], "role": Boards.role_in(b, me)} for b in Boards.my_boards(me)]}


@anvil.server.callable(require_user=True)
def get_story(story_id):
    return story_view(C.require_user(), story_id)


def story_view(me, story_id):
    s = owned_story(story_id, me)
    if s is None:
        return C.fail("That story doesn't exist (any more).")
    d = story_dict(s, me, full=True)
    bundle = Insights.ai_bundle(
        {k: d[k] for k in ("title", "persona", "goal", "benefit", "acceptance", "notes", "priority", "status", "points")},
        [{k: e[k] for k in ("kind", "message", "rating", "page_url", "created")} for e in d["entries"]],
        [{"author": c["author"], "body": c["body"]} for c in d["comments"]])
    pool = [Inbox.entry_dict(e) for e in app_tables.entries.search(tables.order_by("created", ascending=False), board=s["board"])
            if e["story"] is None and e["status"] != "archived"][:60]
    b = s["board"]
    return C.ok(story=d, bundle=bundle, pool=pool, statuses=STATUSES, provider=Insights.PROVIDER, team=Team.team_list(b),
                roadmap={"on": Roadmap.roadmap_on(b), "slug": b["slug"], "board_id": b.get_id()},
                tracking=Tracking.tracking_on(b))


@anvil.server.callable(require_user=True)
def create_story(board_id, entry_ids=None):
    """A new story. With entry_ids, it's drafted from that feedback (Insights.draft_story) and linked to it."""
    return create_story_as(C.require_user(), board_id, entry_ids)


def create_story_as(me, board_id, entry_ids=None):
    entries = [Inbox.owned_entry(i, me) for i in (entry_ids or [])[:50]] if isinstance(entry_ids, list) else []
    if any(e is None for e in entries):
        return C.fail("Some of that feedback doesn't exist (any more). Reload and try again.")
    if entries:
        board = entries[0]["board"]
        if any(e["board"] != board for e in entries):
            return C.fail("Pick feedback from one link at a time: a story belongs to one link.")
    else:
        board = Boards.team_board(board_id, me)
        if board is None:
            return C.fail("Choose one of your links for this story.")
    draft = Insights.draft_story([{"kind": e["kind"], "message": e["message"], "rating": e["rating"], "ai": e["ai"]}
                                  for e in entries], board["name"])
    s = app_tables.stories.add_row(board=board, owner=me, title=draft["title"] or "New story", persona=draft["persona"],
                                   goal=draft["goal"], benefit=draft["benefit"], acceptance=draft["acceptance"],
                                   notes=draft["notes"], priority="", status="draft", points=None,
                                   source=draft["source"] if entries else "manual",
                                   created=C.now(), updated=C.now(), is_demo=False)
    for e in entries:
        was = e["status"]
        e.update(story=s, status="planned" if e["status"] in ("new", "reviewing") else e["status"], updated=C.now())
        Tracking.log(e, "story", s["title"], author=me)
        if e["status"] != was:
            Tracking.log(e, "status", e["status"], author=me)
    return C.ok(story=story_dict(s, me))


@anvil.server.callable(require_user=True)
def save_story(story_id, data):
    return save_story_as(C.require_user(), story_id, data)


def save_story_as(me, story_id, data, partial=False):
    """partial=True (the API): fields that aren't sent keep their current values."""
    s = owned_story(story_id, me)
    if s is None:
        return C.fail("That story doesn't exist (any more).")
    if partial:
        cur = {k: s[k] for k in ("title", "persona", "goal", "benefit", "notes", "priority", "status", "points")}
        cur["acceptance"] = list(s["acceptance"] or [])
        cur["public"], cur["public_note"] = C.col(s, "public") is True, C.col(s, "public_note") or ""
        cur.update({k: v for k, v in (data if isinstance(data, dict) else {}).items() if k in cur})
        data = cur
    d = _clean(data)
    if len(d["title"]) < 2:
        return C.fail("Give the story a title (at least 2 characters).")
    d["updated"] = C.now()
    was = s["status"] or "draft"
    s.update(**d)
    _save_public(s, data, d["status"] == "shipped" and was != "shipped")
    if d["status"] != was and d["status"] != "draft":  # tell the people who asked for it: work started, shipped...
        for e in app_tables.entries.search(story=s):
            Tracking.log(e, "story_status", d["status"], author=me)
    return C.ok(story=story_dict(s, me))


def _save_public(s, data, just_shipped):
    """The roadmap columns, each in its own guarded write: story saving works before the Schema Mismatch is accepted."""
    data = data if isinstance(data, dict) else {}
    if "public" in data:
        try:
            s["public"] = bool(data.get("public"))
        except Exception as ex:
            print("stories.public not in the database yet:", ex)
    if "public_note" in data:
        try:
            s["public_note"] = C.text(data.get("public_note"), Roadmap.NOTE_LIMIT)
        except Exception as ex:
            print("stories.public_note not in the database yet:", ex)
    if just_shipped:  # the changelog's date
        try:
            s["shipped_at"] = C.now()
        except Exception as ex:
            print("stories.shipped_at not in the database yet:", ex)


@anvil.server.callable(require_user=True)
def announce_story(story_id, text):
    """"Update everyone who asked": one message on the tracking page of every piece of feedback linked to the story
    (votes included). Prepsto sends no email: the reply lists the addresses people left, for the team's own mail app."""
    return announce_as(C.require_user(), story_id, text)


def announce_as(me, story_id, text, limit=True):
    s = owned_story(story_id, me)
    if s is None:
        return C.fail("That story doesn't exist (any more).")
    text = C.text(text, 2000, multiline=True)
    if len(text) < 2:
        return C.fail("Write the update first.")
    rows = list(app_tables.entries.search(tables.order_by("created", ascending=True), story=s))[:ANNOUNCE_MAX]
    if not rows:
        return C.fail("Nobody has asked for this story yet: link some feedback to it first.")
    if limit and C.rate_limited("announce", ANNOUNCES_PER_HOUR, 3600):
        return C.fail("That's a lot of updates in one hour. Please try again later.")
    tracking = Tracking.tracking_on(s["board"])
    posted = 0
    if tracking:
        for e in rows:
            if Tracking.reply_row(me, e, text) is not None:
                posted += 1
    emails = []
    for e in rows:
        mail = (e["email"] or "").strip().lower()
        if mail and mail not in emails:
            emails.append(mail)
    if posted:  # the team sees it was sent (and doesn't send it twice)
        app_tables.comments.add_row(author=me, story=s, body="Update posted to %d tracking page%s: %s" % (
            posted, "" if posted == 1 else "s", text[:400]), mentions=[], created=C.now(), is_demo=bool(s["is_demo"]))
        s["updated"] = C.now()
    return C.ok(posted=posted, total=len(rows), tracking_off=not tracking, emails=emails)


@anvil.server.callable(require_user=True)
def redraft_story(story_id):
    """A fresh draft from the linked feedback (not saved: the page fills the form, the person saves)."""
    me = C.require_user()
    s = owned_story(story_id, me)
    if s is None:
        return C.fail("That story doesn't exist (any more).")
    rows = app_tables.entries.search(story=s)
    if not len(rows):
        return C.fail("Link some feedback to this story first.")
    return C.ok(draft=Insights.draft_story([{"kind": e["kind"], "message": e["message"], "rating": e["rating"],
                                             "ai": e["ai"]} for e in rows], s["board"]["name"]))


@anvil.server.callable(require_user=True)
def link_entries(story_id, entry_ids):
    me = C.require_user()
    s = owned_story(story_id, me)
    if s is None:
        return C.fail("That story doesn't exist (any more).")
    rows = [Inbox.owned_entry(i, me) for i in (entry_ids if isinstance(entry_ids, list) else [])[:100]]
    if not rows or any(r is None or r["board"] != s["board"] for r in rows):
        return C.fail("Pick feedback from this story's link.")
    for r in rows:
        if r["story"] != s:
            Tracking.log(r, "story", s["title"], author=me)
        r.update(story=s, updated=C.now())
    s["updated"] = C.now()
    return C.ok(count=len(rows))


@anvil.server.callable(require_user=True)
def unlink_entry(story_id, entry_id):
    me = C.require_user()
    s = owned_story(story_id, me)
    r = Inbox.owned_entry(entry_id, me)
    if s is None or r is None:
        return C.fail("That doesn't exist (any more).")
    if r["story"] == s:
        r.update(story=None, updated=C.now())
    return C.ok()


@anvil.server.callable(require_user=True)
def delete_story(story_id):
    me = C.require_user()
    s = owned_story(story_id, me)
    if s is None:
        return C.fail("That story doesn't exist (any more).")
    if s["owner"] != me and s["board"]["owner"] != me:
        return C.fail("Only the story's author or the link's owner can delete it.")
    for r in app_tables.entries.search(story=s):
        r["story"] = None
    for c in app_tables.comments.search(story=s):
        c.delete()
    for n in app_tables.notifications.search(story=s):
        n.delete()
    s.delete()
    return C.ok()
