from anvil import *

from ._anvil_designer import ExportTemplate
from ... import exports, state

TYPES = {"json": "application/json", "csv": "text/csv"}


class Export(ExportTemplate):
    """The story's Export dialog: Markdown, plain text, Gherkin, Jira, CSV, AI-ready JSON (client_code/exports.py),
    copy or download. The chosen format is remembered."""

    def __init__(self, story=None, bundle=None, fmt=None, **properties):
        super().__init__(**properties)
        self.story, self.bundle = story, bundle
        self.fmt = fmt or state.store_get("export.fmt", "markdown")
        self.formats_panel.add_event_handler("x-pick", self._pick)
        self._show()

    def _show(self):
        self.formats_panel.items = [{"key": k, "label": label, "on": k == self.fmt} for k, label, ext in exports.FORMATS]
        self._text = exports.render(self.fmt, self.story, self.bundle)
        self.out.text = self._text

    def _pick(self, key=None, **event_args):
        k = state.focus_key()
        self.fmt = key
        state.store_set("export.fmt", key)
        self._show()
        state.refocus(self.formats_panel, k)

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        label = [lbl for k, lbl, ext in exports.FORMATS if k == self.fmt][0]
        state.copy(self._text, label + " copied")

    @handle("download_button", "click")
    def download_button_click(self, **event_args):
        state.download(exports.file_name(self.story, self.fmt), self._text, TYPES.get(self.fmt, "text/plain"))

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)
