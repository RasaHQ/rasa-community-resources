#!/usr/bin/env bash
# EXPERIMENTAL, Nov 1, 2026. Still being tested in real codespaces.
# Starts Studio from RasaHQ/studio-docker-compose. That compose file hardcodes localhost for the Studio API,
# the web client's own settings, the model-service chat address and Keycloak's public address. In a browser codespace
# these must be the forwarded addresses, so this script overrides each one. Report the exact error if login still fails.
set -euo pipefail
: "${RASA_STUDIO_LICENSE:?Save RASA_STUDIO_LICENSE as a Codespaces secret scoped to this repository, then restart the codespace}"
# Studio needs a licence with a Studio entitlement, which the free Developer Edition key did not carry in testing. Mantle
# keeps reading RASA_LICENSE. The Studio compose file reads RASA_PRO_LICENSE, which is set here from RASA_STUDIO_LICENSE.
: "${CODESPACE_NAME:?This script is for a codespace}"
DOMAIN="${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
dir="$HOME/studio-docker-compose"
# Pinned to the commit tested in a first run (Studio 1.15.2 and rasa/rasa-pro 3.15.8 from its .env), so a run is repeatable.
STUDIO_COMPOSE_COMMIT=deb6b8fa0dac6991fdb3584ab3143a04b5de3b6c
[ -d "$dir" ] || git clone --quiet https://github.com/RasaHQ/studio-docker-compose "$dir"
git -C "$dir" checkout --quiet "$STUDIO_COMPOSE_COMMIT"
git -C "$dir" rev-parse HEAD
export RASA_PRO_LICENSE="$RASA_STUDIO_LICENSE"
# To try other images, set STUDIO_IMAGE_TAG and RASA_PRO_IMAGE in the environment before running this script, for example
# STUDIO_IMAGE_TAG=1.17.7 RASA_PRO_IMAGE=rasa/rasa-pro:3.21.2. The compose file's own .env pins the tested defaults, and
# variables set in the shell take precedence over it. Nothing was tested with other tags yet.
echo "Studio image tag: ${STUDIO_IMAGE_TAG:-from the compose .env}  Rasa Pro image: ${RASA_PRO_IMAGE:-from the compose .env}"
url() { echo "https://${CODESPACE_NAME}-$1.${DOMAIN}"; }
# The web client serves /usr/share/nginx/html/config.js with the Studio API and Keycloak addresses set to localhost, which
# points at the attendee's own laptop. Nothing in the service environment rewrites it. Take the image's own file, change
# only those two addresses, and mount the result read-only. Every other global stays as the image set it.
mkdir -p "$dir/webclient"
cd "$dir"
docker compose -f docker-compose.yml create studio-web-client
docker cp studio-web-client:/usr/share/nginx/html/config.js "$dir/webclient/config.js"
sed -i -e "s#http://localhost:4000/api#$(url 4000)/api#" -e "s#http://localhost:8081/auth#$(url 8081)/auth#" "$dir/webclient/config.js"
grep -q "$(url 4000)/api" "$dir/webclient/config.js" && grep -q "$(url 8081)/auth" "$dir/webclient/config.js" \
  || { echo "NOT READY: could not set the web client addresses in config.js"; exit 1; }
# The upstream database command starts postgres in the background, sleeps 5 seconds, then runs psql. On a first boot the
# official entrypoint's temporary init server shuts down during that window and psql fails ("database system is shutting
# down"), so the container exits 2. Run postgres in the foreground and let the official init directory create the
# keycloak database (POSTGRES_DB already creates studio). This only helps a FIRST boot with a fresh volume: an already
# initialized volume skips the init directory.
# The model service runs as the image's non-root user (uid 1001, gid 0) and writes to two bind-mounted folders. If Compose
# creates them they are owned by root and the service stops with "Permission denied /app/working-data/logs". Create just
# those two folders and hand them to uid 1001, gid 0. Nothing broader is changed and the service does not run as root.
mkdir -p "$dir/rasa-pro/enterprise-search-data"
docker run --rm -v "$dir/rasa-pro:/data" alpine:3.18 chown -R 1001:0 /data
mkdir -p "$dir/initdb"
printf 'CREATE DATABASE keycloak;\n' > "$dir/initdb/10-keycloak.sql"
cat > "$dir/docker-compose.override.yml" <<YAML
services:
  database:
    command: ["postgres"]
    volumes:
      - ./initdb:/docker-entrypoint-initdb.d:ro
  studio-web-client:
    volumes:
      - ./webclient/config.js:/usr/share/nginx/html/config.js:ro
  model-service:
    # The upstream model health budget (30s start, 5 retries) was shorter than a loaded 8-core start: the model became
    # healthy about two minutes after launch, but the launcher gave up at 123s. Same check, longer budget. The gate stays.
    environment:
      RASA_MODEL_SERVER_BASE_URL: $(url 8000)/talk
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 10s
      timeout: 5s
      retries: 12
      start_period: 90s
  studio-keycloak:
    environment:
      # Keycloak 26 (hostname v2): the browser-facing issuer and endpoints must be the forwarded address, not localhost.
      # Backchannel requests from the Studio containers (http://keycloak:8080/auth) keep resolving from their own host header.
      # Candidate from Keycloak's hostname and reverse-proxy docs. NOT run. Whether Studio's backend accepts a token whose
      # issuer is the public address while it talks to the internal one is unknown.
      KC_HOSTNAME: $(url 8081)/auth
      KC_HOSTNAME_BACKCHANNEL_DYNAMIC: "true"
      KC_PROXY_HEADERS: xforwarded
      KC_HTTP_ENABLED: "true"
    # The upstream health probe fetches /auth/, which now redirects to the forwarded HTTPS address, so the helper exits 1
    # and Studio's dependent services never start. Same helper and timing, pointed at the master realm discovery document,
    # which answers 200 without a redirect and exists before the backend runs. The rasa-studio realm does not: the backend
    # creates it, so probing it would deadlock a first boot. The health gate is kept, not disabled.
    healthcheck:
      test:
        [
          "CMD-SHELL",
          '[ -f /tmp/HealthCheck.java ] || echo "public class HealthCheck { public static void main(String[] args) throws java.lang.Throwable { System.exit(java.net.HttpURLConnection.HTTP_OK == ((java.net.HttpURLConnection)new java.net.URL(args[0]).openConnection()).getResponseCode() ? 0 : 1); } }" > /tmp/HealthCheck.java && java /tmp/HealthCheck.java http://localhost:8080/auth/realms/master/.well-known/openid-configuration',
        ]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 60s
  studio-backend:
    environment:
      API_URL: $(url 4000)/api
      WEB_CLIENT_URL: $(url 8080)
YAML
cd "$dir"
docker compose up -d
echo "Follow startup with: docker compose -f $dir/docker-compose.yml logs -f startup-helper"
echo "Studio: $(url 8080)   Login (Keycloak): $(url 8081)/auth/"
