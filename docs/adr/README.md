# Architecture decision records

A record is written only when **all three** hold:

1. The decision is hard to reverse.
2. It would surprise a future reader.
3. It was a real choice between workable alternatives.

Otherwise a row in the application package's `DECISIONS.md` is enough. `/adr` applies the test
and writes the record.

## Format

File: `docs/adr/NNNN-<slug>.md`, numbered in order of writing. Sections, in this order:

```
# <title>
**Status:** proposed | accepted | superseded by NNNN
**Date:** YYYY-MM-DD

## Context
## Decision
## Alternatives considered
## Consequences
```

A record is never edited into a different decision. When a decision changes, write a new record
and mark the old one superseded.
