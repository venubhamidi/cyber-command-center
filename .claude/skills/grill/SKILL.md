---
name: grill
description: Interview the owner on the decisions a plan depends on, one round at a time, and record every answer in the application's DECISIONS.md. Use before building anything that rests on an unsettled choice, or with no argument to work through the Open rows.
argument-hint: [plan or feature, or nothing for the Open rows]
---

# grill: settle decisions before building

The method is `docs/working-practices.md` §1. Facts are looked up; only choices are asked.

## Steps

1. Find the application package and its decision log:
   `APP=$(python -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['tool']['harness']['app_package'])")`
   then read `$APP/DECISIONS.md`.
   Done when: you can name the package and have the current rows in front of you.

2. Fix the scope. With an argument, the scope is that plan. Without one, the scope is every row
   whose status is `Open` (a "Decide first" section, if present, goes first).
   Done when: the scope is written in one sentence at the top of your notes.

3. List every decision the scope depends on, and which depends on which. Add any decision not
   yet in `DECISIONS.md` as a new `Open` row with the next free ID before asking it.
   Done when: each decision has an ID, and its prerequisites (if any) are named.

4. Look up what can be looked up: the code, the schema, the requirements document, the glossary
   (`CONTEXT.md` at the root and in `$APP/`). Strike every question the repository answers.
   Done when: nothing left to ask is answerable from the repository.

5. Ask one numbered round: every decision whose prerequisites are settled, each with its
   options, your recommended answer and why. Then stop and wait. Do not act on a guess.
   Done when: the round is posted and no answer has been assumed.

6. Record each answer in `DECISIONS.md` as it arrives: status `Decided`, the choice, the person
   who decided. A question the owner defers stays `Open` with the named person in Owner.
   Done when: every answered row says `Decided` and names a choice; nothing else was changed.

7. Work out what the answers unblocked and go back to step 5. Repeat until the scope has no
   `Open` row that is not explicitly deferred to a named person.
   Done when: no askable decision remains.

8. Summarise the decided rows in a short list and ask the owner to confirm it.
   Done when: the owner has confirmed; `DECISIONS.md` matches the summary.

## Completion
No open decision remains for the scope, the owner has confirmed the summary, and
`$APP/DECISIONS.md` is updated. Nothing was decided by you.
