"""Buffered text REST boundary for an existing Rasa conversation."""
from urllib.parse import urlsplit
from aiohttp import ClientTimeout

class RasaRest:
    def __init__(self, session, endpoint):
        url=urlsplit(endpoint)
        if url.scheme not in {"http","https"} or not url.netloc or url.username or url.password:
            raise ValueError("Use a configured HTTP endpoint without URL credentials")
        self.session,self.endpoint=session,endpoint

    async def ask(self, sender: str, text: str) -> list[str]:
        async with self.session.post(self.endpoint,json={"sender":sender,"message":text},timeout=ClientTimeout(total=10)) as response:
            response.raise_for_status()
            rows=await response.json()
        if not isinstance(rows,list) or len(rows)>20:
            raise ValueError("Unusable Rasa reply envelope")
        result=[]
        for row in rows:
            if not isinstance(row,dict): raise ValueError("Unusable Rasa reply record")
            if "text" not in row: continue
            text=row["text"]
            if not isinstance(text,str) or not text.strip() or len(text)>10000:
                raise ValueError("Unusable Rasa text reply")
            result.append(text)
        return result
