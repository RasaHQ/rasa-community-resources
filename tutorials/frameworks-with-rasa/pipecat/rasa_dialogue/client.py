"""Bounded text-only Rasa REST adapter; sender belongs to the connection."""

from urllib.parse import urlsplit
import aiohttp


class RasaRestClient:
    def __init__(self, session: aiohttp.ClientSession, endpoint: str, sender: str):
        url = urlsplit(endpoint)
        if (
            url.scheme not in {"http", "https"}
            or not url.netloc
            or url.username
            or url.password
        ):
            raise ValueError("Use a configured HTTP endpoint without URL credentials")
        if not isinstance(sender, str) or not sender.strip() or len(sender) > 200:
            raise ValueError("Use a configured connection sender")
        self.session, self.endpoint, self.sender = session, endpoint, sender

    async def __call__(self, text: str) -> list[str]:
        async with self.session.post(
            self.endpoint,
            json={"sender": self.sender, "message": text},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            response.raise_for_status()
            result = await response.json()
        if not isinstance(result, list) or len(result) > 20:
            raise ValueError("Expected a bounded Rasa response list")
        replies = []
        for item in result:
            if not isinstance(item, dict):
                raise ValueError("Expected Rasa message records")
            text = item.get("text")
            if text is None:
                continue
            if not isinstance(text, str) or not text.strip() or len(text) > 10000:
                raise ValueError("Expected bounded text replies")
            replies.append(text)
        return replies
