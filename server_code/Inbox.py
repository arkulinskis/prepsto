"""The team's side of feedback: overview numbers, the inbox (list + board), one entry, triage, assignees, comments
(with @mentions). Every call only touches entries on boards the caller owns or is an active teammate on."""
import datetime as dt

import anvil.server
from anvil.tables import app_tables
import anvil.tables as tables

from . import common as C
from . import Boards, Insights, Team

STATUSES = ["new", "reviewing", "planned", "done", "archived"]
PRIORITIES = ["", "low", "medium", "high", "urgent"]
PRIO_RANK = {"urgent": 4, "high": 3, "medium": 2, "low": 1, "": 0, None: 0}


def entry_dict(r):
    b, s = r["board"], r["story"]
    return {"id": r.get_id(), "board_id": b.get_id(), "board": b["name"], "kind": r["kind"],
            "kind_label": Boards.KINDS.get(r["kind"], "Other"), "message": r["message"], "rating": r["rating"],
            "email": r["email"] or "", "name": r["name"] or "", "page_url": r["page_url"] or "",
            "context": r["context"] or {}, "status": r["status"] or "new", "priority": r["priority"] or "",
            "tags": list(r["tags"] or []), "starred": bool(r["starred"]),
            "story": {"id": s.get_id(), "title": s["title"]} if s is not None else None,
            "ai": r["ai"] or {}, "created": C.iso(r["created"]), "updated": C.iso(r["updated"]),
            "assignee": {"id": r["assignee"].get_id(), "name": C.name_of(r["assignee"])} if r["assignee"] is not None else None}


def comment_dict(c, me):
    mentions = []
    for uid in (c["mentions"] or []):
        u = C.row_by_id(app_tables.users, uid)
        if u is not None:
            mentions.append({"id": uid, "name": C.name_of(u)})
    board = c["entry"]["board"] if c["entry"] is not None else (c["story"]["board"] if c["story"] is not None else None)
    return {"id": c.get_id(), "author": C.name_of(c["author"]), "body": c["body"], "created": C.iso(c["created"]),
            "mine": c["author"] == me, "can_delete": c["author"] == me or (board is not None and board["owner"] == me),
            "mentions": mentions, "me_mentioned": me is not None and me.get_id() in (c["mentions"] or [])}


def owned_entry(entry_id, me):
    r = C.row_by_id(app_tables.entries, entry_id)
    if r is None or r["board"] is None or Boards.role_in(r["board"], me) is None:
        return None
    return r


def my_entries(me, board=None):
    boards = [board] if board is not None else Boards.my_boards(me)
    rows = []
    for b in boards:
        rows.extend(app_tables.entries.search(board=b))
    rows.sort(key=lambda r: r["created"], reverse=True)
    return rows


def clean_tags(tags):
    out = []
    for t in (tags if isinstance(tags, list) else []):
        t = C.text(t, 24).lower().strip("#, ")
        if t and t not in out:
            out.append(t)
    return out[:8]


# ------------------------------------------------------------------------------------------- overview (home)
@anvil.server.callable(require_user=True)
def get_overview():
    me = C.require_user()
    Boards.ensure_starter(me)
    boards = Boards.my_boards(me)
    rows = my_entries(me)
    now = C.now()
    today = now.date()
    daily = []
    for i in range(13, -1, -1):
        d = today - dt.timedelta(days=i)
        daily.append({"date": d.isoformat(), "count": len([r for r in rows if r["created"].date() == d])})
    week = [r for r in rows if (now - r["created"]).days < 7]
    prev = [r for r in rows if 7 <= (now - r["created"]).days < 14]
    rated = [r["rating"] for r in rows if r["rating"] and (now - r["created"]).days < 30]
    kinds, senti, tags = {}, {"positive": 0, "neutral": 0, "negative": 0}, {}
    for r in rows:
        if r["status"] == "archived":
            continue
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        s = (r["ai"] or {}).get("sentiment")
        if s in senti:
            senti[s] += 1
        for t in set(list(r["tags"] or []) + list((r["ai"] or {}).get("tags") or [])):
            tags[t] = tags.get(t, 0) + 1
    attention = [r for r in rows if r["status"] == "new" and
                 ((r["ai"] or {}).get("urgency") == "high" or r["priority"] in ("high", "urgent"))]
    stories = []
    for b in boards:
        stories.extend(app_tables.stories.search(board=b))
    return {"name": C.name_of(me),
            "boards": [Boards.board_dict(b, me=me) for b in boards],
            "invites": Team.my_invites(me),
            "assigned": [entry_dict(r) for r in rows if r["assignee"] == me and r["status"] in ("new", "reviewing", "planned")][:5],
            "total": len(rows), "new": len([r for r in rows if r["status"] == "new"]),
            "open": len([r for r in rows if r["status"] in ("new", "reviewing", "planned")]),
            "week": len(week), "prev_week": len(prev),
            "avg_rating": round(sum(rated) / float(len(rated)), 1) if rated else None, "rated": len(rated),
            "daily": daily, "kinds": kinds, "sentiment": senti,
            "tags": sorted(tags.items(), key=lambda x: (-x[1], x[0]))[:10],
            "stories": len(stories), "stories_ready": len([s for s in stories if s["status"] == "ready"]),
            "attention": [entry_dict(r) for r in attention[:5]],
            "recent": [entry_dict(r) for r in rows[:6]],
            "kind_labels": Boards.KINDS, "provider": Insights.PROVIDER}


# ------------------------------------------------------------------------------------------- the inbox
@anvil.server.callable(require_user=True)
def get_inbox(filters=None):
    me = C.require_user()
    Boards.ensure_starter(me)
    f = filters if isinstance(filters, dict) else {}
    board = Boards.team_board(f.get("board"), me) if f.get("board") else None
    rows = my_entries(me, board)
    kind, q, tag, status = f.get("kind") or "", C.text(f.get("q"), 80).lower(), C.text(f.get("tag"), 24).lower(), f.get("status") or "open"
    if kind:
        rows = [r for r in rows if r["kind"] == kind]
    if tag:
        rows = [r for r in rows if tag in (r["tags"] or []) or tag in ((r["ai"] or {}).get("tags") or [])]
    if q:
        rows = [r for r in rows if q in (r["message"] or "").lower() or q in (r["name"] or "").lower()
                or q in (r["email"] or "").lower() or q in (r["page_url"] or "").lower()]
    if f.get("starred"):
        rows = [r for r in rows if r["starred"]]
    if f.get("mine"):
        rows = [r for r in rows if r["assignee"] == me]
    counts = {s: 0 for s in STATUSES}
    for r in rows:
        counts[r["status"] if r["status"] in counts else "new"] += 1
    counts["open"] = counts["new"] + counts["reviewing"] + counts["planned"]
    counts["all"] = len(rows)
    if status == "open":
        rows = [r for r in rows if r["status"] in ("new", "reviewing", "planned")]
    elif status in STATUSES:
        rows = [r for r in rows if r["status"] == status]
    sort = f.get("sort") or "newest"
    if sort == "oldest":
        rows.reverse()
    elif sort == "priority":
        rows.sort(key=lambda r: (-PRIO_RANK.get(r["priority"], 0), -(r["created"].timestamp())))
    elif sort == "rating":
        rows.sort(key=lambda r: (r["rating"] or 9, -(r["created"].timestamp())))
    tags = {}
    for r in my_entries(me, board):
        for t in set(list(r["tags"] or []) + list((r["ai"] or {}).get("tags") or [])):
            tags[t] = tags.get(t, 0) + 1
    return {"entries": [entry_dict(r) for r in rows[:400]], "total": len(rows), "counts": counts,
            "boards": [{"id": b.get_id(), "name": b["name"], "role": Boards.role_in(b, me)} for b in Boards.my_boards(me)],
            "tags": [t for t, _ in sorted(tags.items(), key=lambda x: (-x[1], x[0]))[:16]],
            "kind_labels": Boards.KINDS, "statuses": STATUSES}


@anvil.server.callable(require_user=True)
def get_entry(entry_id):
    me = C.require_user()
    r = owned_entry(entry_id, me)
    if r is None:
        return C.fail("That feedback doesn't exist (any more).")
    same_board = list(app_tables.entries.search(board=r["board"]))
    comments = app_tables.comments.search(tables.order_by("created"), entry=r)
    stories = app_tables.stories.search(tables.order_by("updated", ascending=False), board=r["board"])
    return C.ok(entry=entry_dict(r), comments=[comment_dict(c, me) for c in comments],
                similar=[dict(entry_dict(s), score=score) for score, s in Insights.similar(r, same_board)],
                stories=[{"id": s.get_id(), "title": s["title"], "status": s["status"]} for s in stories],
                team=Team.team_list(r["board"]), role=Boards.role_in(r["board"], me))


def _apply(r, changes, me):
    """Apply allowed changes to one entry. Returns an error message or None."""
    upd = {}
    if "status" in changes:
        if changes["status"] not in STATUSES:
            return "Unknown status."
        upd["status"] = changes["status"]
    if "priority" in changes:
        if (changes["priority"] or "") not in PRIORITIES:
            return "Unknown priority."
        upd["priority"] = changes["priority"] or ""
    if "tags" in changes:
        upd["tags"] = clean_tags(changes["tags"])
    if "add_tag" in changes:
        upd["tags"] = clean_tags(list(r["tags"] or []) + [changes["add_tag"]])
    if "starred" in changes:
        upd["starred"] = bool(changes["starred"])
    if "story_id" in changes:
        if not changes["story_id"]:
            upd["story"] = None
        else:
            s = C.row_by_id(app_tables.stories, changes["story_id"])
            if s is None or s["board"] != r["board"]:
                return "That story isn't on the same link."
            upd["story"] = s
    if "assignee_id" in changes:
        if not changes["assignee_id"]:
            upd["assignee"] = None
        else:
            u = C.row_by_id(app_tables.users, changes["assignee_id"])
            if u is None or u not in Team.team_users(r["board"]):
                return "You can only assign feedback to someone on this link's team."
            upd["assignee"] = u
            if u != r["assignee"]:
                Team.notify(u, me, "assign", r["board"], entry=r, text=(r["message"] or "")[:120])
    if upd:
        upd["updated"] = C.now()
        r.update(**upd)
    return None


@anvil.server.callable(require_user=True)
def update_entry(entry_id, changes):
    me = C.require_user()
    r = owned_entry(entry_id, me)
    if r is None:
        return C.fail("That feedback doesn't exist (any more).")
    err = _apply(r, changes if isinstance(changes, dict) else {}, me)
    if err:
        return C.fail(err)
    return C.ok(entry=entry_dict(r))


@anvil.server.callable(require_user=True)
def bulk_update(entry_ids, changes):
    me = C.require_user()
    if not isinstance(entry_ids, list) or not entry_ids:
        return C.fail("Select some feedback first.")
    rows = [owned_entry(i, me) for i in entry_ids[:400]]
    if any(r is None for r in rows):
        return C.fail("Some of that feedback doesn't exist (any more). Reload and try again.")
    changes = changes if isinstance(changes, dict) else {}
    if changes.get("delete"):
        if any(r["board"]["owner"] != me for r in rows):
            return C.fail("Only the link's owner can delete feedback. Archive it instead.")
        for r in rows:
            _delete_entry(r)
        return C.ok(count=len(rows))
    for r in rows:
        err = _apply(r, changes, me)
        if err:
            return C.fail(err)
    return C.ok(count=len(rows))


def _delete_entry(r):
    for c in app_tables.comments.search(entry=r):
        c.delete()
    for n in app_tables.notifications.search(entry=r):
        n.delete()
    r.delete()


@anvil.server.callable(require_user=True)
def delete_entry(entry_id):
    me = C.require_user()
    r = owned_entry(entry_id, me)
    if r is None:
        return C.fail("That feedback doesn't exist (any more).")
    if r["board"]["owner"] != me:
        return C.fail("Only the link's owner can delete feedback. Archive it instead.")
    _delete_entry(r)
    return C.ok()


@anvil.server.callable(require_user=True)
def reanalyze_board(board_id):
    """Run Insights again on every entry of a link (after the rules change, or once AI is plugged in)."""
    me = C.require_user()
    b = Boards.team_board(board_id, me)
    if b is None:
        return C.fail("That link doesn't exist, or you're not on its team.")
    rows = app_tables.entries.search(board=b)
    for r in rows:
        r["ai"] = Insights.analyze(r["message"], r["kind"], r["rating"])
    return C.ok(count=len(rows), provider=Insights.PROVIDER)


# ------------------------------------------------------------------------------------------- comments
@anvil.server.callable(require_user=True)
def add_comment(target, target_id, body, mentions=None):
    me = C.require_user()
    body = C.text(body, 2000, multiline=True)
    if len(body) < 1:
        return C.fail("Write something first.")
    if C.rate_limited("comment", 120, 3600):
        return C.fail("That's a lot of comments in one hour. Please try again later.")
    if target == "entry":
        r = owned_entry(target_id, me)
        if r is None:
            return C.fail("That feedback doesn't exist (any more).")
        board, entry, story = r["board"], r, None
    elif target == "story":
        s = C.row_by_id(app_tables.stories, target_id)
        if s is None or Boards.role_in(s["board"], me) is None:
            return C.fail("That story doesn't exist (any more).")
        board, entry, story = s["board"], None, s
        s["updated"] = C.now()
    else:
        return C.fail("Unknown comment target.")
    team = Team.team_users(board)
    tagged = []
    for uid in (mentions if isinstance(mentions, list) else [])[:20]:
        u = C.row_by_id(app_tables.users, uid)
        if u is not None and u in team and u not in tagged and ("@" + C.name_of(u)) in body:
            tagged.append(u)
    c = app_tables.comments.add_row(author=me, entry=entry, story=story, body=body, created=C.now(), is_demo=False,
                                    mentions=[u.get_id() for u in tagged])
    for u in tagged:
        Team.notify(u, me, "mention", board, entry=entry, story=story, text=body[:140])
    return C.ok(comment=comment_dict(c, me))


@anvil.server.callable(require_user=True)
def delete_comment(comment_id):
    me = C.require_user()
    c = C.row_by_id(app_tables.comments, comment_id)
    if c is None:
        return C.ok()
    board = c["entry"]["board"] if c["entry"] is not None else (c["story"]["board"] if c["story"] is not None else None)
    if c["author"] != me and not (board is not None and board["owner"] == me):
        return C.fail("You can only delete your own comments.")
    c.delete()
    return C.ok()
