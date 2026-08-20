---
name: jira-refine
description: Read a Jira ticket's title and description, analyse the current repo, work out a concrete solution, and rewrite the ticket description as a structured spec - tables, a numbered flow, and bullet lists. Use when the user says "refine the ticket", "/jira-refine", "整理 ticket", "update the ticket description", "propose a solution on the ticket", or hands over a ticket key and asks how to solve it in this codebase.
---

# jira-refine

Turn a thin ticket — a problem statement and little else — into a solution spec grounded in
this repo, and write it back as the ticket description.

Targets **Jira Server / Data Center**: REST API v2, auth by Personal Access Token.
Description bodies are **Jira wiki markup** — Markdown is not converted, `**bold**` and
`` `code` `` show up literally.

Reads go through the Jira MCP server (`jira_get_issue`) when one is available. The write goes
through `update-description.sh`, because a read-only MCP server exposes no update tool.

## Setup

Same two variables as the rest of this plugin:

```bash
export JIRA_URL=https://jira.example.com
export JIRA_PERSONAL_TOKEN=...   # Jira → Profile → Personal Access Tokens
```

## Steps

### 1. Resolve the ticket

Key comes from the user, or from the branch name if they did not give one:

```bash
git rev-parse --abbrev-ref HEAD    # feature/PROJ-123-foo → PROJ-123
```

Match `[A-Z][A-Z0-9_]+-[0-9]+`. If no key can be resolved, stop and ask. Never guess.

Read the ticket: summary, description, issue type, linked issues, and the comment thread.
Comments frequently narrow or contradict the description — a later comment wins over an
earlier one.

### 2. Analyse the repo

The point of this skill is that the spec is grounded in code that exists, not in a plausible
architecture. Before writing anything, find:

- The entry points the ticket touches (controller, handler, job, screen, script).
- The existing pattern for this kind of change — a similar feature already in the repo is the
  template. Reuse it rather than inventing a second way to do the same thing.
- What actually breaks, for a bug ticket: trace to the root cause and to every caller that
  routes through it, not just the path the ticket names.
- Config, migrations, feature flags the change implies.

Cite real paths (`src/foo/Bar.java:120`). A file path you have not opened does not go in the
description.

If the ticket is too vague to solve — the requirement genuinely has more than one reading and
they lead to different code — ask the user before writing, do not silently pick one.

### 3. Draft the description

**The original description is never overwritten.** It stays at the top, word for word, under
its own heading; the spec is appended below it. The reporter's wording is evidence of what
was asked for — paraphrasing it loses the detail that turns out to matter three weeks later.

```
h2. Original Request
<the previous description, verbatim — not reformatted, not summarised, not corrected>

h2. Background
* one bullet per fact from the original ticket, kept
* one bullet per constraint found in the repo

h2. Current State
||Area||Location||Problem||
|Order creation|{{OrderService.create}} src/order/OrderService.java:88|No stock check|

h2. Solution
# step one — what changes, in which file
# step two
# step three

h2. Impact
||File / module||Change||Risk||
|{{OrderService}}|Add stock check|Checkout behaviour changes|

h2. Acceptance Criteria
* observable condition, phrased so it can be checked
```

Headings in English, as above. If the team reads the ticket in another language, the user
says so and you translate the six headings — the structure does not change.

Tables, flow and bullets only, below `Original Request`. That section is the one exception:
whatever the reporter wrote goes in as it is, prose and all.

**Re-running this skill must not stack copies.** Read the current description first:

- No `h2. Original Request` in it → the whole current text is the original. Put it under the
  heading, append the spec.
- Already has one → keep that block exactly as it stands and replace everything below it.
  Never wrap a previous run's output into a new `Original Request`.

If the description is empty, the ticket summary is all there is: skip the section and say so.

Wiki markup rules that bite:

- Table header row is `||a||b||`, data rows `|a|b|`. One line per row, no line breaks inside a
  cell.
- `*` (bullets) and `#` (numbered) must be in **column 1** — an indented marker does not render.
- `{{monospace}}` for class / method / config names, `*bold*` (single asterisks) for a
  behaviour change.
- Headings are `h2.` at line start, followed by a space.

Content rules:

- Every row of Current State and Impact names a real file. No speculative rows.
- No prose paragraphs of your own. If something does not fit a table, a numbered step or a
  bullet, it does not belong in the description.
- A requirement from the original that you disagree with stays in `Original Request`
  untouched; argue with it in `Background`, do not edit it away.
- Do not invent numbers. Any metric must come from a code comment, a commit, the ticket, or
  something you actually measured — and say which.
- **Never paste credentials.** Repos and tickets contain keys and connection strings; state
  the fact ("signing key rotated"), never the value.

### 4. Confirm, then write

The description field is replaced wholesale by the REST call, even though the text you send
starts with the original. So the body you post must **contain** the original — check that it
does before posting, character for character. Show the full rendered text to the user and get
an explicit go-ahead. "Refine PROJ-123 and update it" in the same turn counts as the
go-ahead; anything less does not.

Write the body to a temp file (UTF-8), then:

```bash
bash <skill-dir>/update-description.sh PROJ-123 /tmp/jira-description.txt
```

The script saves the current description to a backup file and prints its path before writing,
so the previous text is recoverable. Report both the backup path and the browse URL back to
the user.

## Notes

- Analysis only — this skill never edits code, commits, or merges. It reads the repo and
  writes one Jira field.
- The reporter's text survives every run: it sits under `h2. Original Request` and only ever
  gets copied forward, never edited.
- Restoring anyway: `bash update-description.sh PROJ-123 <backup-file>` puts the whole
  previous field back, spec included.
- Pairs with `jira-sync`: `jira-refine` writes the plan onto the ticket before the work,
  `jira-sync` posts what actually changed after it.
