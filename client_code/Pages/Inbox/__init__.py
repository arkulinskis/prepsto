from anvil import *
import anvil.server

from ._anvil_designer import InboxTemplate
from ... import px, router, state

COLS = ["new", "reviewing", "planned", "done"]
PAGE = 60  # rows drawn at a time (the browser's Python is slow with hundreds of rows)
SORTS = [("Newest first", "newest"), ("Oldest first", "oldest"), ("Priority", "priority"), ("Lowest rating", "rating")]


class Inbox(InboxTemplate):
    """#inbox, #inbox/tag/<tag>, #inbox/entry/<id> (opens that feedback's drawer): every piece of feedback on the
    member's links. List view (status tabs, select + bulk actions: status, tag, draft a story, delete) and Board view
    (New / Reviewing / Planned / Done; drag a card to change its status). Filters and view are remembered."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.args = list(args)
        f = state.store_get("inbox.filters", {}) or {}
        self.f = {"board": f.get("board") or "", "kind": f.get("kind") or "", "tag": f.get("tag") or "",
                  "sort": f.get("sort") or "newest", "starred": bool(f.get("starred")), "mine": bool(f.get("mine")),
                  "status": f.get("status") or "open", "q": ""}
        if len(args) > 1 and args[0] == "tag":
            self.f["tag"], self.f["status"] = args[1], "all"
        self.mode = state.store_get("inbox.mode", "list")
        self.picked, self.shown, self._timer = set(), PAGE, None
        self.data: dict = {"entries": []}
        state.heading(self.title, 1)
        state.set_control_attr(self.search_box, "type", "search")
        state.set_control_attr(self.search_box, "aria-label", "Search")
        self.sort_box.items = SORTS
        self.kind_box.items = [("All kinds", "")] + [(px.KINDS[k][0], k) for k in px.KIND_ORDER]
        self.bulk_status.items = [("Set status…", "")] + [(label, key) for key, label in px.STATUSES]
        self.status_panel.add_event_handler("x-pick", self._pick_status)
        self.rows_panel.add_event_handler("x-open", self._open)
        self.rows_panel.add_event_handler("x-pick", self._pick_row)
        self.cols_panel.add_event_handler("x-open", self._open)
        self.cols_panel.add_event_handler("x-move", self._move)
        self._load()

    def opened(self):
        if len(self.args) > 1 and self.args[0] == "entry":
            entry_id = self.args[1]
            state.later(lambda: self._open(entry_id=entry_id), 80)

    def _save(self):
        state.store_set("inbox.filters", {k: self.f[k] for k in ("board", "kind", "tag", "sort", "starred", "mine", "status")})

    # ------------------------------------------------------------------ data
    def _load(self, **event_args):
        q = dict(self.f, status="all" if self.mode == "board" else self.f["status"])
        d = state.call_quiet("get_inbox", q)
        if d is None:
            d = state.call("get_inbox", q)
        if d is None:
            return
        if self.f["board"] and not any(b["id"] == self.f["board"] for b in d["boards"]):
            self.f["board"] = ""
            self._save()
            return self._load()
        if self.mode == "board":
            d["entries"] = [e for e in d["entries"] if e["status"] != "archived"]
        ids = set(e["id"] for e in d["entries"])
        self.picked = set(i for i in self.picked if i in ids)
        self.data = d
        self._draw()

    def _draw(self):
        d, f = self.data, self.f
        self.list_button.role = ["seg"] + (["on"] if self.mode == "list" else [])
        self.board_button.role = ["seg"] + (["on"] if self.mode == "board" else [])
        state.set_control_attr(self.list_button, "aria-pressed", "true" if self.mode == "list" else "false")
        state.set_control_attr(self.board_button, "aria-pressed", "true" if self.mode == "board" else "false")
        self.board_box.items = [("All links", "")] + [(b["name"] + (" (shared)" if b.get("role") == "member" else ""), b["id"]) for b in d["boards"]]
        self.board_box.selected_value = f["board"]
        tags = list(d["tags"])
        if f["tag"] and f["tag"] not in tags:
            tags.insert(0, f["tag"])
        self.tag_box.items = [("All tags", "")] + [("#" + t, t) for t in tags]
        self.tag_box.selected_value = f["tag"]
        self.kind_box.selected_value = f["kind"]
        self.sort_box.selected_value = f["sort"]
        for box, name in ((self.board_box, "Link"), (self.kind_box, "Kind"), (self.tag_box, "Tag"), (self.sort_box, "Sort"),
                          (self.bulk_status, "Set status")):
            state.set_control_attr(box, "aria-label", name)
        self.starred_button.role = ["btn", "btn-sm", "ic-star"] + (["on"] if f["starred"] else [])
        self.mine_button.role = ["btn", "btn-sm", "ic-user"] + (["on"] if f["mine"] else [])
        state.set_control_attr(self.starred_button, "aria-pressed", "true" if f["starred"] else "false")
        state.set_control_attr(self.mine_button, "aria-pressed", "true" if f["mine"] else "false")
        self.clear_button.visible = bool(f["board"] or f["kind"] or f["tag"] or f["starred"] or f["mine"] or f["q"])
        self.list_part.visible, self.board_part.visible = self.mode == "list", self.mode == "board"
        if self.mode == "board":
            self.bulk.visible = False
            by = {c: [] for c in COLS}
            for e in d["entries"]:
                if e["status"] in by:
                    by[e["status"]].append(e)
            self.cols_panel.items = [{"status": c, "entries": by[c]} for c in COLS]
            return
        tabs = [("open", "Open")] + list(px.STATUSES) + [("all", "All")]
        self.status_panel.items = [{"key": k, "label": label, "count": d["counts"].get(k, 0), "on": f["status"] == k} for k, label in tabs]
        rows = d["entries"]
        self.count_part.visible = bool(rows)
        self.all_box.checked = bool(rows) and len(self.picked) == len(rows)
        self.total.text = state.plural(d["total"], "result")
        self.rows_panel.items = [dict(e, _select=True, _picked=e["id"] in self.picked, _board=not f["board"]) for e in rows[:self.shown]]
        self.more_part.visible = len(rows) > self.shown
        self.more_button.text = "Show more (%d more)" % (len(rows) - self.shown)
        self.empty.visible = not rows
        filtered = f["q"] or f["kind"] or f["tag"] or f["board"] or f["starred"] or f["mine"]
        self.empty_title.text = "Nothing matches these filters" if filtered else "Nothing here"
        self.empty_text.text = "No new feedback. Everything has been looked at." if f["status"] == "new" else "Try another tab or clear the filters."
        self._bulk()

    def _bulk(self):
        n = len(self.picked)
        self.bulk.visible = self.mode == "list" and n > 0
        self.picked_count.text = "%d selected" % n
        self.bulk_status.selected_value = ""

    # ------------------------------------------------------------------ view + filters
    @handle("list_button", "click")
    def list_button_click(self, **event_args):
        self._mode("list")

    @handle("board_button", "click")
    def board_button_click(self, **event_args):
        self._mode("board")

    def _mode(self, mode):
        self.mode = mode
        state.store_set("inbox.mode", mode)
        self.picked = set()
        self._load()

    def _pick_status(self, key=None, **event_args):
        k = state.focus_key()
        self.f["status"], self.picked, self.shown = key, set(), PAGE
        self._save()
        self._load()
        state.refocus(self.status_panel, k)

    def _filter(self, name, value):
        self.f[name], self.shown = value, PAGE
        self._save()
        self._load()

    @handle("board_box", "change")
    def board_box_change(self, **event_args):
        self._filter("board", self.board_box.selected_value or "")

    @handle("kind_box", "change")
    def kind_box_change(self, **event_args):
        self._filter("kind", self.kind_box.selected_value or "")

    @handle("tag_box", "change")
    def tag_box_change(self, **event_args):
        self._filter("tag", self.tag_box.selected_value or "")

    @handle("sort_box", "change")
    def sort_box_change(self, **event_args):
        self._filter("sort", self.sort_box.selected_value or "newest")

    @handle("starred_button", "click")
    def starred_button_click(self, **event_args):
        self._filter("starred", not self.f["starred"])

    @handle("mine_button", "click")
    def mine_button_click(self, **event_args):
        self._filter("mine", not self.f["mine"])

    @handle("clear_button", "click")
    def clear_button_click(self, **event_args):
        self.f.update(board="", kind="", tag="", q="", starred=False, mine=False)
        self.search_box.text = ""
        self._filter("q", "")

    @handle("search_box", "change")
    def search_box_change(self, **event_args):
        state.cancel(self._timer)
        self._timer = state.later(self._search, 300)

    @handle("search_box", "pressed_enter")
    def search_box_pressed_enter(self, **event_args):
        state.cancel(self._timer)
        self._search()

    def _search(self):
        self._timer = None
        if (self.search_box.text or "") != self.f["q"]:
            self._filter("q", self.search_box.text or "")

    @handle("more_button", "click")
    def more_button_click(self, **event_args):
        self.shown += PAGE
        self._draw()

    # ------------------------------------------------------------------ rows
    def _open(self, entry_id=None, **event_args):
        from ...Dialogs.Drawer import LAST, Drawer
        r = alert(Drawer(entry_id=entry_id), buttons=[], role="px-drawer", large=True, dismissible=True)
        if isinstance(r, dict) and r.get("go"):
            router.go(*r["go"])
        elif r or LAST["changed"]:
            self._load()

    def _pick_row(self, entry_id=None, on=False, **event_args):
        if on:
            self.picked.add(entry_id)
        else:
            self.picked.discard(entry_id)
        for row in self.rows_panel.get_components():
            it = getattr(row, "item", None)
            if it and it["id"] == entry_id:
                it["_picked"] = on
                getattr(row, "classes")["picked"] = on
        self.all_box.checked = bool(self.data["entries"]) and len(self.picked) == len(self.data["entries"])
        self._bulk()

    @handle("all_box", "change")
    def all_box_change(self, **event_args):
        self.picked = set(e["id"] for e in self.data["entries"]) if self.all_box.checked else set()
        self._draw()

    def _move(self, entry_id=None, status=None, **event_args):
        e = [x for x in self.data["entries"] if x["id"] == entry_id]
        if not e or e[0]["status"] == status:
            return
        e[0]["status"] = status
        self._draw()
        r = anvil.server.call_s("update_entry", entry_id, {"status": status})
        if r.get("ok"):
            state.toast("Moved to " + px.label_of(px.STATUSES, status), "ok")
        else:
            state.toast(r.get("error") or "That didn't work.", "error")
        self._load()

    # ------------------------------------------------------------------ bulk actions
    def _bulk_do(self, changes, msg):
        r = state.call("bulk_update", list(self.picked), changes)
        if r:
            if changes.get("delete"):
                self.picked = set()
            state.toast(msg.replace("#", str(r["count"])), "ok")
            self._load()

    @handle("bulk_status", "change")
    def bulk_status_change(self, **event_args):
        v = self.bulk_status.selected_value
        if v:
            self._bulk_do({"status": v}, "Moved # to " + px.label_of(px.STATUSES, v))

    @handle("bulk_tag", "click")
    def bulk_tag_click(self, **event_args):
        from ...Dialogs.TagAll import TagAll
        tag = alert(TagAll(count=len(self.picked)), buttons=[], role="app-dialog")
        if tag:
            self._bulk_do({"add_tag": tag}, "Tagged #")

    @handle("bulk_story", "click")
    def bulk_story_click(self, **event_args):
        r = state.call("create_story", None, list(self.picked))
        if r:
            self.picked = set()
            state.toast("Story drafted from " + state.plural(r["story"]["feedback_count"], "piece") + " of feedback", "ok")
            router.go("story", r["story"]["id"])

    @handle("bulk_delete", "click")
    def bulk_delete_click(self, **event_args):
        n = len(self.picked)
        if confirm("This can't be undone. Archiving keeps them out of the way instead.",
                   title="Delete %s of feedback?" % state.plural(n, "piece"), buttons=[("Cancel", False), ("Delete", True)],
                   role="app-dialog"):
            self._bulk_do({"delete": True}, "Deleted #")

    @handle("bulk_clear", "click")
    def bulk_clear_click(self, **event_args):
        self.picked = set()
        self._draw()
