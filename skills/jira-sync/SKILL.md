---
name: jira-sync
description: Summarize the current branch's changes and post them as a comment to the matching Jira ticket. Use when the user is merging a feature branch into the mainline, says "sync to jira", "/jira-sync", "post summary to the ticket", or asks to update a Jira ticket with what changed on the branch. Ticket key is derived from the branch name (feature/PROJ-123 -> PROJ-123).
---

# jira-sync

Post a change summary from the current git branch to its Jira ticket.

Targets **Jira Server / Data Center**: REST API v2 comments, auth by Personal Access Token.
Jira Cloud uses ADF for comment bodies and email+API-token auth — the posting script here
will not work against Cloud unchanged.

Comment bodies are written in **Jira wiki markup** — that is what the Server comment renderer
understands. Markdown is not converted: `**bold**` and `` `code` `` would show up literally.

## Setup

Two environment variables, nothing else:

```bash
export JIRA_URL=https://jira.example.com
export JIRA_PERSONAL_TOKEN=...   # Jira → Profile → Personal Access Tokens
```

Or, for Claude Code, the `env` block of the user-level `~/.claude/settings.json` — Bash calls
inherit it, so it works in every project. Never the project `.claude/settings.json`; that one
gets committed.

Optional: `JIRA_COMMENT_MAX` caps the comment length in characters — default `1000`, `0`
disables the check.

`post-comment.sh` exits with a named error if either required variable is missing.

Reads go through the Jira MCP server (`jira_get_issue`) when one is available; use it freely
for context. Writes go through `post-comment.sh`, because a read-only MCP server exposes no
comment tool.

## Steps

### 1. Resolve the ticket key

Branch name carries the key. Match `[A-Z][A-Z0-9_]+-[0-9]+` against:

```bash
git rev-parse --abbrev-ref HEAD
```

`feature/PROJ-123` → `PROJ-123`. Suffixes are fine: `feature/PROJ-123-product-detail-url-fix`
→ `PROJ-123`.

If HEAD is already on the mainline (merge is done), take the key from the merge commit
subject instead:

```bash
git log -1 --format=%s
```

`Merge branch 'feature/PROJ-123' into 'develop'` → `PROJ-123`.

If no key can be resolved, stop and ask the user for it. Never guess.

Confirm the ticket exists and read its summary — this tells you what the ticket was actually
asking for, which shapes the write-up.

### 2. Gather the changes

Use the repo's mainline branch (`develop`, `main`, …) as the base:

```bash
git log --oneline <base>..HEAD
git diff --stat <base>...HEAD
```

Then read the real diff for the source files, not just the stat. Read the full diff of
production code; for large mechanical changes (many similar XML/config edits) sample a few
and describe the pattern with a file count instead of quoting each one.

```bash
git show <sha> -- <paths>
git diff <base>...HEAD -- <paths>
```

Code comments often carry the *reasoning* and the production log numbers that justify a
change. Mine them — they are the best source for the "why" in the summary.

### 3. Write the summary

**Hard limit: 1000 characters**, or whatever `JIRA_COMMENT_MAX` is set to (`0` disables the
check). Count characters (CJK chars count as 1 each), including markup and whitespace. If the
draft is over, cut — do not post it long. `post-comment.sh` enforces the same cap and refuses
an over-long body, so a draft that slips through fails at the post rather than landing
truncated.

Jira wiki markup, but flat and terse. No `h3.` headings, no test section, no scope header:

- One line per logical change: what changed + **why** (root cause), with the class or file.
  `{{monospace}}` for class / method / bean / config names, `*bold*` (single asterisks) for a
  behaviour change.
- `*` at the start of a line for bullets, one level, no nesting. Wiki lists need the marker in
  column 1 — an indented `*` does not render as a bullet.
- 4–8 bullets max at the default cap; fewer if the cap is lower. Merge related changes into one bullet; drop mechanical or trivial edits.
- Keep behaviour changes and new assumptions (e.g. "writes are no longer guaranteed to
  succeed") — these survive the cut before anything else does.
- Drop: diff replay, file counts, restating the ticket, motivation prose, "done" filler.

Do not invent numbers. Any metric (slow query counts, timings, cache miss counts) must come
from a code comment, the commit message, or something you actually measured — and say which.

**Never paste credentials into a comment.** Diffs and code comments sometimes contain keys,
tokens or connection strings. Summarise the fact ("signing key rotated"), never the value.

Before posting, count the characters and state the count to the user.

### 4. Confirm, then post

Posting to Jira is outward-facing and visible to the team. Show the rendered comment text
to the user and get an explicit go-ahead before posting. If the user already said "post it"
in the same turn as invoking the skill, that counts.

Write the body to a temp file (UTF-8), then:

```bash
bash <skill-dir>/post-comment.sh PROJ-123 /tmp/jira-comment.txt
```

Prints `OK <browse url> (comment id N)` on success; non-zero exit and the API response body
on failure. Report the browse URL back to the user.

## Notes

- This skill never commits, merges, or pushes — it only reads git state and posts to Jira.
- Merges usually happen as server-side pull/merge requests, so this skill is invoked manually
  around the merge rather than fired by a git hook.
