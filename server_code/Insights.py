"""Insights: reads feedback and suggests structure. Today a small rules engine; ready for AI.

Everything the rest of the app knows about "understanding text" goes through four functions:

    analyze(message, kind, rating)      -> dict stored in entries.ai (sentiment, urgency, tags, summary, theme)
    draft_story(entries, board_name)    -> dict {title, persona, goal, benefit, acceptance, notes}
    similar(entry_row, rows, limit)     -> the rows that talk about the same thing
    ai_bundle(story, entries, comments) -> the JSON a language model gets (also offered as an export)

To plug in AI later: write `_ai_analyze` / `_ai_draft` (e.g. a Claude call with the prompt in ai_bundle),
set PROVIDER = "ai" (or read it from App Secrets), and keep the same return shapes. Every result carries
"provider" and "version", so old rule-based results can be found and re-run (reanalyze_board in Inbox.py).
"""
import re

PROVIDER = "rules"     # "rules" now; "ai" once a model is wired in (see the module doc)
VERSION = 1

TAGS = {
    "performance": ["slow", "lag", "laggy", "loading", "loads", "speed", "fast", "freeze", "freezes", "spinner", "timeout", "wait"],
    "mobile": ["phone", "mobile", "iphone", "android", "ios", "tablet", "ipad", "app store", "small screen"],
    "design": ["design", "layout", "colour", "color", "font", "dark mode", "button", "icon", "ugly", "beautiful", "contrast", "looks"],
    "onboarding": ["sign up", "signup", "onboarding", "tutorial", "getting started", "first time", "confusing", "welcome"],
    "account": ["login", "log in", "password", "account", "sign in", "email", "profile", "2fa"],
    "billing": ["price", "pricing", "pay", "payment", "invoice", "billing", "subscription", "plan", "refund", "expensive", "cost"],
    "search": ["search", "filter", "find", "sort"],
    "export": ["export", "csv", "pdf", "download", "print", "backup"],
    "integrations": ["integration", "slack", "zapier", "api", "webhook", "google", "calendar", "sync", "notion", "jira"],
    "notifications": ["notification", "notify", "reminder", "email me", "alert", "push"],
    "accessibility": ["accessibility", "screen reader", "keyboard", "font size", "colour blind", "color blind", "a11y"],
    "data loss": ["lost", "deleted", "disappeared", "gone", "missing", "overwrote", "wiped"],
    "collaboration": ["share", "sharing", "team", "invite", "collaborat", "together", "comment"],
}
POSITIVE = ["love", "great", "awesome", "amazing", "thank", "thanks", "nice", "helpful", "easy", "perfect", "brilliant",
            "excellent", "fantastic", "good", "wonderful", "smooth", "clean", "beautiful", "fan", "enjoy"]
NEGATIVE = ["bug", "broken", "crash", "crashes", "error", "fail", "fails", "slow", "hate", "annoying", "confusing", "bad",
            "terrible", "worst", "can't", "cannot", "won't", "doesn't", "didn't", "frustrat", "stuck", "lost", "useless",
            "impossible", "missing", "wrong", "ugly", "problem", "issue"]
URGENT = ["crash", "crashes", "lost", "data", "can't log", "cannot log", "can't sign", "payment", "charged", "security",
          "urgent", "asap", "blocked", "blocking", "down", "500", "deleted", "wiped", "every time"]
STOP = set("""a an the and or but if then so to of in on at for with from by is are was were be been it its this that these those
i me my we our you your they them their he she his her not no yes do does did have has had can could would should will just
very really also there here what when where which who how why all any some more most other into out up down about than too
please app thing things get got make like want would its i'm it's dont don't im""".split())

KIND_PERSONA = {"bug": "user who hit a problem", "idea": "regular user", "question": "new user", "praise": "happy user",
                "other": "user"}


def _words(text):
    return [w for w in re.findall(r"[a-z0-9']+", (text or "").lower()) if len(w) > 2 and w not in STOP]


def _has(text, needle):
    return needle in text


def analyze(message, kind="other", rating=None):
    """Read one message. Returns a JSON-friendly dict (stored in entries.ai)."""
    if PROVIDER == "ai":
        return _ai_analyze(message, kind, rating)
    low = " " + (message or "").lower() + " "
    pos = sum(low.count(w) for w in POSITIVE)
    neg = sum(low.count(w) for w in NEGATIVE)
    if kind == "praise":
        pos += 2
    if kind == "bug":
        neg += 1
    if isinstance(rating, (int, float)) and rating:
        pos += max(0, rating - 3) * 1.5
        neg += max(0, 3 - rating) * 1.5
    score = 0.0 if pos + neg == 0 else round((pos - neg) / float(pos + neg), 2)
    sentiment = "positive" if score > 0.2 else "negative" if score < -0.2 else "neutral"
    tags = [t for t, keys in TAGS.items() if any(_has(low, k) for k in keys)][:4]
    hits = sum(1 for u in URGENT if u in low)
    urgency = "high" if hits >= 2 or (kind == "bug" and hits >= 1) else "medium" if hits == 1 or kind == "bug" else "low"
    first = re.split(r"(?<=[.!?])\s+", (message or "").strip())[0]
    summary = first if len(first) <= 110 else first[:107].rsplit(" ", 1)[0] + "..."
    counts = {}
    for w in _words(message):
        counts[w] = counts.get(w, 0) + 1
    keywords = [w for w, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))][:6]
    return {"provider": PROVIDER, "version": VERSION, "sentiment": sentiment, "score": score, "urgency": urgency,
            "tags": tags, "summary": summary, "keywords": keywords, "theme": tags[0] if tags else (keywords[0] if keywords else "")}


def _similarity(a, b):
    wa, wb = set(_words(a)), set(_words(b))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / float(len(wa | wb))


def similar(entry, rows, limit=4):
    """Other entries that seem to talk about the same thing (shared words and tags)."""
    out = []
    my_tags = set((entry["ai"] or {}).get("tags") or [])
    for r in rows:
        if r == entry:
            continue
        s = _similarity(entry["message"], r["message"])
        s += 0.12 * len(my_tags & set((r["ai"] or {}).get("tags") or []))
        if s >= 0.18:
            out.append((s, r))
    out.sort(key=lambda x: -x[0])
    return [(round(min(s, 1.0), 2), r) for s, r in out[:limit]]


def _cap(s):
    s = (s or "").strip().rstrip(".!?")
    return s[:1].upper() + s[1:] if s else s


def draft_story(entries, board_name=""):
    """A first draft of a user story from a few pieces of feedback. entries: list of dicts
    {kind, message, rating, ai}. Returns {title, persona, goal, benefit, acceptance, notes, source}."""
    if PROVIDER == "ai":
        return _ai_draft(entries, board_name)
    if not entries:
        return {"title": "New story", "persona": "user", "goal": "", "benefit": "", "acceptance": [], "notes": "",
                "source": "manual"}
    tags, kinds = {}, {}
    for e in entries:
        for t in (e.get("ai") or {}).get("tags") or []:
            tags[t] = tags.get(t, 0) + 1
        kinds[e.get("kind") or "other"] = kinds.get(e.get("kind") or "other", 0) + 1
    theme = max(tags, key=tags.get) if tags else ""
    kind = max(kinds, key=kinds.get)
    lead = entries[0]
    summary = (lead.get("ai") or {}).get("summary") or lead.get("message", "")[:100]
    persona = KIND_PERSONA.get(kind, "user")
    if theme == "mobile":
        persona = "user on my phone"
    elif theme == "billing":
        persona = "paying customer"
    elif theme == "onboarding":
        persona = "new user"
    elif theme == "collaboration":
        persona = "team member"
    if kind == "bug":
        goal = "%s to work reliably" % (theme or "this part of the app")
        benefit = "I can finish what I came to do without workarounds"
        title = "Fix: %s" % _cap(summary)[:80]
        acceptance = ["The problem described in the linked feedback can no longer be reproduced",
                      "An error message explains what happened if something still goes wrong",
                      "A regression test covers this case"]
    elif kind == "question":
        goal = "to understand %s without asking for help" % (theme or "how this works")
        benefit = "I can get going on my own"
        title = "Clarify: %s" % _cap(summary)[:80]
        acceptance = ["The answer is visible where the question comes up (hint, empty state or help link)",
                      "Support can link to one clear page for this question"]
    else:
        goal = _cap(summary)[:140]
        goal = goal[:1].lower() + goal[1:]
        benefit = "I get more value from %s" % (board_name or "the product")
        title = _cap(summary)[:80]
        acceptance = ["Given the situation in the linked feedback, when I use the new feature, then it works as described",
                      "It works on phone and desktop", "The change is announced to the people who asked for it"]
    if theme == "performance":
        acceptance.insert(0, "The affected screen loads in under 2 seconds on a typical connection")
    if theme == "accessibility":
        acceptance.insert(0, "Works with a keyboard only and with a screen reader")
    if theme == "export":
        acceptance.insert(0, "The export opens correctly in the tools customers mentioned")
    n = len(entries)
    notes = "Drafted from %d piece%s of feedback%s. Edit freely." % (n, "" if n == 1 else "s", (" about %s" % theme) if theme else "")
    return {"title": title, "persona": persona, "goal": goal, "benefit": benefit, "acceptance": acceptance[:5],
            "notes": notes, "source": PROVIDER}


def ai_bundle(story, entries, comments):
    """Everything a language model needs to refine one story, as one JSON-friendly dict (also an export format)."""
    return {
        "schema": "prepsto.story/v1",
        "task": ("Refine this user story. Keep the persona, goal and benefit grounded in the client feedback. "
                 "Return JSON with: title, persona, goal, benefit, acceptance (list of testable criteria), notes."),
        "story": story,
        "client_feedback": entries,
        "supporting_comments": comments,
        "analysis_provider": PROVIDER,
    }


def _ai_analyze(message, kind, rating):  # pragma: no cover - the AI hook
    raise NotImplementedError("Wire a model in here and keep analyze()'s return shape.")


def _ai_draft(entries, board_name):  # pragma: no cover - the AI hook
    raise NotImplementedError("Wire a model in here and keep draft_story()'s return shape.")
