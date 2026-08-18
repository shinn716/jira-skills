# jira-skills

Two skills for **Jira Server / Data Center**, built around the read-only Jira MCP server:

| Skill | What it does |
|---|---|
| `jira-sync` | Reads the current git branch, writes a ≤1000-char change summary in Jira wiki markup, posts it as a comment on the ticket named by the branch (`feature/PROJ-123` → `PROJ-123`). |
| `jira-sprint-report` | Pulls a sprint, renders one person's work as a self-contained HTML file: stats, SVG charts, a sortable/filterable issue table, a written summary per closed ticket, and a team comparison block. |

They compose: `jira-sync` posts the write-up at merge time, `jira-sprint-report` harvests
those same comments at the end of the sprint.

## Not for Jira Cloud

Comment bodies here are **wiki markup** and auth is a **Personal Access Token**. Jira Cloud
uses ADF for comments and email + API token for auth — `post-comment.sh` will not work
against Cloud unchanged. The read paths (sprint report) go through MCP and are more portable.

## Install

Both skills are plain [Agent Skills](https://developers.openai.com/codex/skills) — a
directory with a `SKILL.md` carrying `name` and `description`. Any agent that reads that
format can run them. Only the Claude Code path uses the plugin marketplace; the rest is
copying two directories.

### Claude Code

```bash
claude plugin marketplace add shinn716/jira-skills
claude plugin install jira-skills@jira-skills
```

Or clone and add the local path (`claude plugin marketplace add /path/to/jira-skills`), or
copy `skills/jira-sync` and `skills/jira-sprint-report` into `~/.claude/skills/`.

### OpenAI Codex

```bash
git clone https://github.com/shinn716/jira-skills
cp -r jira-skills/skills/jira-sync  jira-skills/skills/jira-sprint-report  ~/.codex/skills/
```

Project-scoped instead: copy into `.agents/skills/` and commit. `/skills` lists them, `$`
mentions one. Restart Codex if a freshly copied skill does not show up.

### opencode

```bash
cp -r jira-skills/skills/* ~/.config/opencode/skills/
```

opencode also reads Claude-compatible paths, so `~/.claude/skills/` or a project
`.claude/skills/` works unchanged — one copy serves both agents.

### Cross-agent notes

- **MCP tool names are written bare** in the skills (`jira_get_sprint_issues`), not with
  Claude's `mcp__jira__` prefix. Each agent prefixes its own way; match on the suffix.
- **Codex sandboxes network access by default.** `post-comment.sh` talks to Jira over HTTPS,
  so it fails under the default sandbox — run Codex with network access enabled, or approve
  the command when prompted. The sprint report is unaffected: it reads through MCP and
  `render.py` only writes a local file.
- **`render.py` needs Python 3 and nothing else**, so it runs the same everywhere.
- `post-comment.sh` needs `bash`, `curl` and `python` on PATH. On Windows, Git Bash.

## Setup

### JIRA_URL and JIRA_PERSONAL_TOKEN

`post-comment.sh` reads both from the environment and exits with a named error if either is
missing. The MCP server wants the same pair (see below).

**1. Create the token.** Jira → avatar → **Profile** → **Personal Access Tokens** → *Create
token*. Name it, set an expiry, copy the value — Jira shows it once. The token inherits your
own permissions, so it can comment on exactly the tickets you can.

Personal Access Tokens are Jira **Server / Data Center** (8.14+). On Jira Cloud the same
menu gives an API token that authenticates as `email:token` over Basic, not Bearer — see
"Not for Jira Cloud" above.

**2. Set the variables.** `JIRA_URL` is the base URL, no trailing path — `/rest/...` is
appended by the script. A trailing slash is stripped for you.

Simplest with Claude Code: the `env` block of **`~/.claude/settings.json`**. Every Bash tool
call inherits it, so `post-comment.sh` works in any project without touching your shell
profile:

```json
{
  "env": {
    "JIRA_URL": "https://jira.example.com",
    "JIRA_PERSONAL_TOKEN": "NDU2..."
  }
}
```

Merge into the existing `env` object if you already have one, and restart Claude Code.
Put it in the **user-level** `~/.claude/settings.json`, never in a project's
`.claude/settings.json` — that file gets committed. The token sits in plaintext either way,
so treat the file like an SSH key: user-only permissions, no syncing it into a repo.

Other agents, or if you would rather not keep a token in a config file — shell environment,
persisted in `~/.bashrc` / `~/.zshrc`:

```bash
export JIRA_URL=https://jira.example.com
export JIRA_PERSONAL_TOKEN=NDU2...          # the value you just copied
```

Windows, from PowerShell — `setx` writes to the user environment, so **open a new terminal**
afterwards:

```powershell
setx JIRA_URL "https://jira.example.com"
setx JIRA_PERSONAL_TOKEN "NDU2..."
```

**3. Check it works.** 200 with your account name means both variables are right:

```bash
curl -s -H "Authorization: Bearer $JIRA_PERSONAL_TOKEN" \
  "$JIRA_URL/rest/api/2/myself" | head -c 200
```

`401` → bad or expired token. `404` here → `JIRA_URL` points at something that is not the
Jira base URL (a context path like `/jira` is easy to drop). A connection error → DNS, VPN or
TLS, not auth.

**Optional: `JIRA_COMMENT_MAX`.** Caps the comment length in characters — default `1000`, `0`
disables the check. Set it the same way as the two above. `post-comment.sh` counts characters
(CJK counts as 1 each) and refuses to post an over-long body rather than truncating it.

The skills themselves never write the token anywhere — but the `settings.json` route above
does put it on disk in plaintext, so keep that file user-only and out of any dotfiles repo or
cloud-synced folder. Keep the token out of `config.json`, out of commit messages and out of
Jira comments; rotate it from the same Profile page if it leaks.

### jira-sprint-report — a config file

Copy `skills/jira-sprint-report/config.example.json` to `config.json` beside it:

```json
{
  "jira_url": "https://jira.example.com",
  "board_id": "1234",
  "board_name": "My Scrum Board",
  "me": "your.jira.username"
}
```

No secrets — the sprint report reads Jira through the MCP server, which holds its own
credentials. `config.json` is gitignored because the board id and username are yours.

Assignee resolution, first hit wins: CLI argument → `"me"` in the input JSON → `JIRA_ME`
→ `config.json`. Matched case-insensitively as a substring of the display name, so
`jane.doe` matches `jane.doe Jane Doe`.

### MCP server

Both skills read through an Atlassian MCP server, using the same URL and token as above:

```json
{
  "type": "stdio",
  "command": "uvx",
  "args": ["mcp-atlassian"],
  "env": {
    "JIRA_URL": "https://jira.example.com",
    "JIRA_PERSONAL_TOKEN": "...",
    "READ_ONLY_MODE": "true"
  }
}
```

Claude Code expands `${JIRA_URL}` / `${JIRA_PERSONAL_TOKEN}` in MCP config values, so if you
took the `settings.json` route above you can reference them here instead of pasting the token
a second time.

Codex wants the same server in `~/.codex/config.toml`:

```toml
[mcp_servers.jira]
command = "uvx"
args = ["mcp-atlassian"]
env = { JIRA_URL = "https://jira.example.com", JIRA_PERSONAL_TOKEN = "...", READ_ONLY_MODE = "true" }
```

opencode takes it under the `mcp` key of `opencode.json` (`"type": "local"`, `command` as an
argv array).

`READ_ONLY_MODE=true` is why `jira-sync` posts over REST instead of through MCP: a read-only
server exposes no comment tool. Keeping it read-only means no skill can mutate a ticket by
accident — the one write path is a single script that asks for confirmation first.

## Rendering a report by hand

`render.py` needs no third-party packages — Python 3 standard library only.

```bash
python skills/jira-sprint-report/render.py sprint.json out.html ["Assignee Name"]
```

Input JSON is the raw MCP issue objects plus a `sprint` block; the optional `work_summary`
per issue is what shows up under each row. Re-rendering the same dump for a different
person is one command.

`sample-sprint.json` is a working input you can render without touching Jira:

```bash
python skills/jira-sprint-report/render.py \
  skills/jira-sprint-report/sample-sprint.json out.html
python skills/jira-sprint-report/test_render.py   # same file, as a smoke test
```

## Handling secrets in tickets

People paste keys, tokens and connection strings into Jira comments. Both skills are
instructed to summarise the *fact* ("signing key rotated") and never copy the value into a
report or a new comment. If you find a live credential in a ticket, the skill will say so
instead of quietly propagating it.

## Gotchas worth knowing

- **"Done" is a status category, not a status name.** Custom statuses like `Terminated` or
  `Closed` also sit in category `Done`. Filtering on the literal name undercounts.
- **Sprint issue endpoints cap at 50 per page.** Both skills page until they reach `total`;
  a partial page silently skews every percentage in the report.
- **Comment threads correct themselves.** A later comment often retracts an earlier
  conclusion. The summary step reads the whole thread rather than grabbing the longest
  comment, which is usually the retracted one.

## Licence

MIT.
