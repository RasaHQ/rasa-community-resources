#!/usr/bin/env bash
# Creates the resource's .env from its .env.example, filled from the Codespaces secrets that are present.
# Never prints a value, never overwrites an existing .env, and leaves an unset secret out rather than empty
# so that a blank `KEY=` cannot shadow the real environment variable. Usage: make-env.sh <resource folder>
set -eu
cd "${1:?resource folder}"
[ -f .env.example ] || exit 0
[ -f .env ] && exit 0
umask 077
: > .env
while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    [A-Z]*=*)
      key="${line%%=*}"
      case "$key" in
        RASA_LICENSE|RASA_PRO_LICENSE|OPENAI_API_KEY|ANTHROPIC_API_KEY|GEMINI_API_KEY|DEEPGRAM_API_KEY|RIME_API_KEY|SPEECHMATICS_API_KEY)
          if [ "$key" = RASA_PRO_LICENSE ]; then value="${RASA_PRO_LICENSE:-${RASA_LICENSE:-}}"; else value="${!key:-}"; fi
          if [ -n "$value" ]; then printf '%s=%s\n' "$key" "$value" >> .env; fi
          continue
          ;;
      esac
      ;;
  esac
  printf '%s\n' "$line" >> .env
done < .env.example
