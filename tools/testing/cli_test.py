"""The prepsto CLI (theme/assets/prepsto-cli.py) and its MCP server against a running Prepsto (the local App Server).

    python -I tools/testing/cli_test.py <api key> [url]      (url default: the local App Server of tools/ui_test.py)

tools/ui_test.py's flow.js prints a key it leaves active ("CLIKEY psk_..."); ui_test.py runs this file with it.
Uses a throwaway home folder, so your own ~/.prepsto/config.json is never touched. Prints CLI TESTS PASSED.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
CLI = ROOT / "theme" / "assets" / "prepsto-cli.py"
KEY = sys.argv[1]
URL = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:%d" % (3100 + sum(map(ord, "prepsto")) % 800)
HOME = tempfile.mkdtemp(prefix="prepsto-cli-")
ENV = dict(os.environ, HOME=HOME, USERPROFILE=HOME, PYTHONIOENCODING="utf-8")
ENV.pop("PREPSTO_KEY", None)
ENV.pop("PREPSTO_URL", None)


def run(*args, ok=True, stdin=None):
    r = subprocess.run([sys.executable, "-I", str(CLI)] + list(args), capture_output=True, text=True, encoding="utf-8",
                       env=ENV, input=stdin, timeout=120)
    if ok and r.returncode:
        sys.exit("FAILED: prepsto %s\n%s%s" % (" ".join(args), r.stdout, r.stderr))
    return r


def check(cond, msg):
    if not cond:
        sys.exit("FAILED: " + msg)
    print("ok   " + msg)


r = run("tickets", ok=False)
check(r.returncode == 1 and "No API key yet" in r.stderr, "without a key it says how to get one")
r = run("login", "--url", URL, "--key", KEY)
check("Signed in as" in r.stdout, "login saves the key")
cfg = pathlib.Path(HOME, ".prepsto", "config.json")
check(json.loads(cfg.read_text())["key"] == KEY, "config file written")
check("reply" in run("whoami").stdout, "whoami shows the key's permissions")
check(run("links").stdout.strip() != "", "links")
out = json.loads(run("--json", "tickets", "--status", "all", "--limit", "5").stdout)
check(len(out["tickets"]) == 5 and out["total"] > 5, "tickets --json")
tid = out["tickets"][0]["id"]
check("Open in Prepsto" in run("show", tid).stdout, "show prints the ticket")
check("assigned to you" in run("claim", tid).stdout, "claim")
check("updated" in run("set", tid, "--priority", "high", "--tag", "cli").stdout, "set --priority --tag")
check("Team comment added" in run("comment", tid, "-", stdin="Checked from the CLI test").stdout, "comment from stdin")
check("done" in run("done", tid, "--comment", "Fixed in the CLI test", "--reply", "Thanks! Fixed.").stdout, "done --comment --reply")
d = json.loads(run("--json", "show", tid).stdout)
check(d["ticket"]["status"] == "done" and "cli" in d["ticket"]["tags"] and d["ticket"]["assignee"], "the changes are there")
check(any(u["kind"] == "reply" for u in d["sender"]["timeline"]), "the sender sees the reply")
r = run("show", "999999-1", ok=False)
check(r.returncode == 1 and "no ticket" in r.stderr.lower(), "a wrong id is a clear error")
stories = json.loads(run("--json", "stories").stdout)["stories"]
check(stories and run("story", stories[0]["id"]).stdout.startswith("# "), "story as Markdown")

# the MCP server: what Claude Code talks to
msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                                                         "clientInfo": {"name": "test", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "list_tickets", "arguments": {"kind": "bug", "limit": 3}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "get_ticket", "arguments": {"ticket_id": tid}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "update_ticket", "arguments": {"ticket_id": tid, "status": "planned"}}},
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "get_ticket", "arguments": {"ticket_id": "nope"}}},
        {"jsonrpc": "2.0", "id": 7, "method": "nonsense"}]
r = run("mcp", stdin="\n".join(json.dumps(m) for m in msgs) + "\n")
answers = {a["id"]: a for a in (json.loads(line) for line in r.stdout.splitlines() if line.strip())}
check(answers[1]["result"]["serverInfo"]["name"] == "prepsto" and "tools" in answers[1]["result"]["capabilities"], "mcp: initialize")
names = [t["name"] for t in answers[2]["result"]["tools"]]
check({"list_tickets", "get_ticket", "update_ticket", "add_team_comment", "reply_to_sender", "draft_story"} <= set(names), "mcp: tools/list")
bugs = answers[3]["result"]["structuredContent"]["tickets"]
check(all(t["kind"] == "bug" for t in bugs) and len(bugs) <= 3, "mcp: list_tickets with filters")
check(answers[4]["result"]["structuredContent"]["ticket"]["id"] == tid, "mcp: get_ticket")
check(answers[5]["result"]["structuredContent"]["ticket"]["status"] == "planned", "mcp: update_ticket")
check(answers[6]["result"].get("isError") is True, "mcp: a failing tool call is an error result, not a crash")
check(answers[7]["error"]["code"] == -32601, "mcp: unknown methods are refused")
check(2 not in [a for a in answers if "error" in answers[a]] and len(answers) == 7, "mcp: notifications get no answer")
check("Signed in" not in run("logout").stdout and "key" not in json.loads(cfg.read_text()), "logout removes the key")
print("CLI TESTS PASSED")
