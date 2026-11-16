"""Construct the maintained Sheets service from an in-memory authorized token."""
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, SecretStr


class AuthorizedToken(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True, hide_input_in_errors=True)
    client_id: str
    client_secret: SecretStr
    refresh_token: SecretStr
    token_uri: Literal["https://oauth2.googleapis.com/token"]


def google_service(secret: SecretStr):
    from google.oauth2.credentials import Credentials
    from zeo_integrations.google.sheets import GoogleSheetsService
    raw = json.loads(secret.get_secret_value())
    AuthorizedToken.model_validate(raw)
    credentials = Credentials.from_authorized_user_info(raw,
        scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return GoogleSheetsService.from_credentials(credentials)
