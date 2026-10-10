import asyncio
import logging

import httpx

from config import RASA_REST_URL
from services.i18n import LLM_EMPTY_RESPONSE, LLM_RETRYING, pick

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(300.0)
_MAX_RETRIES = 3
_RETRY_DELAYS = [2.0, 4.0, 8.0]

_CONTEXT_TEMPLATE = """[ANALYSIS CONTEXT]
{context}
[/ANALYSIS CONTEXT]

User message: {message}"""

_LANG_NAMES = {"fr": "French", "en": "English", "de": "German", "es": "Spanish"}

_LANG_TEMPLATE = """[LANGUAGE CONTEXT]
The user's interface is in {language}. ALWAYS reply in {language}.
[/LANGUAGE CONTEXT]

User message: {message}"""


def _extract_texts(responses: list) -> str:
    texts = [entry.get("text", "") for entry in responses if entry.get("text")]
    return "\n\n".join(texts).strip()


async def chat_with_rasa(
    message: str,
    sender_id: str = "web",
    context: str = "",
    lang: str = "fr",
) -> str:
    """Proxy a chat message to the Rasa Mantle REST webhook.

    The analysis context currently displayed on the user's screen is injected
    into the message body so the agent can answer from it without calling
    tools again. Transient provider errors (429 rate-limit, 502/503/504) are
    retried with exponential backoff before falling back to a friendly hint.
    """
    text = _CONTEXT_TEMPLATE.format(context=context, message=message) if context else message
    if lang in _LANG_NAMES:
        text = _LANG_TEMPLATE.format(language=_LANG_NAMES[lang], message=text)
    payload = {"sender": sender_id or "web", "message": text}

    async def _post(client: httpx.AsyncClient) -> str:
        r = await client.post(f"{RASA_REST_URL}/webhooks/rest/webhook", json=payload)
        r.raise_for_status()
        return _extract_texts(r.json())

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                out = await _post(client)
                if out:
                    return out
                logger.warning("Rasa returned empty text on attempt %d", attempt + 1)
            except httpx.HTTPStatusError as e:
                last_exc = e
                status = e.response.status_code
                if status in (429, 502, 503, 504):
                    delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                    logger.warning(
                        "Rasa returned %d on attempt %d/%d — retrying in %.1fs",
                        status, attempt + 1, _MAX_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
            except httpx.RequestError as e:
                last_exc = e
                delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                logger.warning(
                    "Rasa connection error on attempt %d/%d — retrying in %.1fs: %s",
                    attempt + 1, _MAX_RETRIES, delay, e,
                )
                await asyncio.sleep(delay)

        logger.error("All %d attempts to reach Rasa failed", _MAX_RETRIES)
        if isinstance(last_exc, httpx.HTTPStatusError) and last_exc.response.status_code == 429:
            return pick(LLM_RETRYING, lang)
        return pick(LLM_EMPTY_RESPONSE, lang)
