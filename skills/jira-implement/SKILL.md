---
name: jira-implement
description: Implement a Jira ticket in the current repo - read the ticket (the jira-refine spec if there is one), work through its solution steps in code, and verify. Use when the user says "implement the ticket", "/jira-implement", "照 ticket 實作", "做這張單", "start work on PROJ-123", or hands over a ticket key and asks for the code.
---

# jira-implement

Take a ticket that already says *what* to do — ideally one `jira-refine` has structured — and
write the code.

Reads Jira through the MCP server (`jira_get_issue`). Writes nothing back to Jira: the ticket
gets its update from `jira-sync` after the branch merges. This skill only touches the repo.

## Steps

### 1. Resolve the ticket and read it whole

Key comes from the user, or from the current branch (`git rev-parse --abbrev-ref HEAD`,
match `[A-Z][A-Z0-9_]+-[0-9]+`). No key, no guessing — ask.

Read summary, description, issue type, **and the comment thread**. A refined ticket keeps
the reporter's words under `h2. Original Request` above the spec — read that section too, the
spec is one reading of it and can be wrong. A later comment routinely
narrows or reverses the description; the thread wins over the description, the description
wins over the title.

If the description carries the `jira-refine` structure, its Solution numbered list is the
work plan and its Acceptance Criteria are the definition of done. If not, derive both
yourself and state them back to the user before writing code.

**Stop and ask** if the ticket has more than one reading and they lead to different code.
Everything that does not depend on the answer can still be done first.

### 2. Check the ground truth

The ticket describes intent; the repo describes reality. Before editing:

```bash
git status                          # clean tree? uncommitted work is not yours to bury
git rev-parse --abbrev-ref HEAD
```

Open every file the plan names and confirm it still says what the ticket claims. A spec
written days ago against moved code is the main way this goes wrong — if a step no longer
matches the repo, say so and adapt the step rather than forcing it.

For a bug, reproduce first. A fix for a bug you never saw fail is a guess.

### 3. Branch

Unless the user says to work on the current branch:

```bash
git switch -c feature/PROJ-123-short-slug <mainline>
```

Slug from the ticket summary, lowercase, hyphens. The key must be in the branch name —
`jira-sync` reads it back from there.

### 4. Implement

One step of the plan at a time. Follow what the repo already does — its patterns, naming,
error handling and test style are the spec for *how*, the ticket is only the spec for *what*.
Reuse the existing helper before writing a second one.

- Root cause, not symptom. Grep every caller of a function before changing it; fix it once
  where all callers route through.
- Smallest change that satisfies the Acceptance Criteria. Nothing speculative, nothing
  "while I'm here" — unrelated problems you spot get reported to the user, not fixed here.
- Non-trivial logic leaves one runnable check behind, in whatever test style the repo already
  uses.
- Secrets stay out of the diff: config or env, never a literal.

### 5. Verify before claiming anything

Run the repo's own checks — build, lint, tests — and read the output. Then walk the
Acceptance Criteria one condition at a time and say how each was confirmed.

Report failures with the failing line quoted. A test you did not run is not a passing test.
If a condition cannot be verified here (needs staging, a device, prod data), say which and
why rather than implying it passed.

### 6. Hand off

Summarise: what changed per file, which Acceptance Criteria are confirmed, what is left.
Commit only if the user asks. After the merge, `jira-sync` posts the write-up to the ticket.

## Notes

- No pushing, no merging, no ticket transitions — this skill stops at a verified local branch.
- Scope is the ticket. A requirement the ticket does not carry needs the user's word before
  it becomes code.
