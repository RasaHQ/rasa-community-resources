"""Google Desktop OAuth sign-in by pasting the callback URL into Codespaces.

Based on the reviewed shop paste-back example. No listener, laptop command,
credential file, browser automation or public callback endpoint is used.
"""
from __future__ import annotations

import hmac
import json
import os
import sys
from typing import Literal
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

SCOPE = "https://www.googleapis.com/auth/spreadsheets"
REDIRECT = "http://127.0.0.1:8766/"


class DesktopClient(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, hide_input_in_errors=True)
    client_id: str
    client_secret: SecretStr
    auth_uri: Literal["https://accounts.google.com/o/oauth2/auth",
                      "https://accounts.google.com/o/oauth2/v2/auth"]
    token_uri: Literal["https://oauth2.googleapis.com/token"]

    @field_validator("client_id")
    @classmethod
    def google_client_id(cls, value):
        if not value.endswith(".apps.googleusercontent.com") or any(c.isspace() for c in value):
            raise ValueError("Use an unmodified Google Desktop OAuth client")
        return value

    @field_validator("client_secret")
    @classmethod
    def nonempty_secret(cls, value):
        if not value.get_secret_value():
            raise ValueError("The Desktop client secret is missing")
        return value


class DesktopConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, hide_input_in_errors=True)
    installed: DesktopClient


def client_config(value):
    client = DesktopConfig.model_validate_json(value).installed
    # The SDK needs the clear secret in memory; never log this mapping.
    return {"installed": client.model_dump() | {
        "client_secret": client.client_secret.get_secret_value()}}


def callback_code(address, state):
    address = address.strip()
    if len(address) > 8192 or any(c.isspace() for c in address):
        raise ValueError("Invalid callback address")
    url = urlsplit(address)
    if (url.scheme != "http" or url.netloc != "127.0.0.1:8766"
            or url.path != "/" or url.fragment):
        raise ValueError("Unexpected callback address")
    query = parse_qs(url.query, keep_blank_values=True, max_num_fields=16)
    states = query.get("state", [])
    if len(states) != 1 or not hmac.compare_digest(states[0].encode(), state.encode()):
        raise ValueError("The consent state did not match")
    codes = query.get("code", [])
    if ("error" in query or "error_description" in query or len(codes) != 1
            or not codes[0] or any(c.isspace() for c in codes[0])):
        raise ValueError("Consent was not granted")
    return codes[0]


def main():
    from google_auth_oauthlib.flow import InstalledAppFlow

    try:
        config = client_config(os.environ["GOOGLE_CLIENT_SECRETS_JSON"])
        flow = InstalledAppFlow.from_client_config(config, [SCOPE],
            redirect_uri=REDIRECT, autogenerate_code_verifier=True)
        url, state = flow.authorization_url(prompt="consent", access_type="offline")
        print("Open this link in your browser and allow access:", flush=True)
        print(url, flush=True)
        print("The browser will show that 127.0.0.1 cannot connect. That is expected.", flush=True)
        print("Copy the whole address from its address bar and paste it into this Codespace terminal.", flush=True)
        code = callback_code(input("Address: "), state)
        flow.fetch_token(code=code, timeout=30)
        credentials = flow.credentials
        if not credentials.refresh_token:
            raise ValueError("Google did not return an offline refresh token")
        token_json = credentials.to_json()
        if not isinstance(json.loads(token_json), dict):
            raise ValueError("Invalid token response")
        print("Save the following one line as GOOGLE_TOKEN_JSON in your Codespace secrets.")
        print("Give it access to this repository, then restart or rebuild the Codespace.")
        print("Keep this terminal private and clear it after saving the secret.")
        print(token_json, flush=True)
    except (Exception, KeyboardInterrupt):
        # Exceptions can contain codes or client secrets; never print their text.
        print("Google sign-in did not complete. Check the Desktop client secret and repeat sign-in. No credential file was written.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
