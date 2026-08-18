---
name: jira-sprint-report
description: Generate a self-contained HTML report of one person's work in a Jira sprint - stats, charts, a sortable/filterable issue table with a written summary per closed ticket, and a team comparison block. Use when the user says "sprint report", "/jira-sprint-report", "sprint 總結報告", asks how a sprint went, or wants a shareable HTML recap of their sprint.
---

# jira-sprint-report

Read a sprint from Jira and render one standalone HTML file — no external assets, no CDN,
no network needed to open it.

**This is a personal report.** Tiles, charts and the issue table cover one person; the whole
sprint is still fetched so a "Team comparison" block can show every assignee's load, done
count and completion rate with the owner's row highlighted.

## Setup

Copy `config.example.json` to `config.json` beside this skill:

```json
{
  "jira_url": "https://jira.example.com",
  "board_id": "1234",
  "board_name": "My Scrum Board",
  "me": "your.jira.username"
}
```

`config.json` is gitignored. Nothing here is secret — the skill reads Jira through an MCP
server that holds its own credentials — but the board id and username are yours, not the
world's.

Assignee resolution, first hit wins: 3rd CLI argument → `"me"` in the input JSON →
`JIRA_ME` env var → `config.json`. The name is matched case-insensitively as a *substring*
of the assignee display name, so `jane.doe` matches `jane.doe Jane Doe`. An unmatched name
exits with the list of real assignees rather than rendering an empty report.

Read-only: this skill uses Jira MCP read tools only and never writes to Jira.

## Steps

### 1. Pick the sprint

Always present a menu — do not silently assume the active sprint.

```
jira_get_sprints_from_board(board_id=<config.board_id>, state="active")
jira_get_sprints_from_board(board_id=<config.board_id>, state="closed", limit=50)
```

Closed sprints often come back oldest-first — take the tail for the recent ones. Show the
active sprint plus the ~5 most recent closed ones (name, id, date range, state) and let the
user pick (`AskUserQuestion` where available, otherwise a numbered list). If the user already
named a sprint ("Sprint 26", an id), skip the menu.

No board id configured → find it with `jira_get_agile_boards(project_key="PROJ")` and ask
which board, then tell the user to save it in `config.json`.

### 2. Pull every issue

`limit` maxes at 50 and sprints often run past that — **page until you have `total`**.

```
jira_get_sprint_issues(
  sprint_id="<id>", start_at=0, limit=50,
  fields="summary,status,issuetype,assignee,priority,resolutiondate,fixVersions")
```

Repeat with `start_at=50`, `100`, … until the collected count reaches `total`. Never report
on a partial page — the completion percentage would be wrong. Check the returned `total`
against what you collected and say the number out loud before rendering.

### 3. Pick whose report this is

Count the assignees and ask the user (same menu mechanism as step 1), listing them with their
issue counts and the configured `me` first as the default. If the user already named someone, skip the menu.

### 4. Pull the closing summary for each Done ticket

For the owner's Done issues only — a handful, not the whole sprint:

```
jira_get_issue(issue_key="PROJ-123", fields="summary", include="comments", comment_limit=10)
```

Most comments are integration noise ("mentioned this issue in a commit…") from a bot account.
Ignore those. The real write-up is a substantial comment authored by the owner — often the
one this skill's sibling `jira-sync` posted at merge time. Condense it to 2–4 lines into the
issue's `work_summary`: what changed, plus any behaviour change, deployment order or caveat.

Read the whole comment thread before summarising. A later comment often **retracts or
corrects** an earlier one; summarise the corrected conclusion, not the retracted one. Picking
the longest comment blindly gets this wrong.

No such comment → leave `work_summary` out; the row simply shows no note.

Keep the code spans around class / file / config names — `render.py` renders both Markdown
`` `x` `` (what `jira-sync` writes) and wiki `{{x}}` (what older comments carry) as `<code>`.
Do not invent content that is not in the comments.

**Comments can contain secrets** — people paste keys, tokens and connection strings into
Jira. Never copy a credential into `work_summary`; summarise the fact ("signing key rotated")
and tell the user the raw value is sitting in the ticket.

### 5. Write the JSON, render the HTML

Ask the user where to put the HTML. Dump the collected data as UTF-8 JSON:

```json
{
  "sprint": {"name": "Sprint 26", "state": "active",
             "start_date": "2026-08-12T09:37:00.000+0800",
             "end_date": "2026-08-25T09:37:00.000+0800",
             "board": "My Scrum Board"},
  "me": "jane.doe",
  "issues": [ <the issue objects from the MCP results, verbatim, concatenated> ]
}
```

Keep the issue objects as-is — `render.py` reads `key`, `summary`, `browse_url`,
`status.name`, `status.category`, `issue_type.name`, `assignee.display_name`,
`priority.name`, `fix_versions[].name` (or `fixVersions`), `resolutiondate`, `work_summary`,
and ignores the rest. It dedupes by `key`.

```bash
python <skill-dir>/render.py sprint.json out.html ["Assignee Name"]
```

Prints `OK <path> — <name>: N issues, N done, N unfinished (sprint: N issues, N done)`.
Report the path back to the user.

### 6. Report

State the owner's completion rate and unfinished count first, then one line of team context.
Flag what is worth acting on: a status bucket everything is stuck in, a high-priority ticket
still open, work that is merged but not yet deployed. Two or three lines. Do not invent
velocity or story points — the report counts issues, not points.

## Notes

- "Done" is Jira's status **category**, not the status name. Custom statuses like `Terminated`
  or `Closed` also land in category `Done`; filtering on the literal name undercounts.
- Output is one HTML file: inline CSS, inline SVG charts, and a small inline script for the
  Type / Status / Fix Version/s filters and sortable column headers. Fixed light theme.
- Filters and sorting drive the issue table only; the charts stay as rendered.
- The filter select ids and the JS id array must stay in sync. Dropping a filter without
  editing the array leaves a `getElementById` returning null, and the resulting TypeError
  kills the whole script — taking sorting down with it, not just the filter.
- Story points are not in the default field list. If the user wants them, find the custom
  field id with `jira_search_fields("story point")` first; `render.py` does not chart them.
- `render.py` has no third-party dependencies — Python 3 standard library only.
