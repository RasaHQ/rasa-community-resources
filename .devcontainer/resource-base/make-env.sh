#!/usr/bin/env bash
# Creates the resource's .env from its .env.example, filled from the Codespaces secrets that are present.
# Never prints a value, never overwrites an existing .env, and leaves an unset secret out rather than empty
# so that a blank `KEY=` cannot shadow the real environment variable. The file is made private while it is still
# empty, and no value is written unless that succeeded. Usage: make-env.sh <resource folder>
set -eu
cd "${1:?resource folder}"
[ -f .env.example ] || exit 0
[ -f .env ] && exit 0

mode_of() { stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1"; }
fail() {
  rm -f .env
  echo "ERROR: $1 The .env file was removed, so it holds no secret; the resource will read the secrets from the environment instead." >&2
  exit 1
}

umask 077
: > .env || fail "Could not create .env."
# Privacy first, on the empty file: set the mode explicitly (a default ACL can override the umask) and verify it.
chmod 600 .env || fail "Could not restrict .env to mode 600 on this filesystem."
[ "$(mode_of .env)" = "600" ] || fail "The filesystem did not apply mode 600 to .env."

while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    [A-Z]*=*)
      key="${line%%=*}"
      case "$key" in
        RASA_LICENSE|RASA_PRO_LICENSE|OPENAI_API_KEY|ANTHROPIC_API_KEY|GEMINI_API_KEY|DEEPGRAM_API_KEY|RIME_API_KEY|SPEECHMATICS_API_KEY)
          if [ "$key" = RASA_PRO_LICENSE ]; then value="${RASA_PRO_LICENSE:-${RASA_LICENSE:-}}"; else value="${!key:-}"; fi
          if [ -n "$value" ]; then printf '%s=%s\n' "$key" "$value" >> .env || fail "Could not write .env."; fi
          continue
          ;;
      esac
      ;;
  esac
  printf '%s\n' "$line" >> .env || fail "Could not write .env."
done < .env.example
