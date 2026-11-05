from anvil import *
import anvil.server

from ._anvil_designer import ClaudeTemplate
from ... import px, state

TABS = [("claude", "Claude Code", "sparkle"), ("cli", "Command line", "terminal"), ("http", "HTTP API", "code")]
HOME = "https://prepsto.com"


class Claude(ClaudeTemplate):
    """#claude, "Claude & API": API keys (make one, see what each may do, revoke), the last requests made with them,
    and how to connect Claude Code (theme/assets/prepsto-cli.py = the prepsto command line + MCP server,
    theme/assets/prepsto-skill.md = a Claude Code skill), the command line, or plain HTTP (server_code/ApiRoutes.py)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.tab = state.store_get("claude.tab", "claude")
        self.links = []
        state.heading(self.title, 1)
        self.keys_panel.add_event_handler("x-revoke", self._revoke)
        self.tabs_panel.add_event_handler("x-pick", self._pick_tab)
        origin = px.base().rstrip("/")
        self.origin = origin
        self.api = anvil.server.get_api_origin().rstrip("/")
        if not self.api.endswith("/_/api"):
            self.api += "/_/api"
        self._load()
        self._setup()

    def _load(self):
        d = state.call("list_api_keys")
        if d is None:
            return
        self.links = d["links"]
        keys = d["keys"]
        self.keys_panel.items = keys
        self.keys_panel.visible = bool(keys)
        self.no_keys.visible = not keys
        active = len([k for k in keys if k["state"] == "active"])
        self.keys_count.text = "%d active" % active if keys else ""
        self.log_panel.items = d["log"]
        self.no_log.visible = not d["log"]
        lim = d["limits"]
        self.rate.text = "%d requests every %d minutes" % (lim["rate"], lim["window"] // 60)

    # ------------------------------------------------------------------ setup instructions
    def _login(self):
        return "python prepsto.py login" + ("" if self.origin == HOME else " --url " + self.origin)

    def _setup(self):
        self.tabs_panel.items = [{"key": k, "label": label, "icon": ic, "on": self.tab == k} for k, label, ic in TABS]
        if self.tab == "claude":
            self.intro.text = "Needs Python 3.8 or newer, nothing else to install. Save prepsto.py somewhere it can stay, then run:"
            self.code.text = "\n".join([
                self._login() + "                # paste your key when asked",
                'claude mcp add prepsto -- python "/full/path/to/prepsto.py" mcp',
                "", "# optional: teach Claude the workflow in one project",
                "# save SKILL.md as .claude/skills/prepsto/SKILL.md"])
            self.after.text = ('Then ask Claude: "Work through my open Prepsto bugs: fix each one, add a note about what changed '
                               'and mark it done." Claude asks you before it replies to anyone who sent feedback.')
        elif self.tab == "cli":
            self.intro.text = "The same file works on its own in any terminal:"
            self.code.text = "\n".join([
                self._login(),
                "python prepsto.py tickets                 # open tickets, newest first",
                "python prepsto.py tickets --kind bug --mine",
                "python prepsto.py show <id>",
                "python prepsto.py claim <id>              # assign it to you",
                'python prepsto.py comment <id> "Fixed in a1b2c3d"',
                'python prepsto.py done <id> --reply "Thanks! It\'s fixed in today\'s release."',
                'python prepsto.py new --link <code> "Idea: export to PDF"   # file one yourself'])
            self.after.text = "Add --json to any command for the raw answer. python prepsto.py help lists everything."
        else:
            self.intro.text = "Any language: send the key in the Authorization header. JSON in, JSON out."
            self.code.text = "\n".join([
                'curl -H "Authorization: Bearer $PREPSTO_KEY" \\',
                '  "%s/v1/tickets?status=open&limit=10"' % self.api, "",
                'curl -X POST -H "Authorization: Bearer $PREPSTO_KEY" \\',
                '  -H "Content-Type: application/json" -d \'{"status": "done"}\' \\',
                '  "%s/v1/tickets/<id>"' % self.api])
            self.after.text = ("Endpoints: /v1/me, /v1/links, /v1/tickets (POST files a new one), /v1/tickets/<id> (and /comments, /replies), "
                               "/v1/stories, /v1/stories/<id>?format=markdown. Never put the key in the address.")

    def _pick_tab(self, key=None, **event_args):
        k = state.focus_key()
        self.tab = key
        state.store_set("claude.tab", key)
        self._setup()
        state.refocus(self.tabs_panel, k)

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        state.copy(self.code.text, "Commands copied")

    # ------------------------------------------------------------------ keys
    @handle("new_button", "click")
    def new_button_click(self, **event_args):
        self._new()

    @handle("first_button", "click")
    def first_button_click(self, **event_args):
        self._new()

    def _new(self):
        from ...Dialogs.NewKey import NewKey
        r = alert(NewKey(links=self.links), buttons=[], role="app-dialog")
        if not r:
            return
        self._load()
        from ...Dialogs.KeyCreated import KeyCreated
        setup = "\n".join([self._login(), 'claude mcp add prepsto -- python "/full/path/to/prepsto.py" mcp'])
        alert(KeyCreated(key=r["key"], setup=setup), buttons=[], role="app-dialog", dismissible=False)

    def _revoke(self, key=None, **event_args):
        key = key or {}
        if confirm("Anything using it stops working straight away. This can't be undone.", title='Revoke "%s"?' % key["name"],
                   buttons=[("Cancel", False), ("Revoke", True)], role="app-dialog"):
            if state.call("revoke_api_key", key["id"]):
                state.toast("Key revoked", "ok")
                self._load()
