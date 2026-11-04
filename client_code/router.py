"""Page addresses: #name/arg1/arg2 -> a page Form (open_form), with sign-in rules. The same addresses as the old
JavaScript version, so links people shared (panels, tracking pages, invites) keep working.

Links in templates are plain <a href="#inbox">; code calls router.go("story", id).

    PAGES[name] = (who may open it, browser-tab title)   who: None = anyone, "guest" = signed out only, "user", "admin"
    NAV = the main menu for members (header + phone tab bar): (page, label, icon). At most 4.
    The public panel (#f) and tracking page (#t) use the Bare layout (no header or footer): they carry the creator's colour.
New page: add it to PAGES, to _form() and (if it belongs in the menu) to NAV.
"""
import anvil
import anvil.js
from anvil.js import window

from . import px, state

PAGES = {
    "landing": (None, "Customer feedback to user stories"),
    "f": (None, "Feedback"),
    "t": (None, "Track your feedback"),
    "join": (None, "Join a team"),
    "auth": ("guest", "Sign in"),
    "home": ("user", "Overview"),
    "inbox": ("user", "Inbox"),
    "stories": ("user", "Stories"),
    "story": ("user", "Story"),
    "links": ("user", "Links"),
    "claude": ("user", "Claude & API"),
    "profile": ("user", "Your profile"),
    "admin": ("admin", "Admin"),
}
NAV = [("home", "Overview", "grid"), ("inbox", "Inbox", "inbox"), ("stories", "Stories", "story"), ("links", "Links", "link")]
APP_NAME = "Prepsto"
_r: dict = {"after": "", "listening": False, "page": None}


def _form(name):
    """The page's Form class (imported when first needed, so start-up stays quick)."""
    if name == "landing":
        from .Pages.Landing import Landing
        return Landing
    if name == "f":
        from .Pages.Panel import Panel
        return Panel
    if name == "t":
        from .Pages.Track import Track
        return Track
    if name == "join":
        from .Pages.Join import Join
        return Join
    if name == "auth":
        from .Pages.Auth import Auth
        return Auth
    if name == "home":
        from .Pages.Home import Home
        return Home
    if name == "inbox":
        from .Pages.Inbox import Inbox
        return Inbox
    if name == "stories":
        from .Pages.Stories import Stories
        return Stories
    if name == "story":
        from .Pages.Story import Story
        return Story
    if name == "links":
        from .Pages.Links import Links
        return Links
    if name == "claude":
        from .Pages.Claude import Claude
        return Claude
    if name == "profile":
        from .Pages.Profile import Profile
        return Profile
    from .Pages.Admin import Admin
    return Admin


def parse(hash_text):
    h = (hash_text or "").lstrip("#").lstrip("!").lstrip("/").split("?")[0]
    parts = [window.decodeURIComponent(p) for p in h.split("/") if p]
    return (parts[0] if parts else ""), parts[1:]


def href(name, *args):
    """'#name/arg1/arg2' with every part URL-encoded (row ids contain brackets and commas)."""
    return "#" + "/".join([name] + [window.encodeURIComponent(str(a)) for a in args if a not in (None, "")])


def home_page():
    return "home" if state.me() else "landing"


def show():
    """Open the page for the current address."""
    name, args = parse(window.location.hash)
    if name not in PAGES:
        name, args = home_page(), []
    who = PAGES[name][0]
    if who == "guest" and state.me():
        name, args = "home", []
    elif who in ("user", "admin") and not state.me():
        _r["after"] = window.location.hash
        name, args = "auth", []
    elif who == "admin" and not state.is_admin():
        state.toast("That page is for admins only.", "error")
        name, args = "home", []
    drawer = px.DIALOG["form"]
    if drawer is not None:  # a drawer left open over the old page
        px.DIALOG["form"] = None
        drawer.raise_event("x-close-alert", value=None)
    old = _r["page"]
    if old is not None and hasattr(old, "leaving"):
        old.leaving()  # the story editor saves what's still unsaved
    window.document.title = PAGES[name][1] + " · " + APP_NAME
    window.UI_READY = False
    page = _form(name)(args=args)
    _r["page"] = page
    anvil.open_form(page)
    shell = getattr(page, "layout", None)
    if shell is not None and hasattr(shell, "refresh"):
        shell.refresh(name)  # Anvil reuses the layout between pages: tell it who is signed in and which page is open
    window.scrollTo(0, 0)
    if hasattr(page, "opened"):
        page.opened()  # things that need the page on screen first (open a drawer, focus a field)
    window.UI_READY = True  # tests and screenshots wait for this


def go(name, *args):
    """Go to a page. Same address again = reload the page."""
    target = href(name, *args)
    if window.location.hash == target:
        show()
    else:
        window.location.hash = target


def replace(name, *args):
    """Change the address without opening anything (a page that switches its own view)."""
    window.history.replaceState(None, "", href(name, *args))


def after_sign_in():
    """Where to go once someone signs in: the page they were heading for, or home."""
    target = _r["after"]
    _r["after"] = ""
    if target and target != window.location.hash:
        window.location.hash = target
    else:
        go("home")


def remember_after(target):
    _r["after"] = target


def _on_hash(event):
    show()


def start():
    if not _r["listening"]:
        window.addEventListener("hashchange", anvil.js.report_exceptions(_on_hash))
        _r["listening"] = True
    show()
