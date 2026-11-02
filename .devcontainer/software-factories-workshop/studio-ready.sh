#!/usr/bin/env bash
# Exit 0 only if every Studio container is running and healthy RIGHT NOW. No old log line counts.
# Reads no key value.
for c in studio-database keycloak studio-backend studio-web-client model-service; do
  state="$(docker inspect -f '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}nohealth{{end}}' "$c" 2>/dev/null)" || exit 1
  case "$state" in
    "running healthy"|"running nohealth") ;;
    *) exit 1 ;;
  esac
done
exit 0
