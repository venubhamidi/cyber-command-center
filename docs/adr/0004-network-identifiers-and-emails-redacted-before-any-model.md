# IP addresses, MAC addresses and e-mail addresses are redacted before any model sees text
**Status:** accepted
**Date:** 2026-11-10

## Context
The PRD requires the data platform to stay on premises and allows hosted inference only after
classification, privacy, contractual and security reviews (§6 deployment principle). Which model
is approved, and whether asset facts such as host names and owners may leave the premises, is
still open (`DECISIONS.md` D-014). Agents already exist and will be pointed at a real model one
day; a redaction policy added later would have to be retrofitted to every agent and every stored
execution.

## Decision
`redact_patterns = ["ipv4", "mac", "email"]` in `ccc/config.py`. The harness replaces matching
values with placeholders before text reaches a model and restores them in the result, whichever
provider is configured. This holds even for a local model. Host names, owner names and business
unit names are not redacted; that is the open half of D-014. Test:
`test_ip_addresses_never_reach_the_model_but_are_intact_in_the_result`.

## Alternatives considered
- **Redact nothing until a model is chosen.** Leaves nothing to test and nothing recorded when the
  choice is made; agents would ship with the gap.
- **Redact everything identifying, including host names and owners.** Makes the agent's answer
  unusable for the executive it is written for; a decision for the CISO, not a default.
- **Redact only for hosted providers.** Couples a security property to a configuration value.

## Consequences
- A model sees `<ipv4_1>` where the asset record says `10.20.2.40`; the brief shown to the user
  has the real value.
- Adding a pattern is a settings change; removing one is a decision for the Security Architect.
