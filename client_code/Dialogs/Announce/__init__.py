from anvil import *
import anvil.server
from anvil.js import window

from ._anvil_designer import AnnounceTemplate
from ... import state

MAILTO_LIMIT = 1800  # longer mailto: links get cut off by some mail apps and browsers


def default_text(title, status):
    t = title or "this"
    if status == "shipped":
        return "Good news: '%s' is live. Thanks for asking for it." % t
    if status == "in_progress":
        return "We've started building '%s'. Thanks for asking for it: we'll post here again when it's live." % t
    if status == "ready":
        return "'%s' is planned. Thanks for asking for it: we'll post here when work starts." % t
    return "Thanks for asking for '%s'. We're looking into it and will post updates here." % t


class Announce(AnnounceTemplate):
    """Story editor -> "Update everyone who asked (N)": one message on the tracking page of every piece of feedback linked
    to the story (Stories.announce_story), pre-filled from the status. Afterwards: how many pages it reached, and the
    addresses people left, to copy or open as BCC in the creator's own mail app. Closes with True once posted."""

    def __init__(self, story=None, tracking=True, **properties):
        super().__init__(**properties)
        self.story: dict = dict(story or {})
        self.tracking, self.emails, self.posted = bool(tracking), [], False
        entries = self.story.get("entries") or []
        mails = set((e.get("email") or "").strip().lower() for e in entries if e.get("email"))
        self.reach.text = "Goes to the %s linked to “%s”%s." % (
            state.plural(len(entries), "person who asked", "people who asked"), self.story.get("title") or "",
            (" · %d left an email" % len(mails)) if mails else "")
        self.message_box.text = default_text(self.story.get("title"), self.story.get("status"))
        state.set_control_attr(self.message_box, "maxlength", "2000")
        self.off_note.visible = not self.tracking
        self.off_note.text = ("Tracking is off for this link, so there are no tracking pages to post to. You can still copy "
                              "the email addresses people left.")
        self.send_button.text = "Post the update" if self.tracking else "Get the email addresses"
        self.done_part.visible = False

    @handle("send_button", "click")
    def send_button_click(self, **event_args):
        self.error.visible = False
        text = (self.message_box.text or "").strip()
        if len(text) < 2:
            self.error.text, self.error.visible = "Write the update first.", True
            return
        self.send_button.enabled = False
        try:
            r = anvil.server.call("announce_story", self.story.get("id"), text)
        finally:
            self.send_button.enabled = True
        if not r.get("ok"):
            self.error.text, self.error.visible = r.get("error") or "That didn't work.", True
            return
        self.posted, self.emails = bool(r.get("posted")), list(r.get("emails") or [])
        n = len(self.emails)
        if r.get("tracking_off"):
            head = "Nothing posted: tracking is off for this link"
        else:
            head = "Posted to " + state.plural(r.get("posted") or 0, "tracking page")
        self.result.text = head + " · " + (state.plural(n, "person", "people") + " left an email" if n else "nobody left an email")
        self.email_note.text = ("Prepsto doesn't send email. Paste the addresses into BCC so nobody sees the others."
                                if n else "Everyone who asked will see it next time they open their tracking link.")
        self.copy_button.visible = bool(n)
        bcc = ",".join(self.emails)
        mailto = "mailto:?bcc=" + window.encodeURIComponent(bcc) + "&subject=" + window.encodeURIComponent(self.story.get("title") or "") + \
            "&body=" + window.encodeURIComponent(text)
        self.mail_link.visible = bool(n) and len(mailto) < MAILTO_LIMIT
        if self.mail_link.visible:
            state.set_attr(self.mail_link, "href", mailto)
        self.write_part.visible, self.done_part.visible = False, True
        state.focus(self.close_button)

    @handle("copy_button", "click")
    def copy_button_click(self, **event_args):
        state.copy(", ".join(self.emails), state.plural(len(self.emails), "email address", "email addresses") + " copied")

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=None)

    @handle("close_button", "click")
    def close_button_click(self, **event_args):
        self.raise_event("x-close-alert", value=self.posted)
