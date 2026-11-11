"""Pydantic request models shared by the FastAPI routers.

These schemas mirror the payloads sent by the frontend (``src/services/api.ts``)
and by the Rasa skills (``skills/*/tools.py``):

* ``SiteRequest``          — ``POST /api/analysis/site``
* ``RegionCompareRequest`` — ``POST /api/analysis/compare``
* ``ChatMessage``          — ``POST /api/llm/chat``
"""

from enum import Enum

from pydantic import BaseModel, Field


class TemporalResolution(str, Enum):
    """Temporal resolution accepted by the weather/analysis services."""

    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"
    CLIMATOLOGY = "climatology"


class SiteRequest(BaseModel):
    """A single-site solar + wind analysis request."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    start_date: str = Field(..., pattern=r"^\d{8}$")
    end_date: str = Field(..., pattern=r"^\d{8}$")
    resolution: TemporalResolution = TemporalResolution.HOURLY
    solar_config: dict = Field(default_factory=dict)
    wind_config: dict = Field(default_factory=dict)
    site_context: dict = Field(default_factory=dict)
    lang: str = "fr"


class RegionCompareRequest(BaseModel):
    """Compare two to five sites in a single request."""

    sites: list[SiteRequest] = Field(..., min_length=2, max_length=5)


class ChatMessage(BaseModel):
    """A chat turn proxied to the Rasa agent by ``/api/llm/chat``."""

    message: str
    history: list[dict] = Field(default_factory=list)
    context: str = ""
    lang: str = "fr"
    sender_id: str = "web"
