"""Scripted HTTP replies through the real SDK; these are not model predictions."""
import json
import httpx2
from .selector import MODEL


def scripted_transport(choice="A-CURRENT", before_reply=None):
    requests = []

    def reply(request):
        body = json.loads(request.content)
        requests.append(body)
        if before_reply:
            before_reply()
        keys = body["questions"]["account"]["criteria"]
        selected = choice if choice in keys else "ask_customer"
        probabilities = {key: float(key == selected) for key in keys}
        return httpx2.Response(200, json={"model": MODEL, "usage": {"input_tokens": None, "output_tokens": None},
            "answers": {"account": {"type": "choice", "choice": selected,
                "confidence": 1.0, "probabilities": probabilities}}})

    return httpx2.MockTransport(reply), requests
