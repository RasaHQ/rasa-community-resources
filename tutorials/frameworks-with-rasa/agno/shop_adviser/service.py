"""A fresh native agent per request retains memory in the application database."""

from pathlib import Path
from threading import Lock

from shop_adviser.adviser import (
    advise_for_demo_sender,
    create_adviser,
    seed_public_preference,
)
from shop_adviser.scope_binding import resolve_demo_scope


class AdviserService:
    def __init__(self, db_path: Path, model_factory):
        self.db_path = db_path
        self.model_factory = model_factory
        self._lock = Lock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        seed_public_preference(db_path)

    def answer(self, sender_id: str, question: str) -> dict:
        if resolve_demo_scope(sender_id) is None:
            return {"status": "unknown_demo_sender"}
        if (
            not isinstance(question, str)
            or not question.strip()
            or len(question) > 1000
        ):
            return {"status": "invalid_question"}
        # A cancelled async caller can leave this native thread running. Keep
        # its serialization lock until the thread, not its caller, has finished.
        with self._lock:
            try:
                agent = create_adviser(self.db_path, self.model_factory())
                return advise_for_demo_sender(agent, sender_id, question)
            except Exception:
                return {"status": "advice_unavailable"}
