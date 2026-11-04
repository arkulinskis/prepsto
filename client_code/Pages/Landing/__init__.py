from anvil import *
import anvil.js
from anvil.js import window

from ._anvil_designer import LandingTemplate
from ... import state


class Landing(LandingTemplate):
    """#landing: what visitors see first (and "About" for members). All static copy in the template; the hero is a
    CSS-only loop (the panel on a site, the inbox that sorts itself, the story it becomes). Members see "Open your
    dashboard" instead of the sign-up buttons. The video cover turns into YouTube's player only when pressed."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        me = bool(state.me())
        self.guest_cta.visible, self.member_cta.visible = not me, me
        self.band_guest.visible, self.band_member.visible = not me, me

    def play_click(self, event):
        window.PX.playVideo(self.dom_nodes["yt_cover"])
