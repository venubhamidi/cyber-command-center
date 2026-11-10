# Working practices

How work is planned, agreed, cut up and built in this repository. The skills in `.claude/skills/`
turn these practices into commands; this file is the reasoning behind them. The practices are
adapted from Matt Pocock's skills repository (https://github.com/mattpocock/skills, MIT) and
restated here for this codebase.

## 1. Settle decisions before building

1. List the decisions the work depends on, and which of them depend on which.
2. Ask only the decisions whose prerequisites are already settled. Ask all of them in one numbered
   round, each with its options and a recommended answer.
3. Wait for the answers. Work out what is now unblocked. Ask the next round.
4. Look facts up yourself in the code, the requirements and the schema. Ask a person only for
   choices.
5. Stop when nothing is open. Summarise what was decided and get agreement before acting.

Open decisions live in the application package's `DECISIONS.md`. An answer is recorded there the
moment it is given. A question the requirements do not answer becomes an Open row; it is never
guessed in code.

The `grill` skill runs this interview.

## 2. Shared language

**Glossary** (`CONTEXT.md`, one at the root for foundation terms and one in the application
package for domain terms). It holds the domain's terms and their meanings, nothing else. Add a
term the moment it is agreed. When someone's wording conflicts with the glossary, or one word is
being used for two things, say so and propose one precise term. Test a definition against concrete
edge cases. Use glossary terms in code, tests, tickets and answers.

**Decision record** (`docs/adr/`). Write one only when all three hold: the decision is hard to
reverse, it would surprise a future reader, and it was a real choice between workable
alternatives. Otherwise a row in `DECISIONS.md` is enough.

The `glossary` and `adr` skills apply these.

## 3. Vertical slices

Each ticket is a thin but complete path through every layer it needs, and can be demonstrated on
its own. It fits one fresh agent session. Preparatory refactoring is its own ticket and comes
first. Each ticket names what blocks it; anyone may pick up a ticket with nothing outstanding.

A ticket says what to build as behaviour a user can observe, what blocks it, and its acceptance
checklist. It does not prescribe files or code. Agree the breakdown before creating tickets.

A mechanical change across the codebase is done in three steps: add the new form beside the old,
move callers over in batches, remove the old form.

The `slice` skill produces the tickets; `.github/ISSUE_TEMPLATE/slice.md` is their shape.

## 4. Test first, at the seams

One failing test, then only the code that makes it pass, then the next test. Agree the seams
before writing tests. A seam is a public boundary where behaviour can be observed: an endpoint,
`AgentRunner.execute`, an MCP tool, a rule function, the evaluation runner. Test behaviour, not
internals. Take expected values from an independent source, never from the logic under test. Name
tests in glossary terms. Restructuring is a separate step, done at review. Every agent bug gets an
evaluation case; every other bug gets a test.

## 5. Module design

Prefer a small interface in front of a lot of behaviour. The interface is everything a caller
must know, including ordering, errors and required settings. If deleting a module makes things
simpler, it was a pass-through. If a test must reach past an interface, the module is the wrong
shape. Add an interchangeable seam only when something really varies across it: one
implementation is a guess, two is evidence. Pass dependencies in; return results.

## 6. Writing for agents

Order instructions by how often they are needed. Detail needed only sometimes goes in a separate
file, with a pointer whose trigger word comes first. End each step with a checkable completion
line. State each rule once. Do not restate what the repository already shows; record conventions,
reasons and traps. Say what to do; keep prohibitions for hard guardrails. Delete instructions the
agent follows anyway, and anything stale. Shorter is easier to keep true.
