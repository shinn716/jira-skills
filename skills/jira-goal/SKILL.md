---
name: jira-goal
description: Autonomous end-to-end run on one Jira ticket - refine the description, implement it, keep implementing until every acceptance condition passes, then post the summary back. Pre-authorized: one approval up front covers every Jira write in the run. Use when the user says "goal mode", "/jira-goal", "超級模式", "自動跑完 PROJ-123", "take this ticket end to end", or "refine, implement and sync without asking me each step".
---

# jira-goal

One ticket, start to finish, without a confirmation prompt per step:

```
jira-refine → jira-implement → verify → (loop until done) → jira-sync
```

This is an orchestration skill. Each phase is the existing skill, run in full — read
`jira-refine`, `jira-implement` and `jira-sync` and follow them. What this skill adds is the
authorization gate, the loop, and the stop conditions.

## The authorization gate

Everything downstream depends on this, so it happens **before any phase runs, and only once**.

State the plan concretely and get an explicit yes:

```
Goal run on PROJ-123 — "<ticket summary>"

Will do, without asking again:
  1. append a solution spec to the description of PROJ-123
     (original text kept at the top, whole field backed up to a file)
  2. branch feature/PROJ-123-<slug> off <mainline>, edit code, run the repo's checks
  3. loop 2 until every Acceptance Criterion passes (max 5 passes)
  4. post a change summary as a comment on PROJ-123

Will NOT do: git commit, git push, merge, transition the ticket, touch any other
ticket or repo. The changes are left in the working tree for you to review and commit.

Go?
```

The user saying "yes" or "go" in reply, or having already said "run it end to end, don't
ask me" in the invoking turn, authorizes phases 1–4 for **this ticket, this run**. Nothing
else. A second ticket needs a second gate.

Never skip the gate on the grounds that the user "clearly wants it" — invoking the skill is
not the approval, the answer to this message is.

## Phases

### 1. Refine

Run `jira-refine` fully: read the ticket and thread, analyse the repo, draft the structured
spec, append it under the untouched original, write it with `update-description.sh`.

Difference under goal mode: you do not stop for the "show and confirm" step — the gate
covered it. Still print the description you wrote and the backup path, so the user can see
what landed and revert it. Check the original text is still in there before posting.

Skip this phase if the description already has the `jira-refine` structure and matches the
current repo. Say that you skipped it and why.

### 2. Implement

Run `jira-implement` fully: branch, work the Solution steps, run the repo's build/lint/tests.

**Never commit.** Creating the branch is allowed; `git commit`, `git add`, `git push`, merge
and anything that rewrites history are not, not even "so the diff is easier to read". The run
ends with the work uncommitted in the tree — reviewing and committing it is the user's step,
and it is the only remaining place a human sees the code before it becomes history.

### 3. Loop until done

After each pass, walk the Acceptance Criteria one condition at a time against real command
output. Then:

| Situation | Do |
|---|---|
| All conditions pass | Go to phase 4 |
| Some fail, cause is understood and new | Fix, run pass N+1 |
| Same failure twice in a row | Stop. Report the failing output and what you tried |
| 5 passes used | Stop. Report what passes, what does not |
| A condition cannot be checked here (staging, device, prod data) | Do not count it as passed — carry it to the report as unverified |

Never weaken a test, skip a check, or reinterpret a condition to make a pass succeed. A
condition that turns out to be wrong is a reason to stop and ask, not to edit it.

### 4. Sync

Run `jira-sync`: summarise the changes, respect the character cap, post with
`post-comment.sh`. The gate covered the confirmation. Report the browse URL.

`jira-sync` normally reads commits (`git log <base>..HEAD`). A goal run has none — the work
is uncommitted — so take the changes from the working tree instead:

```bash
git status --short
git diff <mainline>            # staged + unstaged, against the branch point
```

Everything else in `jira-sync` is unchanged: wiki markup, the character cap, no credentials
in the comment.

Only after phase 3 finished clean. A stopped run does not post a "done" comment — it reports
to the user instead.

## Stop conditions the gate does NOT cover

Hit any of these and the run halts, whatever was authorized. Report what is done, what is
left, and what the run needs from the user:

- The ticket has more than one reading and they lead to different code.
- The repo no longer matches the plan in a way that changes the approach.
- A credential appears in the repo, the diff or the ticket.
- The work needs something outside this repo and this ticket — another repo, another ticket,
  a schema change nobody asked for, a new dependency.
- Any destructive or outward-facing action: commit, push, merge, force, history rewrite,
  ticket transition, deleting anything that is not this run's own output.
- The tree was dirty at the start with work that is not this run's.

Do the parts that do not depend on the blocker first, then stop and say what blocked.

## Report

One block at the end, regardless of how the run finished:

```
PROJ-123 — <finished | stopped at phase N>
description   spec appended, original kept (backup: /tmp/jira-PROJ-123-description-….txt)
branch        feature/PROJ-123-slug, N files changed, uncommitted
verified      3/4 acceptance criteria — <condition> unverified: needs staging
comment       <browse url>
left          review the diff, commit, push  (+ anything else)
```

## Notes

- Writes Jira and the working tree, nothing else. `git commit` and `git push` stay with the
  user — that review step is the last human gate before the code becomes history.
- The old description is recoverable —
  `bash update-description.sh PROJ-123 <backup-file>`.
- One ticket per run. Batching tickets means batching the blast radius of one approval.
