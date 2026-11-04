"""Story exports: Markdown, plain text, Gherkin, Jira markup, CSV and the AI-ready JSON bundle.

Plain Python with no Anvil imports, so both sides use the same code: the story editor's Export dialog (browser) and
the API's GET /v1/stories/<id>?format=markdown (server_code/ApiRoutes.py imports it as `from . import exports`).
A story is the dict from Stories.story_dict(..., full=True); the bundle is Insights.ai_bundle's dict.
"""
import json
import re

STORY_STATUSES = {"draft": "Draft", "ready": "Ready", "in_progress": "In progress", "shipped": "Shipped"}
KIND_LABELS = {"bug": "Bug", "idea": "Idea", "praise": "Praise", "question": "Question", "other": "Other"}
FORMATS = [("markdown", "Markdown", "md"), ("text", "Plain text", "txt"), ("gherkin", "Gherkin", "feature"),
           ("jira", "Jira", "txt"), ("csv", "CSV", "csv"), ("json", "AI-ready JSON", "json")]


def _stars(n):
    n = int(n or 0)
    return "★" * n + "☆" * (5 - n) if n else ""


def _day(iso):
    return (iso or "")[:10]


def _who(e):
    if e.get("name"):
        return e["name"]
    return (e.get("email") or "").split("@")[0] if e.get("email") else "Anonymous"


def _kind(e):
    return e.get("kind_label") or KIND_LABELS.get(e.get("kind"), "Other")


def sentence(s):
    return "As a %s, I want %s%s." % (s.get("persona") or "…", s.get("goal") or "…",
                                      (", so that " + s["benefit"]) if s.get("benefit") else "")


def _meta(s):
    parts = [STORY_STATUSES.get(s.get("status"), s.get("status") or ""),
             ("priority " + s["priority"]) if s.get("priority") else "",
             ("%s pts" % s["points"]) if s.get("points") is not None else "", s.get("board") or ""]
    return [p for p in parts if p]


def _one_line(text):
    return (text or "").replace("\n", " ")


def markdown(s, bundle=None):
    L = ["# " + s["title"], "", "_" + " · ".join(_meta(s)) + "_", "", "## User story", "",
         "As a **%s**, I want **%s**%s." % (s.get("persona") or "…", s.get("goal") or "…",
                                           (", so that **%s**" % s["benefit"]) if s.get("benefit") else ""), ""]
    if s.get("acceptance"):
        L += ["## Acceptance criteria", "", "\n".join("- [ ] " + a for a in s["acceptance"]), ""]
    if s.get("notes"):
        L += ["## Notes", "", s["notes"], ""]
    if s.get("comments"):
        L += ["## Supporting comments", "",
              "\n".join("- **%s** (%s): %s" % (c["author"], _day(c.get("created")), _one_line(c["body"])) for c in s["comments"]), ""]
    entries = s.get("entries") or []
    if entries:
        L += ["## Client feedback (%d)" % len(entries), ""]
        for e in entries:
            meta = [x for x in (_who(e), _kind(e), _stars(e.get("rating")), _day(e.get("created")), e.get("page_url")) if x]
            L += ["> " + (e.get("message") or "").replace("\n", "\n> "), ">", "> — " + " · ".join(meta)]
            for c in e.get("comments") or []:
                L += ["", "  - _%s:_ %s" % (c["author"], _one_line(c["body"]))]
            L.append("")
    return "\n".join(L).strip() + "\n"


def text(s, bundle=None):
    L = [s["title"].upper(), " | ".join(_meta(s)), "", sentence(s), ""]
    if s.get("acceptance"):
        L += ["Acceptance criteria:", "\n".join("  %d. %s" % (i + 1, a) for i, a in enumerate(s["acceptance"])), ""]
    if s.get("notes"):
        L += ["Notes:", s["notes"], ""]
    if s.get("comments"):
        L += ["Supporting comments:", "\n".join("  - %s: %s" % (c["author"], c["body"]) for c in s["comments"]), ""]
    entries = s.get("entries") or []
    if entries:
        rows = []
        for e in entries:
            meta = [x for x in (_who(e), _kind(e), ("%s/5" % e["rating"]) if e.get("rating") else "", _day(e.get("created"))) if x]
            rows.append('  "%s"\n    - %s' % (e.get("message") or "", ", ".join(meta)))
        L += ["Client feedback:", "\n".join(rows)]
    return "\n".join(L).strip() + "\n"


_GWT = re.compile(r"given (.+?),? when (.+?),? then (.+)", re.I)
_WHEN = re.compile(r",? when ", re.I)


def gherkin(s, bundle=None):
    L = ["Feature: " + s["title"], "  As a " + (s.get("persona") or "…"), "  I want " + (s.get("goal") or "…")]
    if s.get("benefit"):
        L.append("  So that " + s["benefit"])
    n = len(s.get("entries") or [])
    L += ["", "  # Based on %d piece%s of client feedback" % (n, "" if n == 1 else "s"), ""]
    for a in s.get("acceptance") or []:
        g = _GWT.search(a)
        if g:
            scenario = _WHEN.split(a)[0]
            if scenario.lower().startswith("given "):
                scenario = scenario[6:]
            L.append("  Scenario: " + scenario)
            L += ["    Given " + g.group(1), "    When " + g.group(2), "    Then " + g.group(3)]
        else:
            L += ["  Scenario: " + a, "    Then " + (a[:1].lower() + a[1:])]
        L.append("")
    return "\n".join(L).strip() + "\n"


def jira(s, bundle=None):
    L = ["h2. " + s["title"], "", "*As a* %s, *I want* %s%s." % (s.get("persona") or "…", s.get("goal") or "…",
                                                                 (", *so that* " + s["benefit"]) if s.get("benefit") else ""), ""]
    if s.get("acceptance"):
        L += ["h3. Acceptance criteria", "\n".join("* " + a for a in s["acceptance"]), ""]
    if s.get("notes"):
        L += ["h3. Notes", s["notes"], ""]
    if s.get("comments"):
        L += ["h3. Supporting comments", "\n".join("* *%s:* %s" % (c["author"], _one_line(c["body"])) for c in s["comments"]), ""]
    entries = s.get("entries") or []
    if entries:
        L.append("h3. Client feedback (%d)" % len(entries))
        for e in entries:
            meta = [x for x in (_who(e), _kind(e), ("%s/5" % e["rating"]) if e.get("rating") else "", _day(e.get("created"))) if x]
            L += ["{quote}%s{quote}" % (e.get("message") or ""), "_%s_" % " · ".join(meta), ""]
    return "\n".join(L).strip() + "\n"


def csv(s, bundle=None):
    def q(v):
        v = "" if v is None else str(v)
        return '"' + v.replace('"', '""') + '"'
    entries = s.get("entries") or []
    desc = sentence(s) + "\n\nAcceptance criteria:\n" + "\n".join("- " + a for a in s.get("acceptance") or [])
    if s.get("notes"):
        desc += "\n\nNotes:\n" + s["notes"]
    if entries:
        desc += "\n\nClient feedback:\n" + "\n".join('"%s" (%s)' % (e.get("message") or "", _who(e)) for e in entries)
    labels = []
    for e in entries:
        for t in list(e.get("tags") or []) + list((e.get("ai") or {}).get("tags") or []):
            t = re.sub(r"\s+", "-", t)
            if t not in labels:
                labels.append(t)
    row = [q(s["title"]), q(desc), q("Story"), q(s.get("priority")), q(s.get("points")), q(" ".join(labels)),
           q(STORY_STATUSES.get(s.get("status"), s.get("status")))]
    return "Summary,Description,Issue Type,Priority,Story Points,Labels,Status\n" + ",".join(row) + "\n"


def ai_json(s, bundle=None):
    b = json.loads(json.dumps(bundle or {}))
    b["story"] = {k: s.get(k) for k in ("title", "persona", "goal", "benefit", "acceptance", "notes", "priority", "status", "points")}
    b["supporting_comments"] = [{"author": c["author"], "body": c["body"]} for c in s.get("comments") or []]
    return json.dumps(b, indent=2, ensure_ascii=False) + "\n"


MAKERS = {"markdown": markdown, "text": text, "gherkin": gherkin, "jira": jira, "csv": csv, "json": ai_json}


def render(fmt, s, bundle=None):
    return MAKERS.get(fmt, markdown)(s, bundle)


def file_name(s, fmt):
    ext = dict((k, e) for k, _, e in FORMATS).get(fmt, "txt")
    slug = re.sub(r"[^a-z0-9]+", "-", (s.get("title") or "story").lower()).strip("-")[:50] or "story"
    return slug + "." + ext
