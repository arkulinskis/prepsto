# Prepsto

Prepsto is a customer-feedback plug-in. A creator (anyone with a website or app) makes a **feedback link**; dropping it on their site as a link or one script tag gives their users a clean feedback panel. The creator then triages everything on prepsto.com and turns it into **user stories** with supporting comments and the client's own words, exported to Markdown, Gherkin, Jira, CSV or an AI-ready JSON bundle. Text analysis is a built-in rules engine today, built to be swapped for AI. Built on [Anvil](https://anvil.works).

- **App repo:** github.com/arkulinskis/prepsto (branch `master`). Anvil pulls `master`.
- **Live:** https://prepsto.com (custom domain; not live yet, set up after the first publish).

## What it does

Keep this list current: it is the first thing read before every change.

**For people giving feedback (no account):**
- **The panel** (`#f/<code>`): kind chips (Bug / Idea / Praise / Question / Other, chosen per link), message, optional 1-5 stars,
  optional email, honeypot against bots, a thank-you screen. Phone-first. Rate-limited (12 per hour per browser session).
- **Embedded** (`#f/<code>/embed/<page url>`): the same panel filling a slide-in frame on the creator's site, with a close button.
- **Follow it (closed loop):** after sending, a private **tracking link** (`#t/<token>`, "Track my feedback" on the
  thank-you screen). It shows the steps Received → Under review → Planned → In progress → Done (or "Closed for now"), the
  priority the team gave it, the story it became ("On the plan") and how many others asked for the same thing, a timeline of
  every change and the team's public replies, and a box to add details or answer the team. The panel remembers each person's
  messages in their browser ("Your feedback · 3", with a dot for new updates). The demo has one at `#t/demo`.
- **The widget** (`assets/widget.js`, served at `https://prepsto.com/_/theme/widget.js`): one script tag adds a floating
  button (colour, label, left/right) that slides the panel in; `data-button="false"` + any `[data-prepsto-open]` element for
  your own button; `Prepsto.open()` / `Prepsto.close()`. No cookies, nothing loaded until opened.

**For creators (members):**
- **Overview** (`#home`): new / this week (vs last week) / average rating / stories, a 14-day chart, needs-attention list
  (new + urgent), latest feedback, sentiment split, feedback by kind, top themes, their links with copy buttons.
- **Inbox** (`#inbox`, `#inbox/tag/<tag>`): list with status tabs (Open, New, Reviewing, Planned, Done, Archived, All), filters
  (link, kind, tag, sort, starred) and search; select + bulk actions (status, tag, draft a story, delete); **Board** view
  (kanban New / Reviewing / Planned / Done with drag and drop). Filters and view are remembered.
- **Feedback drawer**: the message, who/when/page/device/rating, status and priority, tags (+ suggested tags), Insights
  (sentiment, urgency, theme, summary), star, link to a story or "Draft a story from this", team comments, similar feedback,
  archive, delete.
- **Updates for the sender** (in the drawer, marked *public*): the sender's timeline, "They last checked …", a reply box
  (they see it on their tracking page; a reply to a New message moves it to Reviewing), "Copy their tracking link" and "Email it
  to them" (a mailto: with the link). Status, priority, story links and story status (Ready / In progress / Shipped) are added
  to their timeline automatically. When the sender answers, the owner and the assignee get a bell notification and the inbox row
  says **Sender replied** until someone answers. Team comments stay private. Per link: "Let people follow their feedback" (on by default).
- **Stories** (`#stories`) and the **story editor** (`#story/<id>`): title, As a / I want / So that with a live sentence,
  acceptance criteria, priority, estimate, notes; client feedback (add / unlink), supporting comments; autosaves;
  "Redraft from feedback"; **Export**: Markdown, plain text, Gherkin, Jira markup, CSV, AI-ready JSON (copy or download).
- **Links** (`#links`, `#links/<id>`, `#links/new`): create and edit links (name, website, question, kinds in your order
  (the first is picked when the panel opens), colour, button text and side, thank-you text, rating/email on or off,
  open/closed, tracking on/off), up to 60 per account with a live preview; install code tabs (script, link,
  own button, HTML link); new code (rotates the public code), re-run insights, delete.
- **Team workspaces:** each link has its owner plus invited teammates (Links → Team card). The owner invites by email
  (the invite appears on the invitee's Overview and bell when they sign in with that email) and can copy an invite link
  (`#join/<token>`; Prepsto sends no email). Teammates triage, assign, comment and write stories; only the owner changes
  settings, the team or the code, deletes feedback or the link. Members can leave; the owner can remove people or cancel invites.
- **Assign + @mention:** assign feedback to a teammate ("Assigned to you" on the Overview, "Assigned to me" filter in the Inbox);
  type `@` in any comment (drawer or story) to mention a teammate.
- **Notification bell** (header): mentions, assignments, invitations, people joining; each opens what it's about
  (`#inbox/entry/<id>`, `#story/<id>`, `#join/<token>`); mark one or all read.
- **Starter sample:** every new member gets "Sample: Lumen Notes" (14 messages, 2 stories) to explore; deletable.

**For everyone:** a landing page (with "Try the panel" on the demo link `#f/demo`), sign-up with email and password or Google, feedback through Prepsto ("Submit feedback" in the footer and menu opens its panel),
and the Privacy & Terms page (footer link, `#legal`).

**For admins** (`#admin`; arkulinskis@gmail.com becomes an admin on first sign-in):
- **Feedback inbox:** feedback about Prepsto itself: New / Read / Done, private notes.
- **Links:** every feedback link with its owner and message count (team links included); close or reopen one (admins never see the feedback itself).
- **Users:** search, make admin, disable an account.
- **Demo data:** the public demo link `#f/demo` ("Lumen Notes (demo)", owned by a demo account); remove or reload it.

## Setting it up in Anvil (once)

1. In the Anvil editor: **Create app → Clone from GitHub**, and paste `https://github.com/arkulinskis/prepsto`.
2. **Users** service: email + password and "Continue with Google", sign-up allowed (already set in `anvil.yaml`; check it).
3. Open the app in the editor. If it shows a **Schema Mismatch** alert, choose **"The schema of the source code is correct"** so Anvil creates the tables.
4. **Run** it and sign up with **arkulinskis@gmail.com** straight away (that account becomes the admin).
5. **Publish** (Publish → public URL, or your own domain).

<!-- libraries:start -->
## Libraries and outside services

What this project uses besides its own code. Generated by `APP_MAKER/tools/libraries.py`; to change it, edit `APP_MAKER/libraries/catalog.py` and re-run the script.

| Name | How it gets in | Used here for |
|---|---|---|
| [Google Fonts](https://fonts.google.com) | Loaded from a CDN | Inter, JetBrains Mono, Space Grotesk |

**Built into the browser:** localStorage, Clipboard, File downloads (Blob).

**Anvil platform:** Anvil, Anvil Data Tables, Anvil JS bridge (anvil.js), Anvil Users.

**Build and test tools (not shipped):** Node.js, PyYAML, Headless Chrome (DevTools Protocol).

<!-- libraries:end -->

## Working on it

See `.claude/skills/prepsto/SKILL.md`. In short:

```
python -I tools/check.py --ui                    # syntax, server tests, headless UI tests → ALL CHECKS PASSED
python -I tools/preview/devserver.py 8765        # the app on in-memory data: http://localhost:8765/  (?as=ana#home, ?as=admin#admin)
python tools/deploy.py                           # dry run (needs PyYAML, so no -I)
python tools/deploy.py --push "Message"          # deploy: commit + push to GitHub, Anvil pulls it
```

With the dev server running, `http://localhost:8765/demo/embed.html` is a pretend customer site with the widget installed.

## Project layout

```
web/            the interface: core.js/core.css (shared engine + design tokens), app.js (header, footer), pages/*.html
client_code/    Main.py (the only Anvil form: bridge to the server, sign-in), legal.py
server_code/    common.py, Accounts.py, Feedback.py, Admin.py, DemoData.py, legal_server.py,
                Boards.py (links + the public panel), Team.py (teams, invites, notifications), Inbox.py, Stories.py, Insights.py (rules engine / AI hook), Samples.py
assets/         icon.svg + generated PNG icons, widget.js (the embeddable widget), served at _/theme/<name>
tools/          sync_to_anvil.py (settings + table schema), deploy.py, check.py, preview/ (dev server, UI tests, screenshots), testing/
```
