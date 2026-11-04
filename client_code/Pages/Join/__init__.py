from anvil import *
import anvil.server

from ._anvil_designer import JoinTemplate
from ... import router, state


class Join(JoinTemplate):
    """#join/<token>: an invite link to a feedback link's team (server_code/Team.py).
    Signed out: who invited you to what, then sign up or sign in (and come back here).
    Signed in: Join (accept_invite) or Not now. Anyone signed in who holds the link can join; the token is the secret."""

    def __init__(self, args=(), **properties):
        super().__init__(**properties)
        self.token = args[0] if args else ""
        me = state.me()
        r = anvil.server.call("get_invite", self.token)
        self.missing.visible = not r.get("ok")
        self.card.visible = bool(r.get("ok"))
        if not r.get("ok"):
            self.missing_text.text = r.get("error") or ""
            return
        self.avatar.text = state.initials(r.get("inviter"))
        self.inviter.text = r.get("inviter") or ""
        self.board.text = r.get("board") or ""
        owner, already = bool(r.get("is_owner")), bool(r.get("already"))
        self.owner_part.visible = owner
        self.already_part.visible = already and not owner
        self.member_part.visible = bool(me) and not owner and not already
        self.guest_part.visible = not me and not owner and not already
        if me:
            self.signed_in_as.text = "Signed in as " + (me.get("email") or "")

    def _auth(self, *where):
        router.remember_after(router.href("join", self.token))
        router.go(*where)

    @handle("sign_in_button", "click")
    def sign_in_button_click(self, **event_args):
        self._auth("auth")

    @handle("sign_up_button", "click")
    def sign_up_button_click(self, **event_args):
        self._auth("auth", "signup")

    @handle("no_button", "click")
    def no_button_click(self, **event_args):
        router.go("home")

    @handle("yes_button", "click")
    def yes_button_click(self, **event_args):
        r = state.call("accept_invite", self.token)
        if r:
            state.toast("Welcome to the team of " + r["board"], "ok")
            router.go("inbox")
