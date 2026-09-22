"""OpenAI-compatible client retries 429/503 and honors Retry-After."""

from __future__ import annotations

import httpx

from rasa_skill_eval.llm.openai_compat import OpenAICompatClient, retry_wait_sec
from rasa_skill_eval.llm.types import ChatMessage


def test_retry_wait_honors_retry_after() -> None:
    """Retry-After header wins over exponential backoff."""
    response = httpx.Response(
        429,
        headers={"Retry-After": "0"},
        request=httpx.Request("POST", "http://example.test"),
    )
    assert retry_wait_sec(response, 3) == 0.0


def test_429_retries_then_succeeds(monkeypatch) -> None:
    """Two 429s then 200 is a success after retries, not a crash."""
    calls = {"n": 0}

    class FakeClient:
        """Stand-in for httpx.Client that returns scripted status codes."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            del args

        def post(
            self, url: str, headers: object = None, json: object = None, timeout: object = None
        ) -> httpx.Response:
            del headers, json, timeout
            calls["n"] += 1
            request = httpx.Request("POST", url)
            if calls["n"] < 3:
                return httpx.Response(429, headers={"Retry-After": "0"}, request=request)
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "ok"}}], "usage": {}},
                request=request,
            )

    monkeypatch.setattr("rasa_skill_eval.llm.openai_compat.httpx.Client", FakeClient)
    monkeypatch.setattr("rasa_skill_eval.llm.openai_compat.time.sleep", lambda _s: None)
    client = OpenAICompatClient(
        base_url="http://example.test/v1",
        api_key="k",
        model="m",
        max_retries=5,
    )
    result = client.complete([ChatMessage(role="user", content="hi")])
    assert result.text == "ok"
    assert calls["n"] == 3


def test_504_retries_then_succeeds(monkeypatch) -> None:
    """Gateway timeouts are retried like 429/503."""
    calls = {"n": 0}

    class FakeClient:
        """Stand-in that returns 504 then 200."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            del args

        def post(
            self, url: str, headers: object = None, json: object = None, timeout: object = None
        ) -> httpx.Response:
            del headers, json, timeout
            calls["n"] += 1
            request = httpx.Request("POST", url)
            if calls["n"] == 1:
                return httpx.Response(504, request=request)
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "ok"}}], "usage": {}},
                request=request,
            )

    monkeypatch.setattr("rasa_skill_eval.llm.openai_compat.httpx.Client", FakeClient)
    monkeypatch.setattr("rasa_skill_eval.llm.openai_compat.time.sleep", lambda _s: None)
    client = OpenAICompatClient(
        base_url="http://example.test/v1",
        api_key="k",
        model="m",
        max_retries=5,
    )
    result = client.complete([ChatMessage(role="user", content="hi")])
    assert result.text == "ok"
    assert calls["n"] == 2


def test_400_is_not_retried(monkeypatch) -> None:
    """Client errors other than 429/503 fail immediately."""
    calls = {"n": 0}

    class FakeClient:
        """Stand-in that always returns HTTP 400."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            del args

        def post(
            self, url: str, headers: object = None, json: object = None, timeout: object = None
        ) -> httpx.Response:
            del headers, json, timeout
            calls["n"] += 1
            return httpx.Response(400, request=httpx.Request("POST", url))

    monkeypatch.setattr("rasa_skill_eval.llm.openai_compat.httpx.Client", FakeClient)
    client = OpenAICompatClient(
        base_url="http://example.test/v1",
        api_key="k",
        model="m",
        max_retries=5,
    )
    try:
        client.complete([ChatMessage(role="user", content="hi")])
    except httpx.HTTPStatusError:
        pass
    else:
        raise AssertionError("expected HTTPStatusError")
    assert calls["n"] == 1


def test_410_is_not_retried(monkeypatch) -> None:
    """EOL NIM models fail immediately instead of retrying."""
    calls = {"n": 0}

    class FakeClient:
        """Stand-in that always returns HTTP 410."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            del args

        def post(
            self, url: str, headers: object = None, json: object = None, timeout: object = None
        ) -> httpx.Response:
            del headers, json, timeout
            calls["n"] += 1
            return httpx.Response(410, request=httpx.Request("POST", url))

    monkeypatch.setattr("rasa_skill_eval.llm.openai_compat.httpx.Client", FakeClient)
    client = OpenAICompatClient(
        base_url="http://example.test/v1",
        api_key="k",
        model="m",
        max_retries=5,
    )
    try:
        client.complete([ChatMessage(role="user", content="hi")])
    except httpx.HTTPStatusError:
        pass
    else:
        raise AssertionError("expected HTTPStatusError")
    assert calls["n"] == 1


def test_nonpositive_overall_timeout_is_unlimited() -> None:
    """Judge waits: overall_timeout_sec <= 0 is treated as unbounded."""
    client = OpenAICompatClient(
        base_url="http://example.test/v1",
        api_key="k",
        model="m",
        overall_timeout_sec=0.0,
    )
    assert client.overall_timeout_sec > 1e6


def test_retry_after_is_capped() -> None:
    """An unbounded Retry-After header cannot stall the run."""
    response = httpx.Response(
        429,
        headers={"Retry-After": "9999"},
        request=httpx.Request("POST", "http://example.test"),
    )
    assert retry_wait_sec(response, 0, cap_sec=30.0) == 30.0


def test_rate_limit_circuit_trips(monkeypatch) -> None:
    """Repeated exhausted 429 sequences open the run-level breaker."""
    from rasa_skill_eval.llm.openai_compat import RateLimitCircuit, RateLimitTripped

    circuit = RateLimitCircuit(trip_after=1)

    class FakeClient:
        """Always 429."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            del args

        def post(
            self, url: str, headers: object = None, json: object = None, timeout: object = None
        ) -> httpx.Response:
            del headers, json, timeout
            return httpx.Response(
                429,
                headers={"Retry-After": "0"},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr("rasa_skill_eval.llm.openai_compat.httpx.Client", FakeClient)
    monkeypatch.setattr("rasa_skill_eval.llm.openai_compat.time.sleep", lambda _s: None)
    client = OpenAICompatClient(
        base_url="http://example.test/v1",
        api_key="k",
        model="m",
        max_retries=0,
        circuit=circuit,
        overall_timeout_sec=5.0,
    )
    try:
        client.complete([ChatMessage(role="user", content="hi")])
    except httpx.HTTPStatusError:
        pass
    else:
        raise AssertionError("expected HTTPStatusError")
    assert circuit.tripped is True
    client2 = OpenAICompatClient(
        base_url="http://example.test/v1",
        api_key="k",
        model="m",
        circuit=circuit,
    )
    try:
        client2.complete([ChatMessage(role="user", content="hi")])
    except RateLimitTripped:
        return
    raise AssertionError("expected RateLimitTripped")
