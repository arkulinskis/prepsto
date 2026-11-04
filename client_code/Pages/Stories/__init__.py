from anvil import *

from ._anvil_designer import StoriesTemplate
from ... import px, router, state


class Stories(StoriesTemplate):
    """#stories: every user story on the member's links, filtered by status and link (both remembered). New story
    asks which link it's for. A card opens #story/<id>."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.status = state.store_get("stories.status", "") or ""
        self.board = state.store_get("stories.board", "") or ""
        self.boards = []
        state.heading(self.title, 1)
        self.status_panel.add_event_handler("x-pick", self._pick)
        self._load()

    def _load(self):
        d = state.call("list_stories", self.board or None, self.status or None)
        if d is None:
            return
        self.boards = d["boards"]
        total = sum(d["counts"].values())
        self.status_panel.items = [{"key": "", "label": "All", "count": total, "on": not self.status}] + \
            [{"key": k, "label": label, "count": d["counts"].get(k, 0), "on": self.status == k} for k, label in px.STORY_STATUSES]
        self.board_box.visible = len(self.boards) > 1
        self.board_box.items = [("All links", "")] + [(b["name"], b["id"]) for b in self.boards]
        self.board_box.selected_value = self.board if any(b["id"] == self.board for b in self.boards) else ""
        state.set_control_attr(self.board_box, "aria-label", "Link")
        self.stories_panel.items = d["stories"]
        self.empty.visible = not d["stories"]
        self.empty_title.text = "No stories " + ("here" if self.status else "yet")

    def _pick(self, key=None, **event_args):
        k = state.focus_key()
        self.status = key
        state.store_set("stories.status", key)
        self._load()
        state.refocus(self.status_panel, k)

    @handle("board_box", "change")
    def board_box_change(self, **event_args):
        self.board = self.board_box.selected_value or ""
        state.store_set("stories.board", self.board)
        self._load()

    @handle("new_button", "click")
    def new_button_click(self, **event_args):
        if not self.boards:
            state.toast("Create a feedback link first.", "error")
            router.go("links")
            return
        from ...Dialogs.NewStory import NewStory
        story_id = alert(NewStory(boards=self.boards, selected=self.board), buttons=[], role="app-dialog")
        if story_id:
            router.go("story", story_id)
