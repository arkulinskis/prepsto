"""API keys: let a member's own tools (Claude Code through the prepsto CLI / MCP server, or any script) read and work
their tickets through the HTTP API in ApiRoutes.py.

Security model:
  - A key is "psk_" + 40 random letters and digits (about 238 bits) from the operating system's secure random source.
    Prepsto stores only its SHA-256 fingerprint and its first 12 characters (to recognise it in lists); the full key
    is shown once, when it's made. A lost key can't be shown again: revoke it and make a new one.
  - A key acts as the member who made it, with that member's permissions at the moment of each request (Boards.role_in):
    leaving or being removed from a team, or a disabled account, cuts the key off straight away.
  - Each key is limited by what it may do (scopes: read; write = status, priority, tags, assignee, team comments,
    stories; reply = public replies the sender sees), by which links it sees (all, or a chosen few), by an expiry date,
    and by a rate limit (RATE per WINDOW seconds). It never returns senders' email addresses or tracking links.
  - Every request is logged (time, key, action, answer code); members see the last ones on the Claude & API page.
"""
import datetime as dt
import hashlib
import random

import anvil.server
from anvil.tables import app_tables
import anvil.tables as tables

from . import common as C
from . import Boards

PREFIX = "psk_"
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
SCOPES = ("read", "write", "reply")
MAX_KEYS = 10                  # active keys per member
EXPIRY_DAYS = (30, 90, 365, 0)  # 0 = never
RATE, WINDOW = 600, 600        # requests per key per 10 minutes
LOG_KEEP = 200                 # log rows kept per key
_rng = random.SystemRandom()


def fingerprint(key):
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def new_key():
    return PREFIX + "".join(_rng.choice(ALPHABET) for _ in range(40))


def key_state(k, now=None):
    now = now or C.now()
    if k["revoked"] is not None:
        return "revoked"
    if k["expires"] is not None and k["expires"] <= now:
        return "expired"
    return "active"


def key_dict(k):
    ids = list(k["boards"] or [])
    names = []
    for i in ids:
        b = C.row_by_id(app_tables.boards, i)
        if b is not None:
            names.append(b["name"])
    return {"id": k.get_id(), "name": k["name"], "prefix": k["prefix"], "scopes": list(k["scopes"] or ["read"]),
            "links": ids, "link_names": names, "created": C.iso(k["created"]), "expires": C.iso(k["expires"]),
            "last_used": C.iso(k["last_used"]), "uses": int(k["uses"] or 0), "state": key_state(k),
            "revoked": C.iso(k["revoked"])}


def _clean_scopes(scopes):
    picked = [s for s in (scopes if isinstance(scopes, list) else []) if s in SCOPES]
    if "reply" in picked and "write" not in picked:
        picked.append("write")  # replying moves New feedback to Reviewing, which is an update
    return [s for s in SCOPES if s == "read" or s in picked]


# ------------------------------------------------------------------------------------------- the Claude & API page
@anvil.server.callable(require_user=True)
def list_api_keys():
    me = C.require_user()
    keys = list(app_tables.api_keys.search(tables.order_by("created", ascending=False), user=me))
    log = []
    for r in app_tables.api_log.search(tables.order_by("created", ascending=False), user=me)[:30]:
        log.append({"created": C.iso(r["created"]), "key": r["key"]["name"] if r["key"] is not None else "(deleted key)",
                    "action": r["action"] or "", "status": int(r["status"] or 0)})
    return {"keys": [key_dict(k) for k in keys], "log": log,
            "links": [{"id": b.get_id(), "name": b["name"], "role": Boards.role_in(b, me)} for b in Boards.my_boards(me)],
            "limits": {"max_keys": MAX_KEYS, "rate": RATE, "window": WINDOW}}


@anvil.server.callable(require_user=True)
def create_api_key(name, scopes=None, link_ids=None, days=90):
    """Make a key. The reply is the only time the full key is ever shown."""
    me = C.require_user()
    name = C.text(name, 60)
    if len(name) < 2:
        return C.fail("Give the key a name you'll recognise, like \"Claude on my laptop\".")
    now = C.now()
    active = [k for k in app_tables.api_keys.search(user=me) if key_state(k, now) == "active"]
    if len(active) >= MAX_KEYS:
        return C.fail("You already have %d active keys. Revoke one you don't use first." % MAX_KEYS)
    if C.rate_limited("api_key", 20, 3600):
        return C.fail("That's a lot of new keys in one hour. Please try again later.")
    mine = {b.get_id(): b for b in Boards.my_boards(me)}
    ids = []
    for i in (link_ids if isinstance(link_ids, list) else [])[:60]:
        if i not in mine:
            return C.fail("You can only give a key access to links you're on.")
        if i not in ids:
            ids.append(i)
    days = days if days in EXPIRY_DAYS else 90
    key = new_key()
    row = app_tables.api_keys.add_row(user=me, name=name, prefix=key[:12], hash=fingerprint(key), scopes=_clean_scopes(scopes),
                                      boards=ids, created=now, expires=(now + dt.timedelta(days=days)) if days else None,
                                      revoked=None, last_used=None, uses=0, window_start=None, window_count=0)
    return C.ok(key=key, api_key=key_dict(row))


@anvil.server.callable(require_user=True)
def revoke_api_key(key_id):
    me = C.require_user()
    k = C.row_by_id(app_tables.api_keys, key_id)
    if k is None or k["user"] != me:
        return C.fail("That key doesn't exist (any more).")
    if k["revoked"] is None:
        k["revoked"] = C.now()
    return C.ok(api_key=key_dict(k))


# ------------------------------------------------------------------------------------------- used by ApiRoutes
def authenticate(token):
    """(key row, user row, None) for a working key, or (None, None, (status, message))."""
    token = (token or "").strip()
    if not token.startswith(PREFIX) or len(token) != len(PREFIX) + 40:
        return None, None, (401, "Send your Prepsto API key as 'Authorization: Bearer psk_...'. Make one on the Claude & API page.")
    k = app_tables.api_keys.get(hash=fingerprint(token))
    if k is None:
        return None, None, (401, "That API key isn't valid. Check it, or make a new one on the Claude & API page.")
    now = C.now()
    st = key_state(k, now)
    if st != "active":
        return None, None, (401, "This API key was revoked." if st == "revoked" else "This API key has expired. Make a new one.")
    u = k["user"]
    if u is None or u["enabled"] is False:
        return None, None, (403, "The account this key belongs to is disabled.")
    start, count = k["window_start"], int(k["window_count"] or 0)
    if start is None or (now - start).total_seconds() >= WINDOW:
        start, count = now, 0
    if count >= RATE:
        return None, None, (429, "Too many requests with this key. Wait a few minutes and try again.")
    k.update(window_start=start, window_count=count + 1, last_used=now, uses=int(k["uses"] or 0) + 1)
    return k, u, None


def allowed_boards(k, u):
    """The links a key may see: the owner's links (owned + teams), narrowed to the key's list if it has one."""
    boards = Boards.my_boards(u)
    ids = list(k["boards"] or [])
    return [b for b in boards if not ids or b.get_id() in ids]


def has_scope(k, scope):
    return scope in (k["scopes"] or ["read"])


def log(k, u, method, action, status):
    try:
        app_tables.api_log.add_row(key=k, user=u, created=C.now(), method=method, action=C.text(action, 200), status=int(status))
        rows = app_tables.api_log.search(tables.order_by("created", ascending=False), key=k)
        if len(rows) > LOG_KEEP + 20:
            for r in list(rows)[LOG_KEEP:]:
                r.delete()
    except Exception as ex:  # the log must never break a request
        print("api log failed:", ex)
