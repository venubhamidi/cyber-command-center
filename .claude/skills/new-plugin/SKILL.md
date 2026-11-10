---
name: new-plugin
description: Add an integration as a plugin in the application's plugins/ folder, registered with harness.plugins.register, documented in deploy/.env.example, and selected by a setting in a test. Use for any outside system: ticket system, scanner, identity provider, model provider, secret store.
argument-hint: <kind> <name>
---

# new-plugin: an outside system behind a setting

Rules: outside systems are reached through a plugin chosen by a setting, never hard-wired; plugins
live in the application package, never in `harness/`; secrets come from the secrets plugin;
every setting is documented in `deploy/.env.example`.

## Steps

1. Find the application package and the examples to imitate:
   `APP=$(python -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['tool']['harness']['app_package'])")`
   Read `$APP/plugins/__init__.py`, the pattern at the top of `harness/plugins/__init__.py`, the
   small complete example `harness/tests/sample_plugin.py`, and the test that selects it in
   `harness/tests/test_plugins.py`.
   Done when: you can name the kind's interface (for an existing kind) or have defined one (for
   a new kind, in the plugin module's docstring).

2. Write the failing test first, in `tests/`: build the application with
   `plugin_modules=["$APP.plugins.<name>"]` (or the `APP_PLUGIN_MODULES` setting) and the
   kind's provider setting set to your plugin's name, then assert the plugin's type is what the
   application uses and one call through it behaves as expected. Outside calls are simulated;
   no test reaches a real system.
   Done when: the test fails with `PluginNotFound`.

3. Write `$APP/plugins/<name>.py`: a class implementing the kind's interface, and a factory
   `build(settings)` decorated `@register("<kind>", "<name>")`. Every host name, credential or
   model id it needs is a setting on the application's `Settings` or a secret fetched through
   the secrets plugin. Nothing is hard-coded.
   Done when: the test passes.

4. Document every new setting in `deploy/.env.example` (commented out if optional, with its
   meaning), and add the plugin name to the list of values for its kind's `APP_<KIND>_PROVIDER`.
   Done when: `python scripts/check_structure.py` reports no undocumented setting.

5. Run the checks: `python scripts/check_structure.py && ruff check . && python -m pytest -q`.
   Done when: all pass.

## Completion
The plugin is selected by a setting in a test, its settings are in `deploy/.env.example`, and
the structure check passes.
