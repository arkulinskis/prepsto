#!/usr/bin/env python3
"""prepsto: read and work your Prepsto feedback tickets from a terminal, or let Claude do it (MCP server).

One file, Python 3.8+, nothing to install. Download it from Prepsto (Claude & API page), then:

    python prepsto.py login                 paste an API key from the Claude & API page (saved for you only)
    python prepsto.py tickets               open tickets, newest first   (--status --link --kind --tag --q --mine --limit)
    python prepsto.py show <id>             one ticket: the message, details, team comments, the sender's timeline
    python prepsto.py claim <id>            assign it to you (and move it from New to Reviewing)
    python prepsto.py set <id> --status planned --priority high --tag export --assign me
    python prepsto.py comment <id> "text"   a private note for your team ("-" reads the text from stdin)
    python prepsto.py reply <id> "text"     a public reply the sender reads (needs a key that may reply)
    python prepsto.py done <id> [--comment "what changed"] [--reply "text for the sender"]
    python prepsto.py stories               user stories        python prepsto.py story <id> [--format markdown]
    python prepsto.py draft-story <id> <id> ...   draft a user story from tickets
    python prepsto.py links | whoami | logout
    python prepsto.py mcp                   run as an MCP server for Claude Code / Claude Desktop:
                                            claude mcp add prepsto -- python /full/path/to/prepsto.py mcp

Add --json to any command for the raw answer. The key comes from $PREPSTO_KEY, or from the file `login` writes
(~/.prepsto/config.json, readable only by you). $PREPSTO_URL (or login --url) points it at another Prepsto address.
"""
import argparse
import getpass
import json
import os
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request

VERSION = "1.0.0"
DEFAULT_URL = "https://prepsto.com"
CONFIG = os.path.join(os.path.expanduser("~"), ".prepsto", "config.json")
STATUSES = ["new", "reviewing", "planned", "done", "archived"]
PRIORITIES = ["", "low", "medium", "high", "urgent"]


class Fail(Exception):
    pass


# ------------------------------------------------------------------------------------------- config + HTTP
def load_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    try:
        os.chmod(CONFIG, stat.S_IRUSR | stat.S_IWUSR)  # 600: only you can read it (Windows keeps your profile's rights)
    except OSError:
        pass


def settings():
    cfg = load_config()
    key = os.environ.get("PREPSTO_KEY") or cfg.get("key") or ""
    url = (os.environ.get("PREPSTO_URL") or cfg.get("url") or DEFAULT_URL).rstrip("/")
    return url, key


def api(method, path, body=None, query=None, key=None, url=None):
    base, saved = settings()
    base, key = (url or base).rstrip("/"), key or saved
    if not key:
        raise Fail("No API key yet. Make one on Prepsto's Claude & API page, then run: python prepsto.py login")
    q = {k: v for k, v in (query or {}).items() if v not in (None, "", False)}
    full = base + "/_/api" + path + ("?" + urllib.parse.urlencode(q) if q else "")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(full, data=data, method=method, headers={
        "Authorization": "Bearer " + key, "Accept": "application/json", "User-Agent": "prepsto-cli/" + VERSION,
        **({"Content-Type": "application/json"} if data is not None else {})})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error")
        except Exception:
            msg = None
        raise Fail(msg or "Prepsto answered %s %s." % (e.code, e.reason))
    except urllib.error.URLError as e:
        raise Fail("Couldn't reach %s (%s)." % (base, e.reason))


def tid(value):
    """Accept 169207-4096, [169207,4096] or a pasted inbox link."""
    value = (value or "").strip()
    if "#" in value:
        value = urllib.parse.unquote(value.rsplit("/", 1)[-1])
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1].replace(",", "-")
    return urllib.parse.quote(value, safe="-")


# ------------------------------------------------------------------------------------------- printing
def short(text, n):
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[:n - 1] + "…"


def print_ticket_line(t):
    bits = [t["kind"], t["status"]] + ([t["priority"]] if t.get("priority") else []) + (["★"] if t.get("starred") else [])
    who = t.get("from") or "Anonymous"
    extra = (" @" + t["assignee"]["name"]) if t.get("assignee") else ""
    print("%-16s %-28s %s%s" % (t["id"], " ".join(bits), short(t["message"], 70), extra))
    print("%-16s %s · %s · %s" % ("", who, t["link"]["name"], (t.get("created") or "")[:10]))


def print_ticket(d):
    t = d["ticket"]
    print("%s  ·  %s  ·  %s%s" % (t["id"], t["kind"], t["status"], ("  ·  priority " + t["priority"]) if t.get("priority") else ""))
    print("Link: %s   From: %s%s   Sent: %s" % (t["link"]["name"], t.get("from"), " (left an email)" if t.get("has_email") else "",
                                              (t.get("created") or "")[:16].replace("T", " ")))
    if t.get("page_url"):
        print("Page: " + t["page_url"])
    if t.get("rating"):
        print("Rating: %s/5" % t["rating"])
    dev = t.get("device") or {}
    if dev:
        print("Device: " + " · ".join(str(v) for v in dev.values()))
    print("\n" + (t.get("message") or "") + "\n")
    ins = t.get("insights") or {}
    print("Insights (%s): sentiment %s, urgency %s%s" % (ins.get("by"), ins.get("sentiment"), ins.get("urgency"),
                                                        (", theme " + ins["theme"]) if ins.get("theme") else ""))
    if t.get("tags"):
        print("Tags: " + ", ".join("#" + x for x in t["tags"]))
    if t.get("assignee"):
        print("Assigned to: " + t["assignee"]["name"])
    if t.get("story"):
        print("Story: %s (%s)" % (t["story"]["title"], t["story"]["id"]))
    if d.get("comments"):
        print("\nTeam comments (private):")
        for c in d["comments"]:
            print("  - %s: %s" % (c["author"], short(c["body"], 300)))
    s = d.get("sender") or {}
    if s.get("timeline"):
        print("\nWhat the sender sees (%s%s):" % (s.get("stage"), ", waiting for your reply" if s.get("waiting_for_reply") else ""))
        for u in s["timeline"]:
            line = u["kind"] + (": " + u["value"] if u.get("value") else "") + ((" — " + short(u["text"], 200)) if u.get("text") else "")
            print("  - " + line)
    if d.get("similar"):
        print("\nSimilar: " + ", ".join("%s (%d%%)" % (x["id"], round(x["score"] * 100)) for x in d["similar"]))
    print("\nOpen in Prepsto: " + t["url"])


def out(args, data, human):
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        human(data)


# ------------------------------------------------------------------------------------------- commands
def cmd_login(args):
    url = (args.url or settings()[0]).rstrip("/")
    key = args.key or os.environ.get("PREPSTO_KEY") or getpass.getpass("Paste your Prepsto API key (it won't show): ").strip()
    me = api("GET", "/v1/me", key=key, url=url)
    cfg = load_config()
    cfg.update(key=key, url=url)
    save_config(cfg)
    print("Signed in as %s with the key \"%s\" (%s). Saved to %s." % (me["user"]["name"], me["key"]["name"],
                                                                     ", ".join(me["key"]["scopes"]), CONFIG))


def cmd_logout(args):
    cfg = load_config()
    cfg.pop("key", None)
    save_config(cfg)
    print("The key was removed from this computer. (It still works until you revoke it on the Claude & API page.)")


def cmd_whoami(args):
    out(args, api("GET", "/v1/me"), lambda d: print("%s · key \"%s\" (%s) · %d link(s)%s" % (
        d["user"]["name"], d["key"]["name"], ", ".join(d["key"]["scopes"]), len(d["links"]),
        (" · expires " + d["key"]["expires"][:10]) if d["key"].get("expires") else "")))


def cmd_links(args):
    def human(d):
        for b in d["links"]:
            print("%-16s %-30s %3d new / %d total%s" % (b["id"], short(b["name"], 30), b["new"], b["total"], "" if b["open"] else "  (closed)"))
    out(args, api("GET", "/v1/links"), human)


def cmd_tickets(args):
    q = {"status": args.status, "link": args.link, "kind": args.kind, "tag": args.tag, "q": args.q, "sort": args.sort,
         "mine": "1" if args.mine else None, "limit": args.limit, "offset": args.offset}

    def human(d):
        if not d["tickets"]:
            print("No tickets match.")
        for t in d["tickets"]:
            print_ticket_line(t)
        if d["total"] > d["offset"] + len(d["tickets"]):
            print("… %d more (use --offset %d)" % (d["total"] - d["offset"] - len(d["tickets"]), d["offset"] + len(d["tickets"])))
    out(args, api("GET", "/v1/tickets", query=q), human)


def cmd_show(args):
    out(args, api("GET", "/v1/tickets/" + tid(args.id)), print_ticket)


def _changed(args, d, what):
    out(args, d, lambda x: print("%s: %s · %s%s" % (x["ticket"]["id"], what, x["ticket"]["status"],
                                                   (" · " + x["ticket"]["priority"]) if x["ticket"].get("priority") else "")))


def cmd_set(args):
    body = {}
    if args.status:
        body["status"] = args.status
    if args.priority is not None:
        body["priority"] = "" if args.priority == "none" else args.priority
    if args.tag:
        body["add_tag"] = args.tag
    if args.untag:
        body["remove_tag"] = args.untag
    if args.assign:
        body["assignee"] = None if args.assign == "none" else args.assign
    if args.star:
        body["starred"] = True
    if args.unstar:
        body["starred"] = False
    if not body:
        raise Fail("Nothing to change. Use --status, --priority, --tag, --untag, --assign, --star or --unstar.")
    _changed(args, api("POST", "/v1/tickets/" + tid(args.id), body), "updated")


def cmd_claim(args):
    t = api("GET", "/v1/tickets/" + tid(args.id))["ticket"]
    body = {"assignee": "me"}
    if t["status"] == "new":
        body["status"] = "reviewing"
    _changed(args, api("POST", "/v1/tickets/" + tid(args.id), body), "assigned to you")


def _text(value):
    return sys.stdin.read() if value == "-" else value


def cmd_comment(args):
    d = api("POST", "/v1/tickets/%s/comments" % tid(args.id), {"body": _text(args.text)})
    out(args, d, lambda x: print("Team comment added."))


def cmd_reply(args):
    d = api("POST", "/v1/tickets/%s/replies" % tid(args.id), {"body": _text(args.text)})
    out(args, d, lambda x: print("Reply sent: the sender sees it on their tracking page."))


def cmd_done(args):
    if args.comment:
        api("POST", "/v1/tickets/%s/comments" % tid(args.id), {"body": _text(args.comment)})
    d = api("POST", "/v1/tickets/" + tid(args.id), {"status": "done"})
    if args.reply:
        api("POST", "/v1/tickets/%s/replies" % tid(args.id), {"body": _text(args.reply)})
    _changed(args, d, "done" + (" (comment added)" if args.comment else "") + (" (sender told)" if args.reply else ""))


def cmd_stories(args):
    def human(d):
        if not d["stories"]:
            print("No stories.")
        for s in d["stories"]:
            print("%-16s %-12s %s  (%d ticket%s)" % (s["id"], s["status"], short(s["title"], 60), s["feedback_count"],
                                                    "" if s["feedback_count"] == 1 else "s"))
    out(args, api("GET", "/v1/stories", query={"link": args.link, "status": args.status}), human)


def cmd_story(args):
    fmt = args.format or ("json" if args.json else "markdown")
    d = api("GET", "/v1/stories/" + tid(args.id), query={"format": fmt})
    if fmt != "json":
        print(d["text"])
    else:
        print(json.dumps(d, indent=2, ensure_ascii=False))


def cmd_draft(args):
    d = api("POST", "/v1/stories", {"ticket_ids": [tid(i) for i in args.ids]})
    out(args, d, lambda x: print("Story drafted: %s (%s)\n%s" % (x["story"]["title"], x["story"]["id"], x["story"]["url"])))


# ------------------------------------------------------------------------------------------- MCP server (stdio)
def _schema(props, required=()):
    return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}


ID = {"type": "string", "description": "A ticket id like 169207-4096 (from list_tickets)."}
TOOLS = [
    ("whoami", "Who the Prepsto API key belongs to, what it may do and which feedback links it can see.", _schema({}), True, None),
    ("list_links", "The feedback links (one per app or site) this key can see, with how many new and total tickets each has.",
     _schema({}), True, lambda a: api("GET", "/v1/links")),
    ("list_tickets", "List feedback tickets (bug reports, ideas, praise, questions) newest first. Defaults to open ones "
     "(new, reviewing, planned).",
     _schema({"status": {"type": "string", "enum": ["open", "new", "reviewing", "planned", "done", "archived", "all"]},
              "link_id": {"type": "string"}, "kind": {"type": "string", "enum": ["bug", "idea", "praise", "question", "other"]},
              "tag": {"type": "string"}, "query": {"type": "string", "description": "Words to search for"},
              "mine": {"type": "boolean", "description": "Only tickets assigned to the key's owner"},
              "sort": {"type": "string", "enum": ["newest", "oldest", "priority", "rating"]},
              "limit": {"type": "integer", "minimum": 1, "maximum": 100}, "offset": {"type": "integer", "minimum": 0}}), True,
     lambda a: api("GET", "/v1/tickets", query={"status": a.get("status"), "link": a.get("link_id"), "kind": a.get("kind"),
                                                 "tag": a.get("tag"), "q": a.get("query"), "mine": "1" if a.get("mine") else None,
                                                 "sort": a.get("sort"), "limit": a.get("limit"), "offset": a.get("offset")})),
    ("get_ticket", "One ticket in full: the message, page, device, rating, insights, private team comments, what the sender "
     "sees on their tracking page, and similar tickets.", _schema({"ticket_id": ID}, ["ticket_id"]), True,
     lambda a: api("GET", "/v1/tickets/" + tid(a["ticket_id"]))),
    ("update_ticket", "Change a ticket: status (new, reviewing, planned, done, archived), priority (low, medium, high, urgent, or "
     "empty), tags, star, assignee (\"me\" or a teammate's id, or null), or link it to a story. Status and priority changes "
     "show on the sender's tracking page.",
     _schema({"ticket_id": ID, "status": {"type": "string", "enum": STATUSES}, "priority": {"type": "string", "enum": PRIORITIES},
              "add_tag": {"type": "string"}, "remove_tag": {"type": "string"}, "starred": {"type": "boolean"},
              "assignee": {"type": ["string", "null"]}, "story_id": {"type": "string"}}, ["ticket_id"]), False,
     lambda a: api("POST", "/v1/tickets/" + tid(a["ticket_id"]), {k: v for k, v in a.items() if k != "ticket_id"})),
    ("add_team_comment", "Add a PRIVATE note to a ticket for the team (the sender never sees it), e.g. what you changed and where.",
     _schema({"ticket_id": ID, "body": {"type": "string"}}, ["ticket_id", "body"]), False,
     lambda a: api("POST", "/v1/tickets/%s/comments" % tid(a["ticket_id"]), {"body": a["body"]})),
    ("reply_to_sender", "PUBLIC reply: the person who sent the feedback reads it on their tracking page, under the key owner's "
     "name. Show the user the exact text and get their OK before calling this.",
     _schema({"ticket_id": ID, "body": {"type": "string"}}, ["ticket_id", "body"]), False,
     lambda a: api("POST", "/v1/tickets/%s/replies" % tid(a["ticket_id"]), {"body": a["body"]})),
    ("list_stories", "User stories (As a..., I want..., so that...) made from feedback.",
     _schema({"link_id": {"type": "string"}, "status": {"type": "string", "enum": ["draft", "ready", "in_progress", "shipped"]}}),
     True, lambda a: api("GET", "/v1/stories", query={"link": a.get("link_id"), "status": a.get("status")})),
    ("get_story", "One user story with its acceptance criteria, team comments and the tickets behind it. format=markdown, gherkin, "
     "jira, text or csv gives it as text.",
     _schema({"story_id": {"type": "string"}, "format": {"type": "string", "enum": ["json", "markdown", "gherkin", "jira", "text", "csv"]}},
             ["story_id"]), True, lambda a: api("GET", "/v1/stories/" + tid(a["story_id"]), query={"format": a.get("format")})),
    ("draft_story", "Draft a user story from one or more tickets on the same link (they move to Planned).",
     _schema({"ticket_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1}}, ["ticket_ids"]), False,
     lambda a: api("POST", "/v1/stories", {"ticket_ids": [tid(i) for i in a["ticket_ids"]]})),
    ("update_story", "Change a story's title, persona, goal, benefit, acceptance criteria (list), notes, priority, status "
     "(draft, ready, in_progress, shipped) or points. Fields left out stay as they are.",
     _schema({"story_id": {"type": "string"}, "title": {"type": "string"}, "persona": {"type": "string"}, "goal": {"type": "string"},
              "benefit": {"type": "string"}, "acceptance": {"type": "array", "items": {"type": "string"}}, "notes": {"type": "string"},
              "priority": {"type": "string", "enum": PRIORITIES}, "status": {"type": "string", "enum": ["draft", "ready", "in_progress", "shipped"]},
              "points": {"type": ["integer", "null"]}}, ["story_id"]), False,
     lambda a: api("POST", "/v1/stories/" + tid(a["story_id"]), {k: v for k, v in a.items() if k != "story_id"})),
]
INSTRUCTIONS = ("Prepsto holds customer feedback (tickets) for the user's apps. Typical work: list open tickets, read one, fix "
                "the problem in the user's code, add a private team comment saying what changed, and set the status to done. "
                "Replies to senders are public: draft them and ask the user before calling reply_to_sender.")


def _mcp_send(msg):
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _mcp_call(name, args):
    for tname, _, _, _, fn in TOOLS:
        if tname == name:
            data = api("GET", "/v1/me") if fn is None else fn(args or {})
            return {"content": [{"type": "text", "text": json.dumps(data, indent=1, ensure_ascii=False)}], "structuredContent": data}
    raise Fail("Unknown tool: %s" % name)


def cmd_mcp(args):
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            _mcp_send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
            continue
        mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
        if mid is None:
            continue  # a notification (initialized, cancelled): nothing to answer
        try:
            if method == "initialize":
                result = {"protocolVersion": params.get("protocolVersion") or "2025-06-18", "capabilities": {"tools": {}},
                          "serverInfo": {"name": "prepsto", "version": VERSION}, "instructions": INSTRUCTIONS}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": [{"name": n, "description": d, "inputSchema": s,
                                     "annotations": {"readOnlyHint": ro, "destructiveHint": False, "openWorldHint": n == "reply_to_sender"}}
                                    for n, d, s, ro, _ in TOOLS]}
            elif method == "tools/call":
                try:
                    result = _mcp_call(params.get("name"), params.get("arguments"))
                except Fail as e:
                    result = {"content": [{"type": "text", "text": str(e)}], "isError": True}
            else:
                _mcp_send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "Method not found: %s" % method}})
                continue
            _mcp_send({"jsonrpc": "2.0", "id": mid, "result": result})
        except Exception as e:  # never die mid-conversation
            _mcp_send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}})


# ------------------------------------------------------------------------------------------- the command line
def parser():
    p = argparse.ArgumentParser(prog="prepsto", description="Read and work your Prepsto feedback tickets.")
    p.add_argument("--json", action="store_true", help="print the raw JSON answer")
    p.add_argument("--version", action="version", version="prepsto " + VERSION)
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("login", help="save an API key on this computer")
    s.add_argument("--key", help="the key (safer: leave it out and paste it when asked)")
    s.add_argument("--url", help="Prepsto's address (default %s)" % DEFAULT_URL)
    sub.add_parser("logout", help="remove the saved key")
    sub.add_parser("whoami", help="who the key belongs to")
    sub.add_parser("links", help="your feedback links")
    s = sub.add_parser("tickets", help="list tickets")
    s.add_argument("--status", default="open", choices=["open"] + STATUSES + ["all"])
    s.add_argument("--link")
    s.add_argument("--kind", choices=["bug", "idea", "praise", "question", "other"])
    s.add_argument("--tag")
    s.add_argument("--q", help="search words")
    s.add_argument("--mine", action="store_true", help="only tickets assigned to you")
    s.add_argument("--sort", choices=["newest", "oldest", "priority", "rating"])
    s.add_argument("--limit", type=int, default=25)
    s.add_argument("--offset", type=int, default=0)
    s = sub.add_parser("show", help="one ticket in full")
    s.add_argument("id")
    s = sub.add_parser("set", help="change a ticket")
    s.add_argument("id")
    s.add_argument("--status", choices=STATUSES)
    s.add_argument("--priority", choices=["none", "low", "medium", "high", "urgent"])
    s.add_argument("--tag", help="add a tag")
    s.add_argument("--untag", help="remove a tag")
    s.add_argument("--assign", help="me, none, or a teammate's id")
    s.add_argument("--star", action="store_true")
    s.add_argument("--unstar", action="store_true")
    s = sub.add_parser("claim", help="assign a ticket to you")
    s.add_argument("id")
    s = sub.add_parser("comment", help="a private team comment")
    s.add_argument("id")
    s.add_argument("text", help='the comment, or "-" to read it from stdin')
    s = sub.add_parser("reply", help="a public reply to the sender")
    s.add_argument("id")
    s.add_argument("text", help='the reply, or "-" to read it from stdin')
    s = sub.add_parser("done", help="mark a ticket done")
    s.add_argument("id")
    s.add_argument("--comment", help="a private note about what changed")
    s.add_argument("--reply", help="a public reply to the sender")
    s = sub.add_parser("stories", help="list user stories")
    s.add_argument("--link")
    s.add_argument("--status", choices=["draft", "ready", "in_progress", "shipped"])
    s = sub.add_parser("story", help="one user story")
    s.add_argument("id")
    s.add_argument("--format", choices=["json", "markdown", "gherkin", "jira", "text", "csv"])
    s = sub.add_parser("draft-story", help="draft a user story from tickets")
    s.add_argument("ids", nargs="+")
    sub.add_parser("mcp", help="run as an MCP server (stdio) for Claude")
    sub.add_parser("help", help="show this help")
    return p


COMMANDS = {"login": cmd_login, "logout": cmd_logout, "whoami": cmd_whoami, "links": cmd_links, "tickets": cmd_tickets,
            "show": cmd_show, "set": cmd_set, "claim": cmd_claim, "comment": cmd_comment, "reply": cmd_reply, "done": cmd_done,
            "stories": cmd_stories, "story": cmd_story, "draft-story": cmd_draft, "mcp": cmd_mcp}


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    if not args.cmd or args.cmd == "help":
        p.print_help()
        return 0
    try:
        for stream in (sys.stdout, sys.stdin):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")  # Windows: names, stars and Claude's messages stay intact
        COMMANDS[args.cmd](args)
    except Fail as e:
        print("prepsto: " + str(e), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
