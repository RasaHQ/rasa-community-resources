"""Environment-only credentials and explicit local run settings."""
from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    spreadsheet_id: str = Field(pattern=r"^[A-Za-z0-9_-]{20,120}$")
    operator_chat_id: int = Field(gt=0)
    telegram_token: SecretStr
    google_token_json: SecretStr
    state_directory: Path
    currency: str = Field(default="MXN", pattern=r"^[A-Z]{3}$")
    max_turns: int = Field(default=30, ge=1, le=100)

    @classmethod
    def environment(cls):
        names = {"spreadsheet_id": "SHOP_SHEET_ID", "operator_chat_id": "SHOP_OPERATOR_CHAT_ID",
                 "telegram_token": "TELEGRAM_BOT_TOKEN", "google_token_json": "GOOGLE_TOKEN_JSON"}
        missing = [name for name in names.values() if not os.environ.get(name)]
        if missing:
            raise ValueError("Missing Codespace secrets: " + ", ".join(missing))
        try:
            return cls(spreadsheet_id=os.environ[names["spreadsheet_id"]],
                operator_chat_id=int(os.environ[names["operator_chat_id"]]),
                telegram_token=SecretStr(os.environ[names["telegram_token"]]),
                google_token_json=SecretStr(os.environ[names["google_token_json"]]),
                state_directory=Path(os.environ.get("SHOP_STATE_DIR", ".state")).absolute())
        except Exception:
            raise ValueError("Invalid shop settings; inspect the configured secret names and local paths") from None
