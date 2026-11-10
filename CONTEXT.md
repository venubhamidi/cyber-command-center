# Glossary: foundation terms

Terms that mean the same thing in every application built on this template. Domain terms live in
the application package's own `CONTEXT.md`. One `##` heading per term; definition, example, and
the word it is confused with. Add a term the moment it is agreed (`/glossary`).

## advisory
The confidence every agent response carries: the output is a recommendation for a person, never a
decision that has been acted on.
Example: a review agent's `suggested_next_step` is advisory; a person reads it and decides.
Not: approval, verdict.

## agent
A class that answers one kind of question by calling read-only tools for facts, computing flags
with rule functions, and asking a model to write words as a validated structure. It can recommend;
it cannot change anything.
Example: the Item Review Agent summarises one item and names its gaps.
Not: a background job, a workflow step that writes data, a chat bot.

## application
One product built on the template: its own tables, rules, endpoints, agents, tools, screens and
tests, in its own repository.
Example: the Cyber Command Center.
Not: the harness, the template repository.

## application package
The one Python package in the repository that holds the application, named in `pyproject.toml`
under `[tool.harness] app_package`. Everything specific to the application lives under it.
Example: `app/` in the template; `ccc/` in the Cyber Command Center.
Not: `harness/`, `tests/`, `scripts/`.

## evaluation suite
A set of cases, each with an input and checks on the agent's response, run against an agent with
fixed fixture records and a mock model. Every agent has one and CI requires a perfect score.
Example: `ownerless-item-is-flagged` checks that the flags for a fixture item equal `["no_owner"]`.
Not: a unit test, a benchmark of prose quality.

## guardrail event
A note the harness records on an agent response when a protection acted during the run: untrusted
data looked like instructions, values were redacted before a model saw them, or model output failed
validation and was retried.
Example: `injection_suspected:get_item`, `redacted:2`, `output_validation_retry`.
Not: an error; the run may still succeed.

## harness
The read-only foundation folder every application is built on: login, permissions, audit, rate
limiting, database, migrations, agent contract, guardrails, model gateway, evaluations, plugins
and deployment. Versioned and checksum-verified; changed only in the template repository.
Example: `harness/` version 1.0.0.
Not: the application, the template as a whole.

## MCP server
A small process that exposes read-only tools over the Model Context Protocol. It, not the model,
queries the database. Agents reach tools only through it.
Example: the items server with its `get_item` tool.
Not: a model provider, an API endpoint.

## plugin
A factory registered under a kind and a name, chosen by a setting, that connects the application
to one outside system. Swapping systems is a configuration change.
Example: `APP_TICKETING_PROVIDER=servicenow` selects the ServiceNow ticketing plugin.
Not: a Python package dependency, a library.

## plugin kind
The role a plugin fills, which fixes the interface it must implement. The harness defines `auth`,
`llm`, `secrets` and `ticketing`; an application may add its own.
Example: `scanner`, with `tenable` and `defender` plugins.
Not: the plugin's name.

## seam
A public boundary where behaviour can be observed and tested without reaching inside: an
endpoint, `AgentRunner.execute`, an MCP tool, a rule function, the evaluation runner.
Example: a test calls `/api/v1/items/summary` rather than the SQL behind it.
Not: a private function, a module's internals.

## tool
A named, read-only function an agent may call for facts, listed in the agent's `allowed_tools`;
any other name is refused and audited.
Example: `get_item(item_key)` returns one item as JSON.
Not: a shell command, a write operation, a model call.
