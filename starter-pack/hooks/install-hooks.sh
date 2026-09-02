#!/usr/bin/env bash
# Wire the starter-pack pre-commit gate into this repository's git hooks.
# Idempotent; refuses to clobber an unrelated existing hook.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
git_dir="$(git rev-parse --git-dir 2>/dev/null)" || {
  echo "Not a git repository — run 'git init' first." >&2
  exit 1
}

hook="$git_dir/hooks/pre-commit"
src="$here/pre-commit"

if [ -e "$hook" ] && ! grep -q "lint_mantle.py" "$hook"; then
  echo "Refusing to overwrite an existing unrelated pre-commit hook at:" >&2
  echo "  $hook" >&2
  echo "Merge it manually with $src" >&2
  exit 1
fi

cp "$src" "$hook"
chmod +x "$hook"
echo "Installed: $hook"
echo "Every commit now runs: python3 scripts/lint_mantle.py"
