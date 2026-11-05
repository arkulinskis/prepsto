"""The Prepsto API for a member's own tools: Claude (through the prepsto CLI or its MCP server) or any script.
Served at https://prepsto.com/_/api/v1/... ; every request needs a key from the Claude & API page:

    Authorization: Bearer psk_...            (or the header X-Prepsto-Key: psk_...)

    GET  /v1/me                        who the key belongs to, what it may do
    GET  /v1/links                     the links the key can see
    GET  /v1/tickets                   ?status=open|new|reviewing|planned|done|archived|all &link= &kind= &tag= &q=
                                       &mine=1 &sort=newest|oldest|priority|rating &limit=25 (max 100) &offset=0
    POST /v1/tickets                   (write) file a new ticket yourself (an idea, a bug you found): {"link": <link id or
                                       its code>, "message", "kind", "page_url", "name" (shown as the sender; default:
                                       your name), "tags", "priority"}
    GET  /v1/tickets/<id>              one ticket: message, details, insights, team comments, the sender's timeline
    POST /v1/tickets/<id>              (write) change it: {"status", "priority", "tags", "add_tag", "remove_tag",
                                       "starred", "assignee": "me" | <user id> | null, "story_id"}
    POST /v1/tickets/<id>/comments     (write) a private team comment {"body"}
    POST /v1/tickets/<id>/replies      (reply) a public reply the sender reads on their tracking page {"body"}
    GET  /v1/stories                   ?link= &status=
    GET  /v1/stories/<id>              ?format=json (default) | markdown | text | gherkin | jira | csv
    POST /v1/stories                   (write) draft a story from tickets {"ticket_ids": [...]} or a blank one {"link_id"}
    POST /v1/stories/<id>              (write) change it {"title", "persona", "goal", "benefit", "acceptance", "notes",
                                       "priority", "status", "points"}
    POST /v1/stories/<id>/comments     (write) a team comment on the story {"body"}

Ids look like "169207-4096" (Anvil's row ids without the brackets). A ticket is one piece of feedback. Answers are JSON: {"ok": true, ...} or {"ok": false, "error": "..."} with a 4xx code.
Senders' email addresses and their private tracking links are never sent. Rules: ApiKeys.py.
"""
import json
import re
import urllib.parse

import anvil.server
from anvil.tables import app_tables

from . import common as C
from . import ApiKeys, Boards, Inbox, Insights, Stories, Tracking
from . import exports

STATUSES = ("open", "new", "reviewing", "planned", "done", "archived", "all")
FIELDS = ("status", "priority", "tags", "add_tag", "remove_tag", "starred", "assignee", "story_id")


class Problem(Exception):
    def __init__(self, status, message):
        Exception.__init__(self, message)
        self.status, self.message = status, message


# ------------------------------------------------------------------------------------------- plumbing
def sid(row_id):
    """Anvil row ids look like "[169207,4096]": tools get "169207-4096" (no brackets or commas to quote in a shell)."""
    if not row_id:
        return row_id
    m = re.match(r"^\[(\d+),(\d+)\]$", str(row_id))
    return "%s-%s" % m.groups() if m else row_id


def rid(value):
    """The other way: "169207-4096" (or the raw "[169207,4096]") -> Anvil's row id."""
    value = str(value or "").strip()
    m = re.match(r"^(\d+)-(\d+)$", value)
    return "[%s,%s]" % m.groups() if m else value


def _ids(d, *keys):
    for k in keys:
        if isinstance(d.get(k), dict) and d[k].get("id"):
            d[k] = dict(d[k], id=sid(d[k]["id"]))
    return d


def _json(status, data):
    return anvil.server.HttpResponse(status, json.dumps(data, ensure_ascii=False),
                                     headers={"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store",
                                              "X-Content-Type-Options": "nosniff"})


def _header(name):
    h = getattr(anvil.server.request, "headers", None) or {}
    for k in h:
        if k.lower() == name:
            return h[k] or ""
    return ""


def _method():
    return (getattr(anvil.server.request, "method", None) or "GET").upper()


def _body():
    r = anvil.server.request
    try:
        b = r.body_json
        b = b() if hasattr(b, "__call__") else b
    except Exception:
        raise Problem(400, "The request body must be JSON.")
    if b is None:
        return {}
    if not isinstance(b, dict):
        raise Problem(400, "The request body must be a JSON object.")
    return b


def _serve(action, fn, query, scope="read"):
    """Authenticate, check the scope, run fn(key, user, query), log it, answer in JSON."""
    if "key" in query or "api_key" in query:
        return _json(400, {"ok": False, "error": "Don't put API keys in the address (it ends up in logs). Use the Authorization header."})
    auth = _header("authorization")
    token = auth[7:] if auth.lower().startswith("bearer ") else _header("x-prepsto-key")
    k, u, err = ApiKeys.authenticate(token)
    if err:
        return _json(err[0], {"ok": False, "error": err[1]})
    method = _method()
    try:
        if not ApiKeys.has_scope(k, scope):
            raise Problem(403, "This key can't do that (it needs the \"%s\" permission). Make a key with more access on the Claude & API page." % scope)
        data = fn(k, u, query)
        status, out = 200, dict(data, ok=True)
    except Problem as p:
        status, out = p.status, {"ok": False, "error": p.message}
    ApiKeys.log(k, u, method, method + " " + action, status)
    return _json(status, out)


def _board_ids(k, u):
    return set(b.get_id() for b in ApiKeys.allowed_boards(k, u))


def _entry(k, u, ticket_id):
    r = Inbox.owned_entry(ticket_id, u)
    if r is None or r["board"].get_id() not in _board_ids(k, u):
        raise Problem(404, "There's no ticket with that id that this key can see.")
    return r


def _story(k, u, story_id):
    s = Stories.owned_story(story_id, u)
    if s is None or s["board"].get_id() not in _board_ids(k, u):
        raise Problem(404, "There's no story with that id that this key can see.")
    return s


def _check(r):
    """A C.fail(...) reply from the app's own functions becomes a 400."""
    if isinstance(r, dict) and r.get("ok") is False:
        raise Problem(400, r.get("error") or "That didn't work.")
    return r


def _int(v, default, low, high):
    try:
        return max(low, min(high, int(v)))
    except Exception:
        return default


def _app_url(*parts):
    try:
        origin = anvil.server.get_app_origin()
    except Exception:
        origin = "https://prepsto.com"
    return origin.rstrip("/") + "/#" + "/".join(urllib.parse.quote(str(x), safe="") for x in parts)


# ------------------------------------------------------------------------------------------- shapes
def ticket(e):
    """An Inbox.entry_dict without the sender's email, for tools."""
    ai = e.get("ai") or {}
    c = e.get("context") or {}
    return _ids({"id": sid(e["id"]), "url": _app_url("inbox", "entry", e["id"]), "link": {"id": sid(e["board_id"]), "name": e["board"]},
            "kind": e["kind"], "status": e["status"], "priority": e["priority"], "stage": e.get("stage"),
            "message": e["message"], "from": e["name"] or "Anonymous", "has_email": bool(e.get("email")),
            "rating": e["rating"], "page_url": e["page_url"], "device": {k: c.get(k) for k in ("browser", "screen", "lang") if c.get(k)},
            "tags": e["tags"], "starred": e["starred"], "assignee": e["assignee"], "story": e["story"],
            "sender_replied": e["reply_waiting"], "created": e["created"], "updated": e["updated"],
            "insights": {"sentiment": ai.get("sentiment"), "urgency": ai.get("urgency"), "theme": ai.get("theme"),
                         "summary": ai.get("summary"), "suggested_tags": ai.get("tags") or [], "by": ai.get("provider") or "rules"}},
                "assignee", "story")


def _comment(c):
    return {"id": sid(c["id"]), "author": c["author"], "body": c["body"], "created": c["created"]}


def _story_out(d, full=False):
    out = {k: d.get(k) for k in ("id", "title", "persona", "goal", "benefit", "acceptance", "notes", "priority", "status",
                                 "points", "source", "created", "updated", "feedback_count", "comment_count", "author")}
    out["id"] = sid(d["id"])
    out["link"] = {"id": sid(d["board_id"]), "name": d["board"]}
    out["url"] = _app_url("story", d["id"])
    out["sentence"] = exports.sentence(d)
    if full:
        out["tickets"] = [ticket(e) for e in d.get("entries") or []]
        out["comments"] = [_comment(c) for c in d.get("comments") or []]
    return out


def _safe_story(d):
    """A story dict for the exports without senders' emails."""
    d = dict(d)
    d["entries"] = [dict(e, email="") for e in d.get("entries") or []]
    return d


# ------------------------------------------------------------------------------------------- endpoints
@anvil.server.http_endpoint("/v1/me", methods=["GET"])
def api_me(**query):
    def run(k, u, q):
        links = ApiKeys.allowed_boards(k, u)
        return {"user": {"id": sid(u.get_id()), "name": C.name_of(u)},
                "key": {"name": k["name"], "prefix": k["prefix"], "scopes": list(k["scopes"] or ["read"]),
                        "expires": C.iso(k["expires"]), "all_links": not (k["boards"] or [])},
                "links": [{"id": sid(b.get_id()), "name": b["name"]} for b in links],
                "limits": {"requests": ApiKeys.RATE, "per_seconds": ApiKeys.WINDOW}}
    return _serve("/v1/me", run, query)


@anvil.server.http_endpoint("/v1/links", methods=["GET"])
def api_links(**query):
    def run(k, u, q):
        out = []
        for b in ApiKeys.allowed_boards(k, u):
            d = Boards.board_dict(b, me=u)
            out.append({"id": sid(d["id"]), "code": d["slug"], "name": d["name"], "role": d["role"], "site_url": d["site_url"], "open": d["is_open"],
                        "total": d["total"], "new": d["new"], "last": d["last"], "kinds": d["kinds"],
                        "tracking": d["public_track"], "team": d["team"]})
        return {"links": out}
    return _serve("/v1/links", run, query)


@anvil.server.http_endpoint("/v1/tickets", methods=["GET", "POST"])
def api_tickets(**query):
    if _method() == "POST":
        return _serve("/v1/tickets", lambda k, u, q: _ticket_create(k, u, _body()), query, scope="write")

    def run(k, u, q):
        status = q.get("status") or "open"
        if status not in STATUSES:
            raise Problem(400, "status must be one of: " + ", ".join(STATUSES))
        allowed = _board_ids(k, u)
        link = rid(q.get("link")) if q.get("link") else ""
        if link and link not in allowed:
            raise Problem(404, "This key can't see that link.")
        f = {"board": link, "kind": q.get("kind") or "", "tag": q.get("tag") or "", "q": q.get("q") or "",
             "mine": str(q.get("mine") or "").lower() in ("1", "true", "yes"), "status": status, "sort": q.get("sort") or "newest",
             "starred": str(q.get("starred") or "").lower() in ("1", "true", "yes")}
        d = Inbox.inbox_view(u, f)
        rows = [e for e in d["entries"] if e["board_id"] in allowed]
        limit, offset = _int(q.get("limit"), 25, 1, 100), _int(q.get("offset"), 0, 0, 100000)
        counts = d["counts"] if len(allowed) == len(Boards.my_boards(u)) or link else None
        return {"tickets": [ticket(e) for e in rows[offset:offset + limit]], "total": len(rows), "offset": offset, "limit": limit,
                "counts": counts}
    return _serve("/v1/tickets", run, query)


CREATE_FIELDS = ("link", "link_id", "message", "kind", "page_url", "name", "tags", "priority")


def _link_for(k, u, value):
    """A link this key can see, by its id ("169207-4096") or its code (the 7 letters in prepsto.com/#f/<code>)."""
    value = str(value or "").strip()
    if not value:
        raise Problem(400, "Send \"link\": the id or code of the feedback link the ticket belongs to (GET /v1/links lists them).")
    boards = ApiKeys.allowed_boards(k, u)
    b = next((b for b in boards if b.get_id() == rid(value)), None) or \
        next((b for b in boards if (b["slug"] or "") == value.lower()), None)
    if b is None:
        raise Problem(404, "This key can't see a link with that id or code.")
    return b


def _ticket_create(k, u, body):
    """A member files a ticket on one of their own links (Claude noting an idea, a bug found while testing...).
    Same row as a panel submission, without an email address; the team sees it in the inbox like any other."""
    unknown = [x for x in body if x not in CREATE_FIELDS]
    if unknown:
        raise Problem(400, "Unknown field(s): %s. You can send: %s." % (", ".join(unknown), ", ".join(CREATE_FIELDS)))
    b = _link_for(k, u, body.get("link") or body.get("link_id"))
    message = C.text(body.get("message"), 4000, multiline=True)
    if len(message) < 3:
        raise Problem(400, "Send a \"message\" of at least a few words.")
    kinds = list(b["kinds"] or Boards.DEFAULT_KINDS)
    kind = body.get("kind") or ("idea" if "idea" in kinds else kinds[0])
    if kind not in kinds:
        raise Problem(400, "kind must be one of this link's kinds: " + ", ".join(kinds))
    priority = body.get("priority") or ""
    if priority not in Inbox.PRIORITIES:
        raise Problem(400, "priority must be one of: " + ", ".join(x for x in Inbox.PRIORITIES if x))
    tags = body.get("tags") or []
    if not isinstance(tags, list):
        raise Problem(400, "tags must be a list of words.")
    ai = Insights.analyze(message, kind, None)
    row: dict = dict(board=b, kind=kind, message=message, rating=None, email=None,
               name=C.text(body.get("name"), 60) or C.name_of(u), page_url=C.text(body.get("page_url"), 300) or None,
               context={"via": "api", "key": C.text(k["name"], 60)}, status="new",
               priority=priority or ("high" if ai["urgency"] == "high" else ""), tags=Inbox.clean_tags(tags), starred=False,
               story=None, ai=ai, created=C.now(), updated=C.now(), is_demo=bool(b["is_demo"]))
    try:
        e = app_tables.entries.add_row(track=Tracking.new_token(), reply_waiting=False, **row)
        Tracking.log(e, "received")
    except Exception as ex:  # tracking columns not accepted in Anvil yet: still save it (as widget_submit does)
        print("tracking unavailable:", ex)
        e = app_tables.entries.add_row(**row)
    return {"ticket": ticket(Inbox.entry_dict(e))}


@anvil.server.http_endpoint("/v1/tickets/:ticket_id", methods=["GET", "POST", "PATCH"])
def api_ticket(ticket_id, **query):
    ticket_id = rid(ticket_id)
    if _method() == "GET":
        return _serve("/v1/tickets/" + ticket_id, lambda k, u, q: _ticket_detail(k, u, ticket_id), query)
    return _serve("/v1/tickets/" + ticket_id, lambda k, u, q: _ticket_update(k, u, ticket_id, _body()), query, scope="write")


def _ticket_detail(k, u, ticket_id):
    _entry(k, u, ticket_id)
    v = _check(Inbox.entry_view(u, ticket_id))
    t = v.get("tracking") or {}
    timeline = [{"kind": x["kind"], "value": x["value"], "text": x["text"], "who": x.get("who") or "", "created": x["created"]}
                for x in t.get("updates") or []]
    return {"ticket": ticket(v["entry"]), "comments": [_comment(c) for c in v["comments"]],
            "sender": {"can_follow": bool(t.get("on")), "stage": t.get("stage"), "last_checked": t.get("seen"),
                       "waiting_for_reply": bool(t.get("waiting")), "timeline": timeline},
            "team": [{"id": sid(p["id"]), "name": p["name"]} for p in v["team"]],
            "stories": [{"id": sid(s["id"]), "title": s["title"], "status": s["status"]} for s in v["stories"]],
            "similar": [{"id": sid(s["id"]), "score": s["score"], "message": s["message"][:200], "status": s["status"]} for s in v["similar"]],
            "you_can": {"update": ApiKeys.has_scope(k, "write"), "reply_to_sender": ApiKeys.has_scope(k, "reply") and bool(t.get("on")),
                        "delete": False}}


def _ticket_update(k, u, ticket_id, body):
    r = _entry(k, u, ticket_id)
    unknown = [x for x in body if x not in FIELDS]
    if unknown:
        raise Problem(400, "Unknown field(s): %s. You can change: %s." % (", ".join(unknown), ", ".join(FIELDS)))
    changes = {x: body[x] for x in ("status", "priority", "add_tag", "starred") if x in body}
    if "story_id" in body:
        changes["story_id"] = rid(body["story_id"]) if body["story_id"] else ""
    if "tags" in body:
        if not isinstance(body["tags"], list):
            raise Problem(400, "tags must be a list of words.")
        changes["tags"] = body["tags"]
    if "remove_tag" in body:
        drop = C.text(body["remove_tag"], 24).lower().strip("#, ")
        changes["tags"] = [t for t in changes.get("tags", list(r["tags"] or [])) if t != drop]
    if "assignee" in body:
        a = body["assignee"]
        changes["assignee_id"] = u.get_id() if a == "me" else (rid(a) if a else "")
    if not changes:
        raise Problem(400, "Send at least one field to change: " + ", ".join(FIELDS) + ".")
    if "add_tag" in changes and "tags" in changes:  # both: apply the list, then the new one
        changes["tags"] = list(changes["tags"]) + [changes.pop("add_tag")]
    err = Inbox._apply(r, changes, u)
    if err:
        raise Problem(400, err)
    return {"ticket": ticket(Inbox.entry_dict(r))}


@anvil.server.http_endpoint("/v1/tickets/:ticket_id/comments", methods=["POST"])
def api_ticket_comment(ticket_id, **query):
    ticket_id = rid(ticket_id)

    def run(k, u, q):
        _entry(k, u, ticket_id)
        body = _body()
        r = _check(Inbox.comment_as(u, "entry", ticket_id, body.get("body"), [rid(m) for m in body.get("mentions") or []], limit=False))
        return {"comment": _comment(r["comment"])}
    return _serve("/v1/tickets/%s/comments" % ticket_id, run, query, scope="write")


@anvil.server.http_endpoint("/v1/tickets/:ticket_id/replies", methods=["POST"])
def api_ticket_reply(ticket_id, **query):
    ticket_id = rid(ticket_id)

    def run(k, u, q):
        r = _entry(k, u, ticket_id)
        body = _body()
        _check(Tracking.reply_as(u, ticket_id, body.get("body"), limit=False))
        return {"ticket": ticket(Inbox.entry_dict(r)), "note": "The sender sees this reply on their tracking page."}
    return _serve("/v1/tickets/%s/replies" % ticket_id, run, query, scope="reply")


@anvil.server.http_endpoint("/v1/stories", methods=["GET", "POST"])
def api_stories(**query):
    if _method() == "POST":
        return _serve("/v1/stories", lambda k, u, q: _story_create(k, u, _body()), query, scope="write")

    def run(k, u, q):
        allowed = _board_ids(k, u)
        link = rid(q.get("link")) if q.get("link") else ""
        if link and link not in allowed:
            raise Problem(404, "This key can't see that link.")
        status = q.get("status") or None
        if status and status not in Stories.STATUSES:
            raise Problem(400, "status must be one of: " + ", ".join(Stories.STATUSES))
        d = Stories.stories_view(u, link or None, status)
        return {"stories": [_story_out(s) for s in d["stories"] if s["board_id"] in allowed]}
    return _serve("/v1/stories", run, query)


def _story_create(k, u, body):
    ids = body.get("ticket_ids") or []
    if not isinstance(ids, list):
        raise Problem(400, "ticket_ids must be a list of ticket ids.")
    ids = [rid(i) for i in ids]
    for i in ids:
        _entry(k, u, i)
    link = rid(body.get("link_id")) if body.get("link_id") else None
    if not ids and (not link or link not in _board_ids(k, u)):
        raise Problem(400, "Send ticket_ids (the story is drafted from them) or the link_id of a link this key can see.")
    r = _check(Stories.create_story_as(u, link, ids))
    return {"story": _story_out(r["story"])}


@anvil.server.http_endpoint("/v1/stories/:story_id", methods=["GET", "POST", "PATCH"])
def api_story(story_id, **query):
    story_id = rid(story_id)
    if _method() != "GET":
        def update(k, u, q):
            _story(k, u, story_id)
            body = _body()
            allowed = ("title", "persona", "goal", "benefit", "acceptance", "notes", "priority", "status", "points")
            unknown = [x for x in body if x not in allowed]
            if unknown:
                raise Problem(400, "Unknown field(s): %s. You can change: %s." % (", ".join(unknown), ", ".join(allowed)))
            _check(Stories.save_story_as(u, story_id, body, partial=True))
            return {"story": _story_out(_check(Stories.story_view(u, story_id))["story"], full=True)}
        return _serve("/v1/stories/" + story_id, update, query, scope="write")

    def run(k, u, q):
        _story(k, u, story_id)
        v = _check(Stories.story_view(u, story_id))
        fmt = q.get("format") or "json"
        if fmt != "json":
            if fmt not in exports.MAKERS or fmt == "json":
                raise Problem(400, "format must be json, markdown, text, gherkin, jira or csv.")
            return {"format": fmt, "text": exports.render(fmt, _safe_story(v["story"]), v["bundle"])}
        return {"story": _story_out(v["story"], full=True), "ai_bundle": v["bundle"], "provider": Insights.PROVIDER}
    return _serve("/v1/stories/" + story_id, run, query)


@anvil.server.http_endpoint("/v1/stories/:story_id/comments", methods=["POST"])
def api_story_comment(story_id, **query):
    story_id = rid(story_id)

    def run(k, u, q):
        _story(k, u, story_id)
        body = _body()
        r = _check(Inbox.comment_as(u, "story", story_id, body.get("body"), [rid(m) for m in body.get("mentions") or []], limit=False))
        return {"comment": _comment(r["comment"])}
    return _serve("/v1/stories/%s/comments" % story_id, run, query, scope="write")
