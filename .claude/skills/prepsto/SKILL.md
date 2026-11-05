---
name: prepsto
description: Context, workflow and recipes for Prepsto (folder prepsto-forms), the user's Anvil app built as native Anvil Forms (Python + HTML templates, a layout, custom components, RepeatingPanels). A customer-feedback plug-in (a panel on any site via one link or script tag) with an inbox, kanban board, user stories with exports, and an API + CLI/MCP server so members' Claude can read and work their tickets. Load this before any feature request, bug fix, restyle, content change or deploy for this app.
---

# Prepsto: working on the app

**What it is:** Prepsto, hosted at prepsto.com. **Creators** (members) make feedback links ("boards") and can invite
**teammates** to each link (assign, @mention, notification bell); **people giving feedback** (no account) use the panel
at `#f/<code>`, opened from a plain link or from the floating button that `theme/assets/widget.js` adds to the
creator's site, and follow it on a private tracking page `#t/<token>`. Creators triage feedback (Overview, Inbox list +
board, drawer), turn it into **user stories** and export them (Markdown, text, Gherkin, Jira, CSV, AI-ready JSON).
**Claude & API** (`#claude`): members make API keys so Claude Code (through `prepsto.py`, a CLI + MCP server) or their
own scripts read and work their tickets. Text analysis is the rules engine in `server_code/Insights.py`.

**Where it lives:**
- Folder `C:\Users\arkvi\Documents\CLAUDE\prepsto-forms\` = the git clone of **github.com/arkulinskis/prepsto**.
  "git" layout: the folder *is* the Anvil app. Converted to native Forms on branch **`forms`** (Nov 4 2026); master and
  the live app keep running the old JavaScript version (folder `prepsto`, source layout) until the user approves the merge.
- Made the template-forms way (`APP_MAKER/template-forms`). Anvil's agent skills: `APP_MAKER/vendor/anvil-agent-references`.
- **README.md** lists every feature. Keep it up to date.

**What the user wants:** "white and technical with a dark mode". Pure white page, hairline borders, almost no shadows,
small radii (10/7px), electric blue brand #2b59ff + signal orange accent #ff5a1f (as text: `--c-accent-ink`); dark:
#0a0b0f / #111319, brand #6e8bff. Fonts: Space Grotesk (headings), Inter (body), JetBrains Mono (labels, badges, eyebrows
like `// overview`, numbers). Grid-paper backgrounds. Claude assumes details and builds; Claude deploys. Mobile-first:
every page must fit 390 px. Prepsto is every other app's feedback channel: its panel must never break.

## Workflow for any change

1. `git pull --ff-only` (Anvil commits "Edited ..." when the user changes something in the IDE; read those commits).
2. Edit: a page's template and Python side by side (`client_code/Pages/X/form_template.html` + `__init__.py`).
3. `python tools/check.py` (no -I) -> **ALL CHECKS PASSED**: `anvil validate` (type-checks every template and Python
   file, server code too), JS syntax, asset hashes, server tests (`tools/testing/test_server.py`, includes the API).
4. `python -I tools/ui_test.py` (Docker Desktop running) -> **ALL UI TESTS PASSED**: flow.js (visitor panel + tracking,
   sign-up, Overview, Inbox + drawer + board, story + export, Links preview, Claude & API with real HTTP calls), then
   `tools/testing/cli_test.py` (the prepsto CLI + MCP server against the same App Server, with a key flow.js made),
   phone.js, admin.js, a11y.js (axe WCAG 2.2 AA, light + dark). Server edits need `--restart`.
   `--shots DIR` = screenshots of every page (desktop + phone, light + dark): Read them.
5. Commit only your files as arkulinskis with the Co-Authored-By line; push (`forms` until merged, then `master`).
   New tables/columns: tell the user to accept the **Schema Mismatch** alert ("The schema of the source code is correct").

## Architecture

```
anvil.yaml          startup module `startup`; db_schema (+ api_keys, api_log); head_html: SEO block, fonts, Prepsto widget,
                    icons.css, app.css, app-kit.js, px.js, legal-kit.js (all ?v=<hash>, tools/assets.py)
client_code/
  startup.py router.py state.py auth.py legal.py   the template's modules (router: PAGES, NAV, closes an open drawer)
  px.py             kinds/statuses/priorities/stages, badge helpers (px.kind(label, "bug") ...), link + snippet builders,
                    the sender timeline wording (update_parts), this browser's "Your feedback" list (mine_*)
  exports.py        story exports, plain Python: the Export dialog AND the API (server imports it)
  Layouts/Shell     header (nav, bell + notifications, account menu with Claude & API), footer, phone tab bar
  Layouts/Bare      no chrome: #f (panel, f-embed inside the widget frame) and #t (tracking)
  Pages/            Landing, Panel (#f), Track (#t), Join, Auth, Home (Overview), Inbox, Stories, Story, Links, Claude,
                    Profile, Admin (+ Links tab)
  Components/FeedbackPanel   the panel (custom component): setup(board, preview, embed, page, on_close, on_sent), update(b)
  Dialogs/          Drawer (one piece of feedback; alert role px-drawer), TagAll, NewStory, Export, AddFeedback,
                    StoryMore, NewKey, KeyCreated
  Items/            EntryRow, BoardColumn/BoardCard, NotifItem, InviteRow, HomeLink, KindBar, ThemeTag, DayBar, TabButton
                    (tabs/seg/format choices), StoryCard, AcRow, StoryQuote, Comment, TimelineItem, SimilarItem, PickRow,
                    LinkPick, KindToggle, Swatch, PersonRow, Step, MineItem, KindChip, CheckRow, DrawerTag, AdminLinkRow,
                    ApiKeyRow, ApiLogRow, TagChip, NavLink, FeedbackRow, UserRow
server_code/        unchanged callables (Accounts, Feedback, Admin, DemoData, Boards, Team, Inbox, Stories, Insights,
                    Tracking, Samples, SchemaCheck, seo_routes, legal_server); Inbox/Stories/Tracking have `*_view`/`*_as(me, ...)`
                    helpers the API reuses. ApiKeys.py (keys, auth, log) + ApiRoutes.py (HTTP API /_/api/v1/...)
theme/assets/       app.css (tokens, old page styles, role layer, Prepsto Forms layer at the end), icons.css (generated),
                    app-kit.js (icons table), px.js (clipboard, download, browser names, @mentions, board drag highlight,
                    video), widget.js (served to other sites), prepsto-cli.py + prepsto-skill.md (downloads on #claude)
tools/              check.py, assets.py, build_icons.py, ui_test.py + ui/, testing/test_server.py, testing/cli_test.py
```

Pages and addresses are the same as the JavaScript version (`#inbox/entry/<id>` opens a drawer, `#inbox/tag/<t>`,
`#links/new`, `#join/<token>`, `#f/<code>/embed/<page>`), so shared links keep working.

## How things are done here

The template-forms rules apply (one Form per page, Shell refresh, RepeatingPanel + Items, Dialogs + alert(), Labels for
changing text, Buttons with roles, JS only for engines). Prepsto specifics:
- **Badges are Labels with roles** set by px.py (`px-kind bug ic-bug`, `px-status new`, `px-prio high`, `px-senti`,
  `px-stars` with `--n`, `px-stage`, `st-state`). `ic-<name>` on a Label puts the icon before its text (build_icons.py).
- **Inline Labels:** role `px-inline` (+ `strong`, `muted`...). Never put Labels inside `<p>`: the HTML parser moves the
  Label's `<div>` out of the paragraph. Use a `<div>`/`<span>`.
- **TextArea/TextBox/DropDown roles sit on the `<textarea>`/`<input>`/`<select>` itself**: style
  `:is(textarea.anvil-role-x, .anvil-role-x textarea)`.
- **The drawer**: `alert(Drawer(entry_id=...), buttons=[], role="px-drawer", large=True, dismissible=True)`; it returns
  True (reload), `{"go": (page, arg)}`, or None; `Drawer.LAST["changed"]` covers Escape/backdrop closes. It registers in
  `px.DIALOG`, and router.show closes it when the address changes (Back button, bell links).
- Lists draw 60 rows at a time (Inbox "Show more"): the browser's Python is slow with hundreds of item Forms.
- Clicks on whole rows/cards use `anvil.js.get_dom_node(self).addEventListener` (root `anvil:on-dom` isn't wired on 1.18).
- Story editor: inputs listen to `input` events (0.9 s autosave via state.later), `leaving()` saves when the page changes.

## The API, keys and the CLI (Claude & API)

- Keys: `psk_` + 40 random chars; only SHA-256 + first 12 chars stored. Scopes read / write / reply (reply implies
  write), optional link list, expiry 30/90/365 days or never, max 10 active keys, 600 requests / 10 min per key, last 200
  requests logged per key (api_log). A key acts as its owner through Boards.role_in at request time.
- Endpoints (ApiRoutes.py docstring has the full list): `/v1/me`, `/v1/links` (with each link's code), `/v1/tickets`
  (POST = file a ticket yourself, by link id or code; no email field) (+ `/<id>`, `/comments`,
  `/replies`), `/v1/stories` (+ `/<id>?format=markdown`, `/comments`). Ids are `169207-4096` (Anvil's `[169207,4096]`
  without brackets: `sid`/`rid`). Never returns senders' emails or tracking tokens; no deletes; keys in the address are refused.
- `prepsto-cli.py` (served as `_/theme/prepsto-cli.py`, downloaded as prepsto.py): stdlib only, config in
  `~/.prepsto/config.json` (600), `prepsto.py mcp` = MCP stdio server (tools list_tickets, get_ticket, update_ticket,
  create_ticket, add_team_comment, reply_to_sender, list_stories, get_story, draft_story, update_story, list_links, whoami).
  `prepsto-skill.md` = a Claude Code skill for the ticket workflow (reply to senders only with the user's OK).
- New API field: add it to `ticket()` in ApiRoutes (check it leaks nothing), the CLI's printing, the MCP schema, tests.

## Recipes

- **New page:** Pages/X + router PAGES/_form (+ NAV), add to tools/ui/phone.js and a11y.js, a journey in flow.js.
- **New server function:** callable + `C.require_user()` + ownership via Boards.role_in; tests in test_server.py
  (happy path, bad input, someone not allowed; public ones in `PUBLIC`).
- **New table or column:** `db_schema` in anvil.yaml; read new columns with `C.col(row, name)` where other sites depend on
  it (the panel's widget_config / widget_submit) so the old behaviour works until the Schema Mismatch is accepted.
- **New panel option:** a `boards` column, `_clean` + `board_dict` + the `widget_config` whitelist in Boards.py, the form
  in Pages/Links, and Components/FeedbackPanel.update.
- **New export format:** `exports.py` (FORMATS + MAKERS); the API picks it up too.
- **New feedback kind:** `KINDS` in Boards.py, `px.KINDS` + `KIND_ORDER`, a `.anvil-role-px-kind.anvil-role-<kind>` colour,
  `KIND_PERSONA` in Insights.py, the CLI's choices.
- **Plug in AI:** `_ai_analyze` / `_ai_draft` in Insights.py, `PROVIDER = "ai"`, the legal kit (providers, automated_note).
- **Widget changes:** theme/assets/widget.js is served to other people's sites: dependency-free, ES5, no cookies.

## Gotchas

- `python -I` hides PyYAML: check.py, assets.py and test_server.py run without -I; ui_test.py and cli_test.py with -I.
- Old page CSS aimed at `span`s (`.x .grow span {...}`) hits Label text: use `> span`. Anvil's `.anvil-label-text` is
  inline-block: `px-inline` forces inline so long text doesn't jump to its own line.
- `.ui-menu` is also the bell panel's class: tests use `.ui-menu:not(.px-notifs)` for the account menu.
- A board dict has `new` (a count): don't use `new` as a flag on items (LinkPick uses `_new`).
- `ALLOW_EMBEDDING` (anvil.yaml `allow_embedding: true`) is required: the widget shows the panel in an iframe.
- Don't rotate the "Prepsto" link (938ktjj) or any code in APP_MAKER/prepsto-links.json: every app's feedback button uses them.
- Rate limits are per Anvil session for the browser (C.rate_limited) and per key for the API (ApiKeys.authenticate).
- Contrast: status colours were darkened for WCAG AA (Nov 2026); check new colours with a11y.js.

## Privacy & Terms (legal kit)

From `APP_MAKER/legal-kit`: change `apps/prepsto.json`, then there `python -I build.py prepsto` and install into this
folder (`install.APPS["prepsto"] = ("prepsto-forms", "git"); install.install("prepsto", False)` until apps.json points
here), then `python tools/assets.py`. The facts cover the API keys (fingerprint only, log, what connected tools get).
Sign-up keeps the tick box (`legal.consent_field()` in Pages/Auth). Feedback = Prepsto only ("Submit feedback").
