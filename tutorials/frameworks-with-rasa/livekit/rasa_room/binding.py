"""Bind a public room conversation; authentication belongs to the application."""
from dataclasses import dataclass
import hashlib
import json

@dataclass(frozen=True)
class Conversation:
    room: str
    participant: str

    def __post_init__(self):
        if any(not isinstance(v, str) or not v.strip() or len(v)>200 for v in (self.room,self.participant)):
            raise ValueError("A configured room and participant are required")

    def sender(self) -> str:
        payload = json.dumps([self.room,self.participant],separators=(",",":"),ensure_ascii=False)
        return "livekit-public-" + hashlib.sha256(payload.encode()).hexdigest()
