"""User stories made from feedback: "As a <persona>, I want <goal>, so that <benefit>", acceptance criteria,
notes, supporting comments, and the client feedback they came from (entries.story links back here).
Exports are drawn in the browser (web/pages/story.html) from get_story; the AI-ready JSON comes from
Insights.ai_bundle so the shape lives in one place."""
import anvil.server
from anvil.tables import app_tables
import anvil.tables as tables

from . import common as C
from . import Boards, Inbox, Insights, Team, Tracking

STATUSES = ["draft", "ready", "in_progress", "shipped"]
PRIORITIES = ["", "low", "medium", "high", "urgent"]


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
         "comment_count": len(app_tables.comments.search(story=s)), "author": C.name_of(s["owner"])}
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
    acc = [C.text(a, 300) for a in (data.get("acceptance") if isinstance(data.get("acceptance"), list) else [])]
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
    me = C.require_user()
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
    return C.ok(story=d, bundle=bundle, pool=pool, statuses=STATUSES, provider=Insights.PROVIDER, team=Team.team_list(s["board"]))


@anvil.server.callable(require_user=True)
def create_story(board_id, entry_ids=None):
    """A new story. With entry_ids, it's drafted from that feedback (Insights.draft_story) and linked to it."""
    me = C.require_user()
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
    me = C.require_user()
    s = owned_story(story_id, me)
    if s is None:
        return C.fail("That story doesn't exist (any more).")
    d = _clean(data)
    if len(d["title"]) < 2:
        return C.fail("Give the story a title (at least 2 characters).")
    d["updated"] = C.now()
    was = s["status"] or "draft"
    s.update(**d)
    if d["status"] != was and d["status"] != "draft":  # tell the people who asked for it: work started, shipped...
        for e in app_tables.entries.search(story=s):
            Tracking.log(e, "story_status", d["status"], author=me)
    return C.ok(story=story_dict(s, me))


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
