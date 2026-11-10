#!/usr/bin/env bash
# Upgrade this repository's harness/ to a released version of the template.
#
#   scripts/update_harness.sh <template-repo-url-or-path> [tag-or-branch]
#
# Replaces harness/ with the template's copy, then runs the checks and tests. Review the
# harness/CHANGELOG.md entries between your old version and the new one before committing.
set -euo pipefail
SOURCE="${1:?usage: scripts/update_harness.sh <template-repo-url-or-path> [tag-or-branch]}"
REF="${2:-main}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [ -n "$(git -C "$ROOT" status --porcelain)" ]; then
  echo "Commit or stash your changes first." >&2; exit 1
fi
OLD="$(cat "$ROOT/harness/VERSION")"
git clone --quiet --depth 1 --branch "$REF" "$SOURCE" "$TMP/template"
NEW="$(cat "$TMP/template/harness/VERSION")"
rm -rf "$ROOT/harness"
cp -r "$TMP/template/harness" "$ROOT/harness"
find "$ROOT/harness" -name __pycache__ -type d -prune -exec rm -rf {} +
cp "$TMP/template/scripts/harness_lock.py" "$TMP/template/scripts/check_structure.py" "$ROOT/scripts/"
echo "harness $OLD -> $NEW. Running checks..."
cd "$ROOT"
python scripts/check_structure.py
python -m pytest -q
echo "Done. Read harness/CHANGELOG.md, then commit."
