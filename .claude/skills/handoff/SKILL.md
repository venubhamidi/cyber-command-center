---
name: handoff
description: Write .scratch/handoff-<date>.md so a fresh session can continue the current work from the file alone. Use at the end of a session, before context runs out, or when stopping mid-task.
argument-hint: [one-line goal, optional]
---

# handoff: leave the next session everything it needs

## Steps

1. Find the application package and check the working tree:
   `APP=$(python -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['tool']['harness']['app_package'])")`
   then `git status --short` and `git log --oneline -5`.
   Done when: you know what is committed, what is modified, and what is untracked.

2. Run the checks and keep the results:
   `python scripts/check_structure.py; ruff check .; python -m pytest -q`
   Done when: you can state pass or fail for each, with the failing names if any.

3. Write `.scratch/handoff-<YYYY-MM-DD>.md` (add `-2`, `-3` if the file exists) with these
   headings, each filled, none skipped:
   - **Goal**: the task in one or two sentences.
   - **Done**: what is finished and committed, with commit hashes.
   - **In progress**: what is modified or half-built, file by file, and what state it is in.
   - **Decisions made**: choices made this session and where they are recorded
     (`$APP/DECISIONS.md` row IDs, ADR numbers, glossary terms added).
   - **Open questions**: what you could not settle and who can.
   - **Next step**: the exact next action, specific enough to start without thinking.
   - **Verify**: the commands to run and the output that means "still green".
   Done when: every heading has content, and nothing in it relies on this conversation.

4. Read the file as if you had no memory of the session. Add whatever a stranger would need.
   Done when: a new session could continue from the file alone.

## Completion
The handoff file exists, every heading is filled, and the check results in it are current.
