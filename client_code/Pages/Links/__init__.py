from anvil import *
import anvil.js
import anvil.server

from ._anvil_designer import LinksTemplate
from ... import px, router, state

SWATCHES = ["#2b59ff", "#0c0e14", "#ff5a1f", "#0f8a5f", "#7c3aed", "#e11d74", "#0891b2"]
BLANK: dict = {"id": "", "name": "", "site_url": "", "prompt": "How can we make this better?", "thanks": "Thank you! We read every message.",
         "label": "Feedback", "color": "#2b59ff", "position": "right", "kinds": ["bug", "idea", "praise", "question"],
         "ask_email": True, "ask_rating": True, "is_open": True, "public_track": True, "slug": "preview", "role": "owner"}
TABS = [("script", "Script", "code"), ("link", "Link", "link"), ("button", "Own button", "sliders"), ("html", "HTML link", "external")]


class Links(LinksTemplate):
    """#links, #links/<id>, #links/new: the member's feedback links (and the ones shared with them, read-only).
    Settings (name, question, kinds, colour, button, thank-you text, rating/email, open, tracking) with a live preview
    of the panel on a pretend site; install code (script tag, plain link, own button, HTML link); the Team card
    (invite by email, copy invite links, remove, leave); Manage (new code, re-run insights, delete)."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.arg = args[0] if args else ""
        self.tab = state.store_get("links.tab", "script")
        self.boards, self._timer, self._code, self.color = [], None, "", "#2b59ff"
        self.cur: dict = dict(BLANK)
        state.heading(self.title, 1)
        self.position_box.items = [("Bottom right", "right"), ("Bottom left", "left")]
        state.set_control_attr(self.url_box, "readonly", "readonly")
        state.set_control_attr(self.url_box, "aria-label", "Link")
        state.set_control_attr(self.invite_box, "aria-label", "Teammate's email")
        for box, n in ((self.name_box, 60), (self.site_box, 200), (self.prompt_box, 140), (self.label_box, 24), (self.thanks_box, 200)):
            el = state.control(box)
            el.setAttribute("maxlength", str(n))
            el.addEventListener("input", anvil.js.report_exceptions(self._typed))
        self.kinds_panel.add_event_handler("x-changed", self._paint)
        self.swatches_panel.add_event_handler("x-color", self._pick_color)
        self.tabs_panel.add_event_handler("x-pick", self._pick_tab)
        self.team_panel.add_event_handler("x-remove", self._remove_member)
        self.preview_panel.setup(dict(BLANK), preview=True, on_close=lambda: None)
        self._load()

    # ------------------------------------------------------------------ loading
    def _load(self):
        d = state.call("list_boards")
        if d is None:
            return
        self.boards = d["boards"]
        a = self.arg
        if a == "new" or not self.boards:
            self.cur = dict(BLANK)
        else:
            hit = [b for b in self.boards if b["id"] == a] or [b for b in self.boards if not b.get("is_sample")] or self.boards
            self.cur = dict(hit[0])
        self._draw()

    def _draw(self):
        b, is_new = self.cur, not self.cur.get("id")
        ro = b.get("role") == "member"
        self.picks_panel.items = [dict(x, on=x["id"] == b.get("id")) for x in self.boards] + [{"_new": True, "on": is_new}]
        self.sample_note.visible = bool(b.get("is_sample")) and b.get("role") == "owner"
        self.settings_title.text = "Panel settings" if not is_new else "New feedback link"
        self.ro_note.visible = ro
        self.ro_note.text = "Shared with you by %s. Only the owner can change these settings." % b.get("owner_name", "")
        self.name_box.text, self.site_box.text, self.prompt_box.text = b.get("name") or "", b.get("site_url") or "", b.get("prompt") or ""
        self.label_box.text, self.thanks_box.text = b.get("label") or "", b.get("thanks") or ""
        self.position_box.selected_value = b.get("position") or "right"
        state.set_control_attr(self.position_box, "aria-label", "Button position")
        self.rating_box.checked, self.email_box.checked = bool(b.get("ask_rating")), bool(b.get("ask_email"))
        self.open_box.checked, self.track_box.checked = bool(b.get("is_open")), b.get("public_track") is not False
        kinds = list(b.get("kinds") or [])
        order = kinds + [k for k in px.KIND_ORDER if k not in kinds]
        self.kinds_panel.items = [{"kind": k, "on": k in kinds, "enabled": not ro} for k in order]
        self.color = b.get("color") or "#2b59ff"
        self.dom_nodes["color_input"].value = self.color
        self.dom_nodes["color_input"].disabled = ro
        for box in (self.name_box, self.site_box, self.prompt_box, self.label_box, self.thanks_box, self.position_box,
                    self.rating_box, self.email_box, self.open_box, self.track_box):
            box.enabled = not ro
        self.save_row.visible = not ro
        self.save_button.text = "Create link" if is_new else "Save changes"
        self.cancel_button.visible = is_new and bool(self.boards)
        self.install_part.visible = self.team_part.visible = self.manage_part.visible = not is_new
        if not is_new:
            self._install()
            self._manage()
            self._team()
        self._paint()

    # ------------------------------------------------------------------ the form + live preview
    def _values(self):
        return {"name": self.name_box.text or "", "site_url": self.site_box.text or "", "prompt": self.prompt_box.text or "",
                "thanks": self.thanks_box.text or "", "label": self.label_box.text or "", "color": self.color,
                "position": self.position_box.selected_value or "right",
                "kinds": [it["kind"] for it in self.kinds_panel.items if it.get("on")],
                "ask_email": self.email_box.checked, "ask_rating": self.rating_box.checked, "is_open": self.open_box.checked,
                "public_track": self.track_box.checked}

    def _typed(self, event):
        state.cancel(self._timer)
        self._timer = state.later(self._paint, 120)

    def _paint(self, **event_args):
        v: dict = dict(self.cur)
        if self.cur.get("role") != "member":
            v.update(self._values())
        v["name"] = v.get("name") or "Your app"
        v["prompt"] = v.get("prompt") or BLANK["prompt"]
        v["label"] = v.get("label") or "Feedback"
        v["kinds"] = v.get("kinds") or ["idea"]
        self.stage.classes.update({"left": v["position"] == "left", "right": v["position"] != "left"})
        anvil.js.get_dom_node(self.fab).style.background = v["color"]
        self.fab_label.text = v["label"]
        self.host.text = px.host(v.get("site_url")) or "your-site.com"
        self.preview_panel.update(v)
        ro = self.cur.get("role") == "member"
        self.swatches_panel.items = [{"color": c, "on": c == v["color"], "enabled": not ro} for c in SWATCHES]

    def _pick_color(self, color=None, **event_args):
        self.color = color or "#2b59ff"
        self.dom_nodes["color_input"].value = self.color
        self._paint()

    def color_input(self, event):
        self.color = self.dom_nodes["color_input"].value
        self._paint()

    @handle("position_box", "change")
    def position_box_change(self, **event_args):
        self._paint()

    @handle("rating_box", "change")
    def rating_box_change(self, **event_args):
        self._paint()

    @handle("email_box", "change")
    def email_box_change(self, **event_args):
        self._paint()

    @handle("open_box", "change")
    def open_box_change(self, **event_args):
        self._paint()

    @handle("track_box", "change")
    def track_box_change(self, **event_args):
        self._paint()

    @handle("save_button", "click")
    def save_button_click(self, **event_args):
        is_new = not self.cur.get("id")
        r = state.call("save_board", self.cur.get("id") or None, self._values())
        if r:
            state.toast("Link created. Now put it on your site!" if is_new else "Saved", "ok")
            if is_new:
                self.tab = "script"
                state.store_set("links.tab", "script")
                router.go("links", r["board"]["id"])
            else:
                self._load()

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        router.go("links")

    # ------------------------------------------------------------------ install code
    def _install(self):
        b = self.cur
        self.tabs_panel.items = [{"key": k, "label": label, "icon": ic, "on": self.tab == k} for k, label, ic in TABS]
        self.link_part.visible, self.code_part.visible = self.tab == "link", self.tab != "link"
        link = px.link(b)
        self.url_box.text = link
        state.set_attr(self.open_link, "href", link)
        if self.tab == "script":
            self._code = px.snippet(b)
        elif self.tab == "button":
            self._code = px.snippet(b).replace(" async>", ' data-button="false" async>') + "\n\n<button data-prepsto-open>Give feedback</button>"
        else:
            self._code = px.anchor(b)
        self.code.text = self._code
        self.step_script.visible = self.tab == "script"
        self.step_button.visible = self.tab == "button"
        self.step_html.visible = self.tab == "html"
        self.step2.text = 'A "%s" button appears; it slides the panel in. The page address is sent with each message.' % (b.get("label") or "Feedback")

    def _pick_tab(self, key=None, **event_args):
        k = state.focus_key()
        self.tab = key
        state.store_set("links.tab", key)
        self._install()
        state.refocus(self.tabs_panel, k)

    @handle("copy_link_button", "click")
    def copy_link_button_click(self, **event_args):
        state.copy(px.link(self.cur), "Link copied")

    @handle("copy_code_button", "click")
    def copy_code_button_click(self, **event_args):
        state.copy(self._code, "Code copied")

    # ------------------------------------------------------------------ team
    def _team(self):
        board_id = self.cur["id"]
        d = state.call_quiet("list_team", board_id)
        if not d or not d.get("ok") or self.cur.get("id") != board_id:
            return
        owner = bool(d.get("is_owner"))
        self.team_count.text = state.plural(len([p for p in d["people"] if p["status"] == "active"]), "person", "people")
        self.team_panel.items = [dict(p, _owner=owner) for p in d["people"]]
        self.invite_row.visible = owner
        self.team_hint.text = ("They see the invitation when they sign in with that email. Prepsto doesn't send email: copy the invite "
                               "link and send it yourself to be sure. Teammates can triage, assign, comment and write stories; only you "
                               "change settings and the team.") if owner else \
            "Type @ in a comment to mention a teammate. Only %s can invite people." % self.cur.get("owner_name", "the owner")

    @handle("invite_box", "pressed_enter")
    def invite_box_pressed_enter(self, **event_args):
        self.invite_button_click()

    @handle("invite_button", "click")
    def invite_button_click(self, **event_args):
        r = state.call("invite_member", self.cur["id"], self.invite_box.text or "")
        if r:
            self.invite_box.text = ""
            state.copy(px.base() + "#join/" + r["member"]["token"], "Invited %s. Invite link copied" % r["member"]["email"])
            self._team()

    def _remove_member(self, member_id=None, leave=False, who="", **event_args):
        if leave:
            ok = confirm("You lose access to its feedback and stories. The owner can invite you again.",
                         title='Leave "%s"?' % self.cur["name"], buttons=[("Cancel", False), ("Leave", True)], role="app-dialog")
        else:
            ok = confirm("They lose access to this link's feedback and stories. Their comments stay.", title="Remove %s?" % who,
                         buttons=[("Cancel", False), ("Remove", True)], role="app-dialog")
        if not ok:
            return
        r = state.call("remove_member", self.cur["id"], member_id)
        if r:
            if r.get("left"):
                state.toast("You left the team", "ok")
                router.go("links")
            else:
                state.toast("Removed", "ok")
                self._team()

    # ------------------------------------------------------------------ manage
    def _manage(self):
        b, owner = self.cur, self.cur.get("role") == "owner"
        self.code_line.text = "code: %s · created %s · %s" % (b["slug"], state.fmt_date(b.get("created")), state.plural(b.get("total", 0), "message"))
        self.newcode_button.visible = self.delete_button.visible = self.manage_hint.visible = owner

    @handle("inbox_button", "click")
    def inbox_button_click(self, **event_args):
        f = dict(state.store_get("inbox.filters", {}) or {})
        f.update(board=self.cur["id"], status="open")
        state.store_set("inbox.filters", f)
        router.go("inbox")

    @handle("newcode_button", "click")
    def newcode_button_click(self, **event_args):
        if confirm("The current link and snippet stop working right away. You'll need to update your site with the new code.",
                   title="Make a new code?", buttons=[("Cancel", False), ("New code", True)], role="app-dialog"):
            r = state.call("new_board_code", self.cur["id"])
            if r:
                state.toast("New code: " + r["board"]["slug"], "ok")
                self._load()

    @handle("reanalyze_button", "click")
    def reanalyze_button_click(self, **event_args):
        r = state.call("reanalyze_board", self.cur["id"])
        if r:
            state.toast("Insights updated for " + state.plural(r["count"], "message"), "ok")

    @handle("delete_button", "click")
    def delete_button_click(self, **event_args):
        b = self.cur
        if confirm("Its %s, stories and comments are deleted for good, and the link stops working." % state.plural(b.get("total", 0), "message"),
                   title='Delete "%s"?' % b["name"], buttons=[("Cancel", False), ("Delete link", True)], role="app-dialog"):
            if state.call("delete_board", b["id"]) is not None:
                state.toast("Link deleted", "ok")
                router.go("links")
