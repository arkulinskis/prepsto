"""Team workspaces: each feedback link (board) has its owner plus invited members, and notifications.

- The owner invites by email. The invite shows up for anyone signed in with that email (Overview -> Invitations,
  and a bell notification if they already have an account), and the owner can also copy an invite link
  (#join/<token>) and send it themselves: Prepsto sends no email. Whoever opens the link signed in can join
  (the token is the secret), then the invite is bound to their account.
- Members can do everything with the link's feedback and stories (triage, assign, comment, stories, exports).
  Only the owner changes the link's settings, its team, its code, or deletes it.
- Notifications: mention (in a comment), assign (feedback assigned to you), invite, joined (someone accepted your invite).
Teammates see each other's names; only the owner sees members' email addresses (they typed them).
"""
import random
import re

import anvil.server
from anvil.tables import app_tables
import anvil.tables as tables

from . import common as C
from . import Boards

MAX_MEMBERS = 20
TOKEN_CHARS = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _token():
    return "".join(random.choice(TOKEN_CHARS) for _ in range(24))


def team_users(b):
    """The owner and the active members of a board (user rows)."""
    out = [b["owner"]] if b["owner"] is not None else []
    for m in app_tables.members.search(board=b, status="active"):
        if m["user"] is not None and m["user"] not in out:
            out.append(m["user"])
    return out


def team_list(b):
    """Light list for mentions and the assignee picker: [{id, name, initials}]."""
    return [{"id": u.get_id(), "name": C.name_of(u)} for u in team_users(b)]


def notify(user, actor, kind, board, entry=None, story=None, text=""):
    if user is None or user == actor:
        return
    app_tables.notifications.add_row(user=user, actor=actor, kind=kind, board=board, entry=entry, story=story,
                                     text=C.text(text, 160), read=False, created=C.now(),
                                     is_demo=bool(board is not None and board["is_demo"]))


def _member_dict(m, show_email):
    u = m["user"]
    d = {"id": m.get_id(), "user_id": u.get_id() if u is not None else None,
         "name": C.name_of(u) if u is not None else (m["email"] or "").split("@")[0],
         "role": "member", "status": m["status"], "joined": C.iso(m["joined"]), "created": C.iso(m["created"])}
    if show_email:
        d["email"] = m["email"] or (u["email"] if u is not None else "")
        if m["status"] == "invited":
            d["token"] = m["token"]
    return d


def my_invites(me):
    email = (me["email"] or "").lower()
    out = []
    for m in app_tables.members.search(email=email, status="invited"):
        b = m["board"]
        if b is None or b["owner"] == me:
            continue
        out.append({"token": m["token"], "board": b["name"], "from": C.name_of(m["invited_by"]), "created": C.iso(m["created"])})
    return out


# ------------------------------------------------------------------------------------------- the team of a link
@anvil.server.callable(require_user=True)
def list_team(board_id):
    me = C.require_user()
    b = Boards.team_board(board_id, me)
    if b is None:
        return C.fail("That link doesn't exist, or you're not on its team.")
    is_owner = b["owner"] == me
    owner = b["owner"]
    people = [{"id": None, "user_id": owner.get_id(), "name": C.name_of(owner), "role": "owner", "status": "active",
               "email": owner["email"] if is_owner else None, "joined": C.iso(b["created"])}]
    rows = app_tables.members.search(tables.order_by("created"), board=b)
    people += [_member_dict(m, is_owner or m["user"] == me) for m in rows if is_owner or m["status"] == "active"]
    for p in people:
        p["me"] = p["user_id"] == me.get_id()
    return C.ok(people=people, is_owner=is_owner, board=b["name"])


@anvil.server.callable(require_user=True)
def invite_member(board_id, email):
    me = C.require_user()
    b = Boards.owned_board(board_id, me)
    if b is None:
        return C.fail("Only the owner of a link can invite people.")
    email = C.text(email, 120).replace(" ", "").lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return C.fail("That email address doesn't look right.")
    if email == (me["email"] or "").lower():
        return C.fail("You're already the owner of this link.")
    rows = list(app_tables.members.search(board=b))
    if any((m["email"] or "") == email or (m["user"] is not None and (m["user"]["email"] or "").lower() == email) for m in rows):
        return C.fail("That person is already invited or on the team.")
    if len(rows) >= MAX_MEMBERS:
        return C.fail("A link can have up to %d teammates." % MAX_MEMBERS)
    if C.rate_limited("invite", 30, 3600):
        return C.fail("That's a lot of invitations in one hour. Please try again later.")
    m = app_tables.members.add_row(board=b, user=None, email=email, role="member", status="invited", token=_token(),
                                   invited_by=me, created=C.now(), joined=None, is_demo=False)
    existing = app_tables.users.get(email=email)
    if existing is not None:
        notify(existing, me, "invite", b, text="invited you to the team of %s" % b["name"])
    return C.ok(member=_member_dict(m, True))


@anvil.server.callable(require_user=True)
def remove_member(board_id, member_id):
    """The owner removes anyone (or cancels an invite); a member can remove themselves (leave)."""
    me = C.require_user()
    b = C.row_by_id(app_tables.boards, board_id)
    m = C.row_by_id(app_tables.members, member_id)
    if b is None or m is None or m["board"] != b:
        return C.fail("That teammate isn't on this link.")
    if b["owner"] != me and m["user"] != me:
        return C.fail("Only the owner can remove teammates.")
    u = m["user"]
    if u is not None:
        for e in app_tables.entries.search(board=b, assignee=u):
            e["assignee"] = None
    m.delete()
    return C.ok(left=u == me)


# ------------------------------------------------------------------------------------------- joining
def _invite(token):
    if not isinstance(token, str) or len(token) < 10:
        return None
    m = app_tables.members.get(token=token)
    return m if m is not None and m["board"] is not None else None


@anvil.server.callable
def get_invite(token):
    """Public: what the #join page shows before signing in. No email addresses."""
    m = _invite(token)
    if m is None or m["status"] != "invited":
        return C.fail("This invitation doesn't exist any more. Ask the link's owner for a new one.")
    me = C.me()
    return C.ok(board=m["board"]["name"], inviter=C.name_of(m["invited_by"]),
                is_owner=me is not None and m["board"]["owner"] == me,
                already=me is not None and Boards.role_in(m["board"], me) is not None)


@anvil.server.callable(require_user=True)
def accept_invite(token):
    me = C.require_user()
    m = _invite(token)
    if m is None or m["status"] != "invited":
        return C.fail("This invitation doesn't exist any more. Ask the link's owner for a new one.")
    b = m["board"]
    if Boards.role_in(b, me) is not None:
        return C.ok(board_id=b.get_id(), board=b["name"])
    m.update(user=me, email=(me["email"] or "").lower(), status="active", joined=C.now(), token=None)
    notify(b["owner"], me, "joined", b, text="joined the team of %s" % b["name"])
    return C.ok(board_id=b.get_id(), board=b["name"])


@anvil.server.callable(require_user=True)
def decline_invite(token):
    me = C.require_user()
    m = _invite(token)
    if m is None or m["status"] != "invited":
        return C.ok()
    if (m["email"] or "") != (me["email"] or "").lower():
        return C.fail("This invitation was sent to someone else.")
    m.delete()
    return C.ok()


# ------------------------------------------------------------------------------------------- notifications
def _notif(n, me):
    d = {"id": n.get_id(), "kind": n["kind"], "actor": C.name_of(n["actor"]) if n["actor"] is not None else "Someone",
         "text": n["text"] or "", "board": n["board"]["name"] if n["board"] is not None else "",
         "entry_id": n["entry"].get_id() if n["entry"] is not None else None,
         "story_id": n["story"].get_id() if n["story"] is not None else None,
         "read": bool(n["read"]), "created": C.iso(n["created"]), "token": None}
    if n["kind"] == "invite" and n["board"] is not None:
        inv = [m for m in app_tables.members.search(board=n["board"], status="invited") if (m["email"] or "") == (me["email"] or "").lower()]
        d["token"] = inv[0]["token"] if inv else None
    return d


@anvil.server.callable(require_user=True)
def get_notifications():
    me = C.require_user()
    rows = app_tables.notifications.search(tables.order_by("created", ascending=False), user=me)
    items = []
    for n in rows[:40]:
        b = n["board"]
        if b is not None and n["kind"] != "invite" and Boards.role_in(b, me) is None:
            continue  # no longer on that team
        items.append(_notif(n, me))
    return {"items": items[:30], "unread": len([i for i in items if not i["read"]])}


@anvil.server.callable(require_user=True)
def mark_notifications_read(ids=None):
    me = C.require_user()
    for n in app_tables.notifications.search(user=me, read=False):
        if ids is None or n.get_id() in (ids if isinstance(ids, list) else []):
            n["read"] = True
    return C.ok()
