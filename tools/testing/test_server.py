"""Server tests against the strict mock of Anvil (tools/testing/mock).

    python -I tools/testing/test_server.py          -> prints ALL OK, or the first failure

call(name, ...) runs a server function the way the browser does: by name, with require_user enforced,
and the reply must be JSON (a datetime or a row in a reply fails here, like it would break the page).
Add tests for every new server function: the happy path, bad input, and someone who isn't allowed.
The API (server_code/ApiRoutes.py) is tested at the end through its http endpoints (api(...)).
"""
import datetime as dt
import importlib
import json
import os
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
_tmp = pathlib.Path(tempfile.mkdtemp())
shutil.copytree(PROJECT / "server_code", _tmp / "app")
shutil.copyfile(PROJECT / "client_code" / "exports.py", _tmp / "app" / "exports.py")  # shared with the browser
(_tmp / "app" / "__init__.py").write_text("")
os.environ["ANVIL_APP_YAML"] = str(PROJECT / "anvil.yaml")  # the mock's tables follow the app's own schema
sys.path[:0] = [str(HERE / "mock"), str(_tmp)]
import anvil.server  # noqa: E402
import anvil.users  # noqa: E402
from anvil.tables import app_tables as T  # noqa: E402

M = {p.stem: importlib.import_module("app." + p.stem) for p in sorted((PROJECT / "server_code").glob("*.py"))}
now = dt.datetime.now(dt.timezone.utc)


def call(name, *args):
    r = anvil.server.call(name, *args)
    json.dumps(r)  # strict: must be JSON-able
    return r


def as_user(row):
    anvil.users.CURRENT[0] = row
    anvil.server.session.use(row.get_id() if row is not None else None)


def denied(name, *args):
    try:
        call(name, *args)
    except anvil.server.PermissionDenied:
        return True
    return False


def ok(r, msg=""):
    assert isinstance(r, dict) and r.get("ok"), (msg, r)
    return r


def bad(r, msg=""):
    assert isinstance(r, dict) and r.get("ok") is False and r.get("error"), (msg, r)
    return r


def person(email, name=None, **kw):
    return T.users.add_row(email=email, enabled=True, signed_up=now, display_name=name, **kw)


# ---------------------------------------------------------------------------------- accounts
admin = person("arkulinskis@gmail.com", "The Admin")
ana = person("ana@example.com", "Ana")
bob = person("bob@example.com")

as_user(None)
assert call("get_me") is None
assert denied("update_profile", "X")
as_user(admin)
assert call("get_me")["is_admin"] is True, "ADMIN_EMAILS become admins on first sign-in"
as_user(ana)
me = call("get_me")
assert me["name"] == "Ana" and me["is_admin"] is False
assert ana["last_seen"] is not None
as_user(bob)
assert call("get_me")["name"] == "Bob", "a name comes from the email when none is set"
bad(call("update_profile", " x "))
assert ok(call("update_profile", "  Bob   Stone "))["me"]["name"] == "Bob Stone"

# ---------------------------------------------------------------------------------- feedback
as_user(None)
bad(call("submit_feedback", "bug", "hi"))
ok(call("submit_feedback", "bug", "The button is broken", "guest@example.com", {"page": "#home", "evil": "x" * 9999}))
fb = T.feedback.search()[0]
assert fb["name"] == "Guest" and fb["email"] == "guest@example.com" and "evil" not in fb["context"] and fb["status"] == "new"
for i in range(4):
    ok(call("submit_feedback", "idea", "Idea number %d" % i))
bad(call("submit_feedback", "idea", "One too many this hour"), "rate limit")
as_user(ana)
ok(call("submit_feedback", "nonsense-kind", "Signed-in feedback"))
assert T.feedback.get(message="Signed-in feedback")["kind"] == "other"
assert denied("list_feedback")
as_user(admin)
lst = call("list_feedback")
assert lst["counts"]["new"] == 6 and len(lst["items"]) == 6
fid = lst["items"][0]["id"]
ok(call("set_feedback_status", fid, "done", "Fixed it"))
assert call("list_feedback", "done")["items"][0]["note"] == "Fixed it"
bad(call("set_feedback_status", fid, "weird"))
bad(call("set_feedback_status", "nope", "done"))
ok(call("delete_feedback", fid))
assert len(call("list_feedback")["items"]) == 5

# ---------------------------------------------------------------------------------- admin
as_user(ana)
for fn, args in [("admin_overview", ()), ("list_users", ()), ("set_admin", (bob.get_id(), True)), ("demo_load", ()), ("demo_remove", ())]:
    assert denied(fn, *args), fn
as_user(admin)
ov = call("admin_overview")
assert ov["users"] == 3 and ov["admins"] == 1 and ov["feedback_new"] == 5
assert len(call("list_users")["users"]) == 3 and len(call("list_users", "bob")["users"]) == 1
ok(call("set_admin", bob.get_id(), True))
assert bob["is_admin"] is True
bad(call("set_admin", admin.get_id(), False), "can't remove your own admin")
ok(call("set_enabled", bob.get_id(), False))
assert bob["enabled"] is False
bad(call("set_enabled", admin.get_id(), False))
ok(call("set_enabled", bob.get_id(), True))
ok(call("set_admin", bob.get_id(), False))
assert bob["is_admin"] is False

# ---------------------------------------------------------------------------------- demo data + the public panel
as_user(None)
cfg = ok(call("widget_config", "demo"))
assert M["DemoData"].state() == "loaded", "demo loads on first panel visit"
assert cfg["board"]["name"] and "owner" not in cfg["board"] and "@" not in json.dumps(cfg)
bad(call("widget_config", "nope123"))
bad(call("widget_config", None))
demo_board = T.boards.get(slug="demo")
n_demo = len(T.entries.search(board=demo_board))
assert n_demo == len(M["Samples"].ENTRIES)
bad(call("widget_submit", "demo", {"message": "x"}), "too short")
bad(call("widget_submit", "demo", {"message": "Bad email here", "email": "nope"}))
bad(call("widget_submit", "nope", {"message": "Hello there"}))
r = ok(call("widget_submit", "demo", {"kind": "bug", "message": "The app crashes and I lost my data!", "rating": 1,
                                      "email": "visitor@example.com", "page": "https://x.example/a", "context": {"screen": "1x1", "evil": "z"}}))
assert r["thanks"]
e = T.entries.search(board=demo_board, email="visitor@example.com")[0]
assert e["is_demo"] and e["status"] == "new" and e["ai"]["sentiment"] == "negative" and e["ai"]["urgency"] == "high"
assert e["priority"] == "high" and "evil" not in e["context"] and "data loss" in e["ai"]["tags"]
ok(call("widget_submit", "demo", {"kind": "weird", "message": "Kind falls back", "rating": 99}))
e2 = T.entries.get(message="Kind falls back")
assert e2["kind"] == "other" and e2["rating"] is None
ok(call("widget_submit", "demo", {"message": "I am a bot", "website": "spam.example"}))
assert T.entries.get(message="I am a bot") is None, "honeypot drops bots silently"
for i in range(10):
    call("widget_submit", "demo", {"message": "Message number %d" % i})
bad(call("widget_submit", "demo", {"message": "One too many"}), "rate limit")

# ---------------------------------------------------------------------------------- links (boards)
for fn, args in [("list_boards", ()), ("save_board", (None, {})), ("delete_board", ("x",)), ("get_overview", ()),
                 ("get_inbox", ()), ("get_entry", ("x",)), ("update_entry", ("x", {})), ("list_stories", ()),
                 ("create_story", ("x", [])), ("add_comment", ("entry", "x", "hi")), ("new_board_code", ("x",))]:
    assert denied(fn, *args), fn
as_user(ana)
lb = call("list_boards")
assert len(lb["boards"]) == 1 and lb["boards"][0]["is_sample"] and lb["boards"][0]["total"] == len(M["Samples"].ENTRIES), "starter sample"
assert ana["starter_done"] is True
call("list_boards")
assert len(call("list_boards")["boards"]) == 1, "the starter is made once"
sample = lb["boards"][0]
bad(call("save_board", None, {"name": "x"}))
bad(call("save_board", None, {"name": "My app", "kinds": []}))
nb = ok(call("save_board", None, {"name": "My app", "kinds": ["idea", "bug", "nonsense"], "color": "red", "site_url": "myapp.example",
                                   "position": "left", "ask_email": False}))["board"]
assert nb["kinds"] == ["idea", "bug"] and nb["color"] == "#2b59ff" and nb["site_url"] == "https://myapp.example"
assert nb["position"] == "left" and nb["ask_email"] is False and len(nb["slug"]) == 7
nb2 = ok(call("save_board", nb["id"], {"name": "My app 2", "kinds": ["idea"], "color": "#ff0000", "is_open": False}))["board"]
assert nb2["name"] == "My app 2" and nb2["color"] == "#ff0000" and not nb2["is_open"]
as_user(None)
bad(call("widget_submit", nb["slug"], {"message": "Closed panel"}), "closed links refuse feedback")
as_user(ana)
ok(call("save_board", nb["id"], {"name": "My app 2", "kinds": ["idea", "bug"], "is_open": True}))
old = nb["slug"]
nb3 = ok(call("new_board_code", nb["id"]))["board"]
assert nb3["slug"] != old and T.boards.get(slug=old) is None
as_user(bob)
bad(call("save_board", nb["id"], {"name": "Hijack", "kinds": ["idea"]}), "can't edit someone else's link")
bad(call("delete_board", nb["id"]))
bad(call("new_board_code", nb["id"]))
assert all(b["id"] != nb["id"] for b in call("list_boards")["boards"])

# ---------------------------------------------------------------------------------- inbox + overview
as_user(None)
anvil.server.session.use("visitor2")
ok(call("widget_submit", nb3["slug"], {"kind": "idea", "message": "Please add dark mode, I love the app", "rating": 5}))
ok(call("widget_submit", nb3["slug"], {"kind": "bug", "message": "Login button hidden on my phone"}))
as_user(ana)
ov = call("get_overview")
assert ov["total"] == len(M["Samples"].ENTRIES) + 2 and len(ov["daily"]) == 14 and len(ov["boards"]) == 2
assert sum(ov["sentiment"].values()) > 0 and ov["stories"] == 2 and ov["kinds"]
assert all(x["board_id"] in (sample["id"], nb["id"]) for x in ov["recent"])
ib = call("get_inbox", {})
assert ib["counts"]["all"] == ov["total"] and ib["total"] == ib["counts"]["open"]
assert all(x["status"] in ("new", "reviewing", "planned") for x in ib["entries"])
assert call("get_inbox", {"board": nb["id"], "status": "all"})["total"] == 2
assert call("get_inbox", {"board": nb["id"], "status": "all", "kind": "bug"})["total"] == 1
assert call("get_inbox", {"q": "DARK MODE", "status": "all"})["total"] >= 2
assert call("get_inbox", {"status": "done"})["total"] == len([x for x in M["Samples"].ENTRIES if x[7] == "done"])
assert call("get_inbox", {"status": "all", "sort": "priority"})["entries"][0]["priority"] == "urgent"
mine = call("get_inbox", {"board": nb["id"], "status": "all"})["entries"]
eid = [x for x in mine if x["kind"] == "bug"][0]["id"]
ge = ok(call("get_entry", eid))
assert ge["entry"]["ai"]["tags"] and ge["comments"] == [] and isinstance(ge["similar"], list)
up = ok(call("update_entry", eid, {"status": "reviewing", "priority": "high", "tags": ["Mobile", "mobile", " login "], "starred": True}))["entry"]
assert up["status"] == "reviewing" and up["tags"] == ["mobile", "login"] and up["starred"]
bad(call("update_entry", eid, {"status": "weird"}))
bad(call("update_entry", eid, {"priority": "mega"}))
bad(call("update_entry", "nope", {"status": "done"}))
c = ok(call("add_comment", "entry", eid, "Checked on iPhone 15: confirmed."))["comment"]
bad(call("add_comment", "entry", eid, "   "))
bad(call("add_comment", "thing", eid, "x"))
assert len(ok(call("get_entry", eid))["comments"]) == 1
as_user(bob)
bad(call("get_entry", eid), "can't read someone else's feedback")
bad(call("update_entry", eid, {"status": "done"}))
bad(call("add_comment", "entry", eid, "Sneaky"))
bad(call("delete_comment", c["id"]))
bad(call("bulk_update", [eid], {"status": "done"}))
bad(call("delete_entry", eid))
assert call("get_inbox", {})["counts"]["all"] == len(M["Samples"].ENTRIES), "bob sees only his own starter"
as_user(ana)
ids = [x["id"] for x in mine]
ok(call("bulk_update", ids, {"add_tag": "q4"}))
assert all("q4" in T.entries.get_by_id(i)["tags"] for i in ids)
bad(call("bulk_update", [], {"status": "done"}))
bad(call("bulk_update", ids + ["nope"], {"status": "done"}))
ok(call("reanalyze_board", nb["id"]))
bad(call("reanalyze_board", "nope"))

# ---------------------------------------------------------------------------------- stories
ls = call("list_stories")
assert len(ls["stories"]) == 2 and ls["counts"]["ready"] == 1
st = ok(call("create_story", None, ids))["story"]
assert st["feedback_count"] == 2 and st["board_id"] == nb["id"] and st["source"] == "rules" and st["title"]
assert T.entries.get_by_id(ids[0])["status"] in ("planned", "reviewing")
bad(call("create_story", None, [ids[0], [x["id"] for x in call("get_inbox", {"board": sample["id"]})["entries"]][0]]), "one link per story")
bad(call("create_story", "nope", []))
blank = ok(call("create_story", nb["id"], []))["story"]
assert blank["feedback_count"] == 0 and blank["source"] == "manual"
bad(call("redraft_story", blank["id"]), "no feedback to draft from")
g = ok(call("get_story", st["id"]))
assert len(g["story"]["entries"]) == 2 and g["bundle"]["schema"] == "prepsto.story/v1" and len(g["bundle"]["client_feedback"]) == 2
assert g["story"]["entries"][0]["comments"] is not None
assert all(p["id"] not in ids for p in g["pool"])
sv = ok(call("save_story", st["id"], {"title": "Dark mode", "persona": "night owl", "goal": "a dark theme", "benefit": "my eyes rest",
                                      "acceptance": ["Toggle in settings", "", "Remembers my choice"], "priority": "high",
                                      "status": "ready", "points": 3, "notes": "From 2 customers"}))["story"]
assert sv["acceptance"] == ["Toggle in settings", "Remembers my choice"] and sv["points"] == 3 and sv["status"] == "ready"
bad(call("save_story", st["id"], {"title": ""}))
ok(call("save_story", st["id"], {"title": "Weird", "status": "zzz", "points": "lots"}))
assert T.stories.get_by_id(st["id"])["status"] == "draft" and T.stories.get_by_id(st["id"])["points"] is None
assert ok(call("redraft_story", st["id"]))["draft"]["acceptance"]
ok(call("add_comment", "story", st["id"], "Design is ready in Figma."))
assert len(ok(call("get_story", st["id"]))["story"]["comments"]) == 1
ok(call("unlink_entry", st["id"], ids[0]))
assert T.entries.get_by_id(ids[0])["story"] is None
ok(call("link_entries", st["id"], [ids[0]]))
bad(call("link_entries", st["id"], [x["id"] for x in call("get_inbox", {"board": sample["id"]})["entries"]][:1]), "other link's feedback")
ok(call("update_entry", ids[0], {"story_id": ""}))
bad(call("update_entry", ids[0], {"story_id": ls["stories"][0]["id"]}), "a story from another link")
ok(call("update_entry", ids[0], {"story_id": blank["id"]}))
as_user(bob)
for fn, args in [("get_story", (st["id"],)), ("save_story", (st["id"], {"title": "Mine now"})), ("redraft_story", (st["id"],)),
                 ("link_entries", (st["id"], ids)), ("unlink_entry", (st["id"], ids[1])), ("delete_story", (st["id"],)),
                 ("add_comment", ("story", st["id"], "hi")), ("create_story", (nb["id"], []))]:
    bad(call(fn, *args), fn)
as_user(ana)
ok(call("delete_story", st["id"]))
assert T.entries.get_by_id(ids[1])["story"] is None and not T.comments.search(story=None, entry=None)
ok(call("delete_comment", c["id"]))
ok(call("delete_entry", ids[1]))
bad(call("get_entry", ids[1]))

# ---------------------------------------------------------------------------------- admin: links + demo data
as_user(ana)
assert denied("admin_boards") and denied("admin_set_board_open", nb["id"], False)
as_user(admin)
ab = call("admin_boards")
assert ab["total"] >= 4 and all("owner_email" in b for b in ab["boards"])
ok(call("admin_set_board_open", nb["id"], False))
assert T.boards.get_by_id(nb["id"])["is_open"] is False
bad(call("admin_set_board_open", "nope", True))
ov = call("admin_overview")
assert ov["boards"] >= 3 and ov["entries"] >= 2 and "items" not in ov
ok(call("demo_remove"))
assert M["DemoData"].state() == "removed" and T.boards.get(slug="demo") is None and not T.entries.search(is_demo=True)
assert not T.users.search(is_demo=True) and T.boards.get_by_id(nb["id"]) is not None, "removing demo data keeps real data"
as_user(None)
bad(call("widget_config", "demo"))
assert M["DemoData"].state() == "removed", "removed demo data doesn't come back by itself"
as_user(admin)
ok(call("demo_load"))
ok(call("demo_load"))
assert len(T.boards.search(slug="demo")) == 1, "reloading replaces the demo instead of doubling it"
as_user(ana)
ok(call("delete_board", sample["id"]))
assert T.boards.get_by_id(sample["id"]) is None and len(call("list_boards")["boards"]) == 1, "the sample can be deleted and stays gone"

# ---------------------------------------------------------------------------------- Insights (rules engine)
I = M["Insights"]
a = I.analyze("I love it, thank you, fantastic work", "praise", 5)
assert a["sentiment"] == "positive" and a["provider"] == "rules"
a = I.analyze("Slow loading on my iPhone, very annoying", "bug", 2)
assert a["sentiment"] == "negative" and "performance" in a["tags"] and "mobile" in a["tags"]
d = I.draft_story([{"kind": "bug", "message": "Export to PDF loses images", "rating": 2, "ai": I.analyze("Export to PDF loses images", "bug", 2)}], "X")
assert d["title"].startswith("Fix:") and d["acceptance"] and d["persona"]
assert I.draft_story([], "X")["title"] == "New story"
# wish lead-ins are stripped from drafted ideas
for msg, want in [("I'd love a focus mode for long sessions", "a focus mode for long sessions"),
                  ("I’d love to see dark mode", "dark mode"),
                  ("Please add CSV export", "CSV export"),
                  ("It would be great to have a weekly digest", "a weekly digest"),
                  ("Hi! Can you add tags to stories?", "tags to stories?"),
                  ("I wish I could export to Jira", "to be able to export to Jira"),
                  ("Would love it if you added keyboard shortcuts", "keyboard shortcuts"),
                  ("Dark mode please", "Dark mode please")]:
    assert I._wish(msg) == want, (msg, I._wish(msg))
d = I.draft_story([{"kind": "idea", "message": "I'd love a focus mode", "rating": 0, "ai": {"summary": "I'd love a focus mode"}}], "X")
assert d["goal"] == "a focus mode" and d["title"] == "A focus mode", d

# ---------------------------------------------------------------------------------- team workspaces
for fn, args in [("list_team", ("x",)), ("invite_member", ("x", "a@b.co")), ("remove_member", ("x", "y")),
                 ("accept_invite", ("x" * 24,)), ("decline_invite", ("x" * 24,)), ("get_notifications", ()),
                 ("mark_notifications_read", ())]:
    as_user(None)
    assert denied(fn, *args), fn
owner = person("owen@example.com", "Owen Park")
mate = person("mia@example.com", "Mia Ray")
outsider = person("zed@example.com", "Zed")
as_user(owner)
tb = ok(call("save_board", None, {"name": "Team app", "kinds": ["bug", "idea"]}))["board"]
assert tb["role"] == "owner" and tb["team"] == 1
as_user(None)
anvil.server.session.use("visitor-team")
ok(call("widget_submit", tb["slug"], {"kind": "bug", "message": "Checkout is broken on Safari"}))
as_user(owner)
team_entry = call("get_inbox", {"board": tb["id"]})["entries"][0]["id"]
# invites
bad(call("invite_member", tb["id"], "not-an-email"))
bad(call("invite_member", tb["id"], "owen@example.com"), "can't invite yourself")
inv = ok(call("invite_member", tb["id"], " MIA@example.com "))["member"]
assert inv["status"] == "invited" and inv["email"] == "mia@example.com" and len(inv["token"]) == 24
bad(call("invite_member", tb["id"], "mia@example.com"), "no double invites")
inv2 = ok(call("invite_member", tb["id"], "newbie@example.com"))["member"]
as_user(mate)
bad(call("invite_member", tb["id"], "x@example.com"), "only the owner invites")
assert call("get_overview")["invites"][0]["board"] == "Team app", "the invitee sees the invite on the overview"
nt = call("get_notifications")
assert nt["unread"] == 1 and nt["items"][0]["kind"] == "invite" and nt["items"][0]["token"] == inv["token"]
bad(call("get_entry", team_entry), "not a member yet")
gi = ok(call("get_invite", inv["token"]))
assert gi["board"] == "Team app" and gi["inviter"] == "Owen Park" and "@" not in json.dumps(gi)
as_user(None)
ok(call("get_invite", inv["token"]))
bad(call("get_invite", "short"))
as_user(outsider)
bad(call("decline_invite", inv["token"]), "can't decline someone else's invite")
as_user(mate)
acc = ok(call("accept_invite", inv["token"]))
assert acc["board_id"] == tb["id"]
bad(call("accept_invite", inv["token"]), "a used invite can't be reused")
assert any(b["id"] == tb["id"] and b["role"] == "member" for b in call("list_boards")["boards"])
assert any(b["id"] == tb["id"] for b in call("get_inbox", {})["boards"])
as_user(owner)
assert any(n["kind"] == "joined" for n in call("get_notifications")["items"]), "the owner hears that Mia joined"
lt = ok(call("list_team", tb["id"]))
assert lt["is_owner"] and len(lt["people"]) == 3 and all("email" in p for p in lt["people"])
as_user(mate)
lt = ok(call("list_team", tb["id"]))
assert not lt["is_owner"] and len(lt["people"]) == 2, "members don't see pending invites"
assert all(p.get("email") in (None, "mia@example.com") for p in lt["people"]), "members don't see the owner's email"
as_user(outsider)
bad(call("list_team", tb["id"]))
bad(call("accept_invite", "nope" * 6))
ok(call("accept_invite", inv2["token"]))  # whoever holds an invite link can use it
assert any(b["id"] == tb["id"] for b in call("list_boards")["boards"])
# members work on the feedback, owner-only actions stay owner-only
as_user(mate)
ge = ok(call("get_entry", team_entry))
assert {p["name"] for p in ge["team"]} >= {"Owen Park", "Mia Ray"} and ge["role"] == "member"
ok(call("update_entry", team_entry, {"status": "reviewing", "assignee_id": owner.get_id()}))
assert T.entries.get_by_id(team_entry)["assignee"] == owner
bad(call("update_entry", team_entry, {"assignee_id": bob.get_id()}), "only teammates can be assigned")
bad(call("save_board", tb["id"], {"name": "Mine now", "kinds": ["idea"]}), "members can't change settings")
bad(call("new_board_code", tb["id"]))
bad(call("delete_board", tb["id"]))
bad(call("invite_member", tb["id"], "y@example.com"))
bad(call("delete_entry", team_entry), "members archive, the owner deletes")
bad(call("bulk_update", [team_entry], {"delete": True}))
ok(call("bulk_update", [team_entry], {"status": "planned"}))
ok(call("reanalyze_board", tb["id"]))
# mentions
c1 = ok(call("add_comment", "entry", team_entry, "@Owen Park this one is yours, @Bob too", [owner.get_id(), bob.get_id(), "junk"]))["comment"]
assert [m["name"] for m in c1["mentions"]] == ["Owen Park"], "only teammates named in the text are mentioned"
ok(call("add_comment", "entry", team_entry, "no names here", [owner.get_id()]))
assert len(T.comments.search(entry=T.entries.get_by_id(team_entry))[-1]["mentions"]) == 0, "a mention must be in the text"
st2 = ok(call("create_story", None, [team_entry]))["story"]
ok(call("add_comment", "story", st2["id"], "@Owen Park can you estimate?", [owner.get_id()]))
gs = ok(call("get_story", st2["id"]))
assert gs["team"] and gs["story"]["comments"][0]["mentions"][0]["name"] == "Owen Park"
as_user(owner)
nt = call("get_notifications")
kinds = [n["kind"] for n in nt["items"]]
assert kinds.count("mention") == 2 and "assign" in kinds and nt["unread"] >= 4
assert any(n["entry_id"] == team_entry for n in nt["items"] if n["kind"] == "mention")
assert any(n["story_id"] == st2["id"] for n in nt["items"] if n["kind"] == "mention")
assert call("get_inbox", {"mine": True, "status": "all"})["total"] == 1, "Assigned to me"
assert call("get_overview")["assigned"][0]["id"] == team_entry
ok(call("mark_notifications_read"))
assert call("get_notifications")["unread"] == 0
ok(call("delete_comment", c1["id"]), "the owner can remove any comment on their link")
as_user(outsider)
bad(call("delete_story", st2["id"]), "only the author or the owner deletes a story")
# leaving and removing
as_user(mate)
mem_id = [p for p in call("list_team", tb["id"])["people"] if p["me"]][0]["id"]
as_user(outsider)
bad(call("remove_member", tb["id"], mem_id), "members can't remove each other")
as_user(mate)
assert ok(call("remove_member", tb["id"], mem_id))["left"] is True
bad(call("get_entry", team_entry), "after leaving, no access")
assert not any(n["board"] == "Team app" for n in call("get_notifications")["items"] if n["kind"] != "invite")
as_user(owner)
out_id = [p for p in call("list_team", tb["id"])["people"] if p["name"] == "Zed"][0]["id"]
ok(call("update_entry", team_entry, {"assignee_id": outsider.get_id()}))
ok(call("remove_member", tb["id"], out_id))
assert T.entries.get_by_id(team_entry)["assignee"] is None, "removing someone unassigns their feedback"
inv3 = ok(call("invite_member", tb["id"], "late@example.com"))["member"]
ok(call("remove_member", tb["id"], inv3["id"]))
bad(call("get_invite", inv3["token"]), "a cancelled invite stops working")
ok(call("delete_board", tb["id"]))
assert not T.members.search() or all(m["board"] is not None for m in T.members.search())
assert not [n for n in T.notifications.search() if n["board"] is None and n["kind"] != "invite"]
# the demo link has a team
dm = T.boards.get(slug="demo")
assert len(T.members.search(board=dm, status="active")) == 2

# ---------------------------------------------------------------------------------- following feedback (Tracking)
as_user(owner)
trb = ok(call("save_board", None, {"name": "Tracked app", "kinds": ["idea", "bug"]}))["board"]
assert trb["public_track"] is True and trb["kinds"] == ["idea", "bug"]
as_user(None)
anvil.server.session.use("visitor-track")
sub = ok(call("widget_submit", trb["slug"], {"kind": "idea", "message": "Please add a calendar view", "email": "fan@example.com"}))
tok = sub["track"]
assert tok and len(tok) == 22
tg = ok(call("track_get", tok))
assert tg["stage"] == "received" and tg["steps"][0]["current"] and tg["entry"]["message"] == "Please add a calendar view"
assert "@" not in json.dumps(tg), "the tracking page never shows emails"
assert [u["kind"] for u in tg["updates"]] == ["received"]
bad(call("track_get", "nope-not-a-token"))
bad(call("track_get", None))
bad(call("track_get", ""))
tr_entry = T.entries.get(track=tok)
assert tr_entry["track_seen"] is not None, "opening the page is noted for the team"
# the team triages: the sender's page follows
as_user(owner)
ok(call("update_entry", tr_entry.get_id(), {"status": "reviewing", "priority": "high"}))
ok(call("update_entry", tr_entry.get_id(), {"status": "reviewing"}))  # no change: no new line
st = ok(call("create_story", None, [tr_entry.get_id()]))["story"]
ge = ok(call("get_entry", tr_entry.get_id()))
assert ge["tracking"]["on"] and ge["tracking"]["token"] == tok and ge["tracking"]["stage"] == "planned"
kinds = [u["kind"] for u in ge["tracking"]["updates"]]
assert kinds == ["received", "status", "priority", "story", "status"], kinds
pu = ok(call("post_update", tr_entry.get_id(), "Great idea! It's on the plan for March."))
assert pu["tracking"]["updates"][-1]["kind"] == "reply"
reply_id = pu["tracking"]["updates"][-1]["id"]
bad(call("post_update", tr_entry.get_id(), " "), "empty reply")
full = ok(call("get_story", st["id"]))["story"]
ok(call("save_story", st["id"], dict(full, status="in_progress")))
as_user(None)
anvil.server.session.use("visitor-track")
tg = ok(call("track_get", tok))
assert tg["stage"] == "in_progress" and tg["story"]["title"] and tg["entry"]["priority"] == "high"
assert tg["updates"][-2]["kind"] == "reply" and tg["updates"][-2]["who"] == "Owen Park" and tg["updates"][-1]["value"] == "in_progress"
# the sender answers
__import__("time").sleep(0.03)  # Windows' clock ticks ~15 ms: keep the team's lines strictly older than the sender's
bad(call("track_reply", tok, "x"), "too short")
tr = ok(call("track_reply", tok, "Thanks! Weekly view would be enough for me."))
assert tr["updates"][-1]["kind"] == "sender" and T.entries.get(track=tok)["reply_waiting"] is True
for i in range(9):
    call("track_reply", tok, "More detail %d" % i)
bad(call("track_reply", tok, "One more"), "reply rate limit")
bad(call("track_reply", "nope-not-a-token", "Hello there"))
tl = ok(call("track_list", [tok, "nope", None, 5]))
assert len(tl["items"]) == 1 and tl["items"][0]["stage"] == "in_progress" and tl["items"][0]["last_kind"] == "sender"
assert ok(call("track_list", "not a list"))["items"] == []
as_user(owner)
assert [n for n in call("get_notifications")["items"] if n["kind"] == "reply"], "the owner hears about the reply"
assert [x for x in call("get_inbox", {"board": trb["id"]})["entries"] if x["reply_waiting"]], "the inbox shows it"
ok(call("post_update", tr_entry.get_id(), "Weekly view it is."))
assert T.entries.get(track=tok)["reply_waiting"] is False, "answering clears it"
# outsiders can't post or delete team updates
as_user(outsider)
bad(call("post_update", tr_entry.get_id(), "I'm not on the team"))
bad(call("delete_update", reply_id))
as_user(None)
assert denied("post_update", tr_entry.get_id(), "anon") and denied("delete_update", reply_id)
as_user(owner)
ok(call("delete_update", reply_id))
assert reply_id not in [u["id"] for u in ok(call("get_entry", tr_entry.get_id()))["tracking"]["updates"]]
# done: the sender sees it finished
ok(call("update_entry", tr_entry.get_id(), {"status": "done"}))
assert ok(call("track_get", tok))["stage"] == "done"
ok(call("update_entry", tr_entry.get_id(), {"status": "archived"}))
assert ok(call("track_get", tok))["stage"] == "closed"
# the owner can turn tracking off: no link after sending, and old links stop
ok(call("save_board", trb["id"], {"name": "Tracked app", "kinds": ["idea"], "public_track": False}))
as_user(None)
anvil.server.session.use("visitor-track-2")
assert ok(call("widget_submit", trb["slug"], {"message": "No tracking please"}))["track"] is None
bad(call("track_get", tok), "tracking off hides the page")
as_user(owner)
assert ok(call("get_entry", tr_entry.get_id()))["tracking"]["on"] is False
bad(call("post_update", tr_entry.get_id(), "Hello"), "no public replies while tracking is off")
# deleting feedback removes its timeline
n_upd = len(T.updates.search(entry=tr_entry))
assert n_upd > 0
ok(call("delete_entry", tr_entry.get_id()))
assert not [u for u in T.updates.search() if u["entry"] is None and u["board"] == T.boards.get(slug=trb["slug"])]
# the demo tracking page exists and refuses replies (it's shared by everyone)
as_user(None)
anvil.server.session.use("visitor-demo-track")
dtg = ok(call("track_get", "demo"))
assert dtg["stage"] == "planned" and [u for u in dtg["updates"] if u["kind"] == "reply"]
bad(call("track_reply", "demo", "Spam on the demo"))
# sample data comes with timelines
assert len(T.updates.search(board=T.boards.get(slug="demo"))) > len(M["Samples"].ENTRIES)
# deleting a link removes its updates
as_user(owner)
ok(call("delete_board", trb["id"]))
assert not [u for u in T.updates.search() if u["board"] is None]

# an older demo (before tracking) reloads itself once
M["common"].set_setting("demo_version", 1)
M["DemoData"].ensure_loaded()
assert M["common"].get_setting("demo_version") == M["DemoData"].DEMO_VERSION and T.entries.get(track="demo") is not None
n_before = len(T.entries.search(is_demo=True))
M["DemoData"].ensure_loaded()
assert len(T.entries.search(is_demo=True)) == n_before, "only once"

# ---------------------------------------------------------------------------------- API keys + the HTTP API (Claude & API)
import hashlib  # noqa: E402

AK, AR = M["ApiKeys"], M["ApiRoutes"]


def api(method, path, key=None, body=None, headers=None, **query):
    """Call an http endpoint the way a tool would (no browser session). Returns (status, json)."""
    req = anvil.server.request
    req.method, req.body = method, (json.dumps(body) if body is not None else None)
    req.headers = dict(headers or ({"Authorization": "Bearer " + key} if key else {}))
    as_user(None)
    parts = path.strip("/").split("/")
    for pattern, fn in anvil.server.ENDPOINTS.items():
        pp = pattern.strip("/").split("/")
        if len(pp) == len(parts) and all(a == b or a.startswith(":") for a, b in zip(pp, parts)):
            kw = {a[1:]: b for a, b in zip(pp, parts) if a.startswith(":")}
            kw.update(query)
            r = fn(**kw)
            assert isinstance(r, anvil.server.HttpResponse), path
            assert r.headers.get("Content-Type", "").startswith("application/json") and r.headers.get("Cache-Control") == "no-store"
            return r.status, json.loads(r.body)
    raise AssertionError("no endpoint for " + path)


assert AR.sid("[12,345]") == "12-345" and AR.rid("12-345") == "[12,345]" and AR.rid("[12,345]") == "[12,345]"
kay, lou, zoe = person("kay@example.com", "Kay Owner"), person("lou@example.com", "Lou Mate"), person("zoe@example.com", "Zoe")
as_user(kay)
kb = ok(call("save_board", None, {"name": "Kay's app", "kinds": ["bug", "idea"]}))["board"]
kb2 = ok(call("save_board", None, {"name": "Kay's other app", "kinds": ["idea"]}))["board"]
as_user(None)
anvil.server.session.use("sender-browser")
ok(call("widget_submit", kb["slug"], {"kind": "bug", "message": "Export cuts off the last page", "email": "sender@example.com",
                                      "name": "Sam Sender", "page": "https://kay.example/export"}))
ok(call("widget_submit", kb2["slug"], {"kind": "idea", "message": "Please add a dark mode"}))
k_entry = T.entries.search(board=T.boards.get(slug=kb["slug"]))[0]
k_track = k_entry["track"]
as_user(kay)
inv = ok(call("invite_member", kb["id"], "lou@example.com"))["member"]
as_user(lou)
ok(call("accept_invite", inv["token"]))

# making keys (the Claude & API page)
for fn, args in [("list_api_keys", ()), ("create_api_key", ("x",)), ("revoke_api_key", ("x",))]:
    as_user(None)
    assert denied(fn, *args), fn + " needs a signed-in member"
as_user(kay)
bad(call("create_api_key", "x"), "name too short")
bad(call("create_api_key", "Bad links", ["read"], [nb["id"]]), "only links you're on")
made = ok(call("create_api_key", "Claude on my laptop", ["write"], [], 90))
KEY = made["key"]
assert KEY.startswith("psk_") and len(KEY) == 44 and made["api_key"]["scopes"] == ["read", "write"]
row = T.api_keys.search(user=kay)[0]
assert row["hash"] == hashlib.sha256(KEY.encode()).hexdigest() and row["prefix"] == KEY[:12]
assert KEY not in json.dumps({c: str(row[c]) for c in ("name", "prefix", "hash", "scopes", "boards")}), "only a fingerprint is stored"
lk = call("list_api_keys")
assert len(lk["keys"]) == 1 and KEY not in json.dumps(lk) and "hash" not in lk["keys"][0]
rk = ok(call("create_api_key", "Replier", ["reply"], [], 30))
assert rk["api_key"]["scopes"] == ["read", "write", "reply"], "reply implies write"
REPLY_KEY = rk["key"]
READ_KEY = ok(call("create_api_key", "Read only", ["read"], [kb["id"]], 0))["key"]
assert T.api_keys.search(user=kay, name="Read only")[0]["expires"] is None, "never expires"
as_user(zoe)
bad(call("revoke_api_key", row.get_id()), "someone else's key")

# authentication
assert api("GET", "/v1/me")[0] == 401, "no key"
assert api("GET", "/v1/me", "psk_" + "x" * 40)[0] == 401, "wrong key"
assert api("GET", "/v1/me", headers={"X-Prepsto-Key": KEY})[0] == 200, "X-Prepsto-Key works too"
s, r = api("GET", "/v1/me", KEY, api_key=KEY)
assert s == 400 and "Authorization" in r["error"], "keys never go in the address"
s, r = api("GET", "/v1/me", KEY)
assert s == 200 and r["ok"] and r["user"]["name"] == "Kay Owner" and r["key"]["scopes"] == ["read", "write"]
assert {b["name"] for b in r["links"]} >= {"Kay's app", "Kay's other app"} and r["key"]["all_links"]
s, r = api("GET", "/v1/links", KEY)
assert s == 200 and any(b["name"] == "Kay's app" and b["total"] == 1 for b in r["links"])

# reading tickets: no sender email, no tracking link
s, r = api("GET", "/v1/tickets", KEY, status="all")
assert s == 200 and r["total"] >= 2
t1 = [t for t in r["tickets"] if t["message"].startswith("Export cuts")][0]
assert t1["from"] == "Sam Sender" and t1["has_email"] and t1["id"] == AR.sid(k_entry.get_id()) and "-" in t1["id"]
dump = json.dumps(r)
assert "sender@example.com" not in dump and k_track not in dump
assert api("GET", "/v1/tickets", KEY, status="nonsense")[0] == 400
assert api("GET", "/v1/tickets", KEY, link=AR.sid(nb["id"]))[0] == 404, "someone else's link"
s, r = api("GET", "/v1/tickets", KEY, link=kb2["id"], limit="1")
assert s == 200 and r["total"] == 1 and r["tickets"][0]["kind"] == "idea"
s, d = api("GET", "/v1/tickets/" + t1["id"], KEY)
assert s == 200 and d["ticket"]["page_url"] == "https://kay.example/export" and d["you_can"] == {"update": True, "reply_to_sender": False, "delete": False}
assert "sender@example.com" not in json.dumps(d) and k_track not in json.dumps(d)
assert any(p["name"] == "Lou Mate" for p in d["team"]) and d["sender"]["timeline"][0]["kind"] == "received"
assert api("GET", "/v1/tickets/" + AR.sid(eid), KEY)[0] == 404, "Ana's ticket is not Kay's"
assert api("GET", "/v1/tickets/garbage", KEY)[0] == 404

# working a ticket
s, r = api("POST", "/v1/tickets/" + t1["id"], KEY, {"status": "planned", "priority": "high", "add_tag": "Export", "assignee": "me"})
assert s == 200 and r["ticket"]["status"] == "planned" and r["ticket"]["tags"] == ["export"] and r["ticket"]["assignee"]["name"] == "Kay Owner"
assert k_entry["status"] == "planned" and k_entry["assignee"] == kay
assert [u["kind"] for u in T.updates.search(entry=k_entry)][-2:] == ["status", "priority"], "the sender's timeline follows"
s, r = api("PATCH", "/v1/tickets/" + t1["id"], KEY, {"remove_tag": "export", "starred": True})
assert s == 200 and r["ticket"]["tags"] == [] and r["ticket"]["starred"]
assert api("POST", "/v1/tickets/" + t1["id"], KEY, {"status": "gone"})[0] == 400
assert api("POST", "/v1/tickets/" + t1["id"], KEY, {"delete": True})[0] == 400, "no deleting through the API"
assert api("POST", "/v1/tickets/" + t1["id"], KEY, {})[0] == 400
assert api("POST", "/v1/tickets/" + t1["id"], KEY, {"assignee": AR.sid(zoe.get_id())})[0] == 400, "not on the team"
s, r = api("POST", "/v1/tickets/" + t1["id"], KEY, {"assignee": AR.sid(lou.get_id())})
assert s == 200 and r["ticket"]["assignee"]["name"] == "Lou Mate"
s, r = api("POST", "/v1/tickets/%s/comments" % t1["id"], KEY, {"body": "Fixed the page break in export.py (a1b2c3d)."})
assert s == 200 and T.comments.search(entry=k_entry)[0]["author"] == kay
assert api("POST", "/v1/tickets/%s/comments" % t1["id"], KEY, {"body": ""})[0] == 400
assert api("POST", "/v1/tickets/%s/replies" % t1["id"], KEY, {"body": "Fixed!"})[0] == 403, "replying needs the reply permission"
s, r = api("POST", "/v1/tickets/%s/replies" % t1["id"], REPLY_KEY, {"body": "Thanks Sam, it's fixed in today's release."})
assert s == 200 and T.updates.search(entry=k_entry, kind="reply")[0]["author"] == kay
as_user(None)
assert "fixed in today" in json.dumps(call("track_get", k_track)), "the sender sees the reply"
assert api("POST", "/v1/tickets/" + t1["id"], READ_KEY, {"status": "done"})[0] == 403, "read-only key"
assert api("GET", "/v1/tickets", READ_KEY, link=AR.sid(kb2["id"]))[0] == 404, "the read-only key only sees Kay's app"
s, r = api("GET", "/v1/tickets", READ_KEY, status="all")
assert s == 200 and {t["link"]["name"] for t in r["tickets"]} == {"Kay's app"}

# stories
s, r = api("POST", "/v1/stories", KEY, {"ticket_ids": [t1["id"]]})
assert s == 200 and r["story"]["link"]["name"] == "Kay's app"
sid_ = r["story"]["id"]
s, r = api("GET", "/v1/stories/" + sid_, KEY, format="markdown")
assert s == 200 and r["text"].startswith("# ") and "Export cuts off" in r["text"] and "sender@example.com" not in r["text"]
s, r = api("POST", "/v1/stories/" + sid_, KEY, {"status": "ready", "acceptance": ["Given a long export, when I save it, then every page is there"]})
assert s == 200 and r["story"]["status"] == "ready" and r["story"]["title"], "partial update keeps the title"
assert api("POST", "/v1/stories/" + sid_, KEY, {"owner": "x"})[0] == 400
s, r = api("GET", "/v1/stories", KEY)
assert s == 200 and any(x["id"] == sid_ for x in r["stories"])
s, r = api("GET", "/v1/stories/" + sid_, KEY, format="gherkin")
assert "Scenario: a long export" in r["text"]
assert api("POST", "/v1/stories/%s/comments" % sid_, KEY, {"body": "Ready for the next sprint"})[0] == 200
assert api("POST", "/v1/stories", READ_KEY, {"ticket_ids": [t1["id"]]})[0] == 403

# a teammate's key follows their membership
as_user(lou)
LOU_KEY = ok(call("create_api_key", "Lou's Claude", ["write"], [], 30))["key"]
assert api("GET", "/v1/tickets/" + t1["id"], LOU_KEY)[0] == 200
as_user(kay)
lou_member = [p for p in ok(call("list_team", kb["id"]))["people"] if p["name"] == "Lou Mate"][0]
ok(call("remove_member", kb["id"], lou_member["id"]))
assert api("GET", "/v1/tickets/" + t1["id"], LOU_KEY)[0] == 404, "removed from the team = no access"

# revoked, expired, disabled, rate limit
as_user(kay)
lou_row = T.api_keys.search(user=lou)[0]
bad(call("revoke_api_key", lou_row.get_id()), "only your own keys")
as_user(lou)
assert ok(call("revoke_api_key", lou_row.get_id()))["api_key"]["state"] == "revoked"
s, r = api("GET", "/v1/me", LOU_KEY)
assert s == 401 and "revoked" in r["error"]
krow = T.api_keys.get(hash=hashlib.sha256(KEY.encode()).hexdigest())
krow["window_count"], krow["window_start"] = AK.RATE, M["common"].now()
assert api("GET", "/v1/me", KEY)[0] == 429
krow["window_start"] = M["common"].now() - dt.timedelta(seconds=AK.WINDOW + 1)
assert api("GET", "/v1/me", KEY)[0] == 200, "a new window"
krow["expires"] = M["common"].now() - dt.timedelta(minutes=1)
s, r = api("GET", "/v1/me", KEY)
assert s == 401 and "expired" in r["error"]
krow["expires"] = None
kay["enabled"] = False
assert api("GET", "/v1/me", KEY)[0] == 403
kay["enabled"] = True
for i in range(AK.MAX_KEYS):
    as_user(zoe)
    call("create_api_key", "Zoe %d" % i)
as_user(zoe)
bad(call("create_api_key", "One too many"), "at most MAX_KEYS active keys")

# the log
as_user(kay)
lk = call("list_api_keys")
assert lk["log"] and all(set(x) == {"created", "key", "action", "status"} for x in lk["log"])
assert any(x["status"] == 403 for x in lk["log"]) and any(x["action"].startswith("POST /v1/tickets/") for x in lk["log"])
assert krow["uses"] > 10 and krow["last_used"] is not None

# ---------------------------------------------------------------------------------- Privacy & Terms
if "legal_server" in M:
    as_user(ana)
    st = call("legal_state")
    assert st["signedIn"] and st["accepted_version"] is None
    ok(call("legal_accept", st["version"], "signup"))
    assert ana["legal_source"] == "signup" and call("legal_state")["accepted_version"] == st["version"]

# ---------------------------------------------------------------------------------- every callable is covered by a permission check
# A callable that changes data without require_user / a C.require_* check is a security hole. List the public ones here.
PUBLIC = {"get_me", "submit_feedback", "widget_config", "widget_submit", "get_invite", "legal_state", "legal_accept",
          "track_get", "track_list", "track_reply"}
for name, (f, need) in sorted(anvil.server.CALLABLES.items()):
    if name in PUBLIC:
        continue
    assert need, "%s is callable by anyone: add require_user=True (or list it in PUBLIC in test_server.py)" % name

print("ALL OK (%d server functions)" % len(anvil.server.CALLABLES))
