---
name: glossary
description: Add or sharpen one term in the application's CONTEXT.md glossary, and flag conflicts between the owner's wording, the glossary and the code. Use the moment a term is agreed, or when a word is being used for two things.
argument-hint: <term> [proposed meaning]
---

# glossary: one word, one meaning

The rules are `docs/working-practices.md` §2. The glossary holds terms and meanings only, never
implementation detail.

## Steps

1. Find the application package:
   `APP=$(python -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['tool']['harness']['app_package'])")`
   Domain terms go in `$APP/CONTEXT.md`; terms about the harness itself go in the root
   `CONTEXT.md`. Read both.
   Done when: you know which file the term belongs in and whether it is already there.

2. Search the code, tests, API field names and migrations for the term and for any other word
   used for the same thing (`grep -rni` over `$APP/`, `tests/`, `frontend/src/`).
   Done when: you have a list of every spelling and synonym in use.

3. If the owner's wording, the glossary and the code disagree, or one word covers two meanings,
   list the conflict and propose one precise term per meaning. Ask the owner which wins; do not
   settle it yourself.
   Done when: every conflict is either resolved by the owner or written as an `Open` row in
   `$APP/DECISIONS.md`.

4. Write or sharpen the entry in this format and alphabetical position:
   ```
   ## <term>
   <one or two sentences of definition>
   Example: <a concrete instance>
   Not: <the word people confuse it with, if any>
   ```
   Test the definition against an edge case before saving it.
   Done when: the entry has exactly one definition and one example, and the file has no second
   heading for the same thing.

5. List (do not rename) every test name, API field or column that contradicts the entry, so the
   rename can be its own ticket.
   Done when: the list is in your reply, or empty.

## Completion
The term has one definition and one example in the right `CONTEXT.md`, no second word for the
same thing remains in that file, and every conflict found was put to the owner.
