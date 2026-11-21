from anvil import *
import anvil.server

from ._anvil_designer import RoadmapCardTemplate
from ... import px, state


class RoadmapCard(RoadmapCardTemplate):
    """One story on the public roadmap (Roadmap.card: id, title, note, status, asked, shipped) plus the page's keys:
    _slug, _ask_email, _open, _track (None = not +1'd in this browser, "" = +1'd without a tracking link).
    "+1" opens a short form (optional note, optional email when the link asks for one, a honeypot); sending raises the
    count, and the card then says "You +1'd this · Track it". Shipped cards show their date instead of +1."""

    def __init__(self, **properties):
        super().__init__(**properties)
        it = self.item
        self.title.text = it.get("title") or ""
        state.heading(self.title, 3)
        self.note.text = it.get("note") or ""
        self.note.visible = bool(it.get("note"))
        shipped = it.get("status") == "shipped"
        self.shipped.visible = shipped
        self.shipped.text = ("Shipped " + state.fmt_date(it.get("shipped"))) if shipped else ""
        self.email_part.visible = bool(it.get("_ask_email"))
        self.form_part.visible = False
        state.set_control_attr(self.note_box, "maxlength", "280")
        state.set_control_attr(self.email_box, "autocomplete", "email")
        state.set_control_attr(self.vote_button, "aria-label", "+1: I want “%s” too" % (it.get("title") or ""))
        hp = state.control(self.hp_box)
        hp.setAttribute("tabindex", "-1")
        hp.setAttribute("autocomplete", "off")
        hp.setAttribute("aria-label", "Website")
        self._draw()

    def _draw(self):
        it = self.item
        n = it.get("asked") or 0
        self.asked.text = "%d asked" % n
        state.set_attr(self.asked, "title", state.plural(n, "person has", "people have") + " asked for this")
        voted = it.get("_track") is not None
        can = it.get("status") != "shipped" and bool(it.get("_open"))
        self.vote_button.visible = can and not voted and not self.form_part.visible
        self.voted_part.visible = voted
        self.track_link.visible = bool(it.get("_track"))
        if it.get("_track"):
            state.set_attr(self.track_link, "href", px.track_link(it["_track"]))

    @handle("vote_button", "click")
    def vote_button_click(self, **event_args):
        self.form_part.visible = True
        self.error.visible = False
        self._draw()
        state.focus(self.note_box)

    @handle("cancel_button", "click")
    def cancel_button_click(self, **event_args):
        self.form_part.visible = False
        self._draw()
        state.focus(self.vote_button)

    @handle("note_box", "pressed_enter")
    def note_box_pressed_enter(self, **event_args):
        self.send_button_click()

    @handle("send_button", "click")
    def send_button_click(self, **event_args):
        it = self.item
        self.error.visible = False
        self.send_button.enabled = False
        try:
            r = anvil.server.call("roadmap_vote", it["_slug"], it["id"], self.note_box.text or "", self.email_box.text or "",
                                  self.hp_box.text or "")
        finally:
            self.send_button.enabled = True
        if not r.get("ok"):
            self.error.text, self.error.visible = r.get("error") or "That didn't work. Please try again.", True
            return
        it["asked"] = r.get("asked") or it.get("asked") or 0
        it["_track"] = r.get("track") or ""
        px.vote_add(it["_slug"], it["id"], r.get("track"))
        self.form_part.visible = False
        self._draw()
        state.toast("You've already +1'd this one" if r.get("already") else "Thanks! Your +1 is in.", "ok")
