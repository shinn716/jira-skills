---
name: jira-commit
description: Summarize the work sitting in the working tree, commit it with that summary as the message, then run jira-sync to post the change summary to the ticket. Never pushes. Use when the user says "commit", "/jira-commit", "commit and sync", "幫我 commit 並同步 ticket", or finishes a piece of work and wants it committed and the ticket updated.
---

# jira-commit

Close out a piece of work in two writes: one commit, one Jira comment. No push, no merge.

The natural follow-on to `jira-implement` or a `jira-goal` run, both of which deliberately
leave everything uncommitted for a human to review.

## Steps

### 1. See what is actually there

```bash
git status --short
git diff                 # unstaged
git diff --cached        # staged
git log --format=%s -8   # the repo's own subject style
```

Read the real diff, not just the stat. The commit message is a summary of *changes*, and you
cannot summarise what you have not read.

**If part of the tree is not yours** — files changed before this session that the work does
not touch — stop and ask which files to include. Never sweep unrelated work into someone
else's commit.

Nothing to commit → say so and stop. Do not create an empty commit.

### 2. Check the diff before it becomes history

- **Credentials.** Keys, tokens, connection strings, `.env` files. Found one → stop, tell the
  user, do not commit. A secret in a commit stays in the history after the file is deleted.
- **Debug leftovers.** Stray prints, commented-out code, a hardcoded local URL, a skipped
  test. Point them out; the user decides.
- **Files that should not be tracked.** Build output, IDE folders, local config. Suggest
  `.gitignore` rather than committing them.

### 3. Write the message

Match the repo's existing style — read those eight subjects before writing. Otherwise:

```
<subject: what changed, imperative, ~70 chars, no ticket key prefix unless the repo does that>

<why it changed — the root cause for a fix, the requirement for a feature>

- one line per logical change, with the file or class it lives in
- behaviour changes and new assumptions, spelled out
```

- Summarise the work, not the diff. "Fixed the null check in three callers" is the diff;
  "Guard against a missing session in the shared resolver, which all three callers route
  through" is the work.
- No filler bullets for mechanical edits — say "renamed across 14 call sites" once.
- Do not invent a reason. If the ticket or a code comment does not say why, describe what
  changed and leave the why out.
- The ticket key lives in the branch name already; the message does not need to repeat it
  unless the repo's history does.

### 4. Commit, and only commit

Show the message to the user first. Then:

```bash
git add <the files agreed in step 1>
git commit -F <message-file>
```

`-F` with a file, not `-m` with a shell string: a multi-line message with backticks or quotes
gets mangled by the shell otherwise.

**Never `git push`.** Not as a convenience, not "since the branch is remote already". Pushing
is the user's call, every time. Same for merge, rebase, amend of a pushed commit, and any
force. Report the short SHA and let them push.

### 5. Then sync to the ticket

Default: run it. Skip it when the user said "commit only", or when the branch carries no
ticket key — the commit stands either way, just say the sync was skipped and why.

Run `jira-sync` and follow it: resolve the ticket key from the branch, summarise
`<mainline>..HEAD`, respect the character cap, show the comment and get the go-ahead before
posting. The commit you just made is part of that range.

Posting is visible to the team, so the confirmation stands even though the commit is done.
If the user already said "commit and sync" in one turn, that covers both.

### 6. Report

Labelled lines, not one dense sentence. A SHA on its own says nothing — put the subject next
to it:

```
Committed — PROJ-123

- commit   0463261  Shrink the README diagrams
- files    README.md, README.zh-TW.md (+28 / -68)
- branch   feature/PROJ-123-slug (not pushed)
- comment  https://jira.example.com/browse/PROJ-123?focusedCommentId=88214
```

Labels are written in whatever language the user is speaking; the example is English.

`not pushed` stays on the branch line every time — it is the state the user has to act on.
Sync skipped → say so on the comment line with the reason (`skipped, no ticket key on the
branch`).

## Notes

- Two writes, both recoverable in practice: an unpushed commit (`git reset --soft HEAD~1`)
  and a Jira comment.
- `jira-goal` never commits, on purpose. This skill is the human step that follows it.
