"""Shared fixtures. Tests never touch the network and never need a real Gemini key.

`gemini` replaces the SDK client with a fake that records every call (model, config, history,
message) and returns scripted JSON, so the real llm.py code path (history conversion,
chats.create, parsing, error mapping) is exercised end to end.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app import app as flask_app
from malfunction import llm


class FakeResponse:
    def __init__(self, text, finish_reason="STOP", block_reason=None):
        self.text = text
        self.candidates = [SimpleNamespace(finish_reason=finish_reason)]
        self.prompt_feedback = SimpleNamespace(block_reason=block_reason) if block_reason else None


def reply_json(text="ok", code=None, links=None, image_notes="", serious=False) -> str:
    return json.dumps({"text": text, "code": code, "links": links or [],
                       "image_notes": image_notes, "serious": serious})


class FakeGemini:
    """Stands in for genai.Client: client.chats.create(...).send_message(...)."""

    def __init__(self):
        self.calls: list[dict] = []
        self.queue: list = []     # FakeResponse / str (JSON) / Exception, consumed in order
        self.chats = self

    def create(self, *, model, config=None, history=None):
        gemini = self

        class _Chat:
            def send_message(self, message):
                parts = message if isinstance(message, list) else [message]
                message = "\n".join(p for p in parts if isinstance(p, str))
                gemini.calls.append({
                    "model": model,
                    "config": config,
                    "history": [(c.role, c.parts[0].text) for c in (history or [])],
                    "message": message,
                    "images": [(p.inline_data.mime_type, p.inline_data.data)
                               for p in parts if getattr(p, "inline_data", None)],
                })
                item = gemini.queue.pop(0) if gemini.queue else None
                if isinstance(item, Exception):
                    raise item
                if isinstance(item, FakeResponse):
                    return item
                if isinstance(item, str):
                    return FakeResponse(item)
                # Default: a "dynamic" reply derived from the actual message.
                first_line = message.split("\n")[1] if "\n" in message else message
                return FakeResponse(reply_json(f"Gemini reply #{len(gemini.calls)} to: {first_line}"))

        return _Chat()

    @property
    def last(self) -> dict:
        return self.calls[-1]


@pytest.fixture(autouse=True)
def gemini(monkeypatch):
    fake = FakeGemini()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-main")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "")   # single model unless a test opts in
    monkeypatch.setattr(llm, "_client", lambda: fake)
    return fake


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


class ChatSession:
    """Drives the HTTP API the way static/app.js does (conversation id + signed history token)."""

    def __init__(self, http):
        self.http = http
        self.cid = None
        self.token = None
        self.new_chat()

    def new_chat(self):
        self.cid = self.http.post("/api/reset", json={}).get_json()["conversation_id"]
        self.token = None

    def send(self, message, **extra):
        body = {"message": message, "telemetry": {}, "conversation_id": self.cid,
                "history_token": self.token, **extra}
        res = self.http.post("/api/chat", json=body)
        data = res.get_json()
        if res.status_code == 200:
            self.cid, self.token = data["conversation_id"], data["history_token"]
        return res, data


@pytest.fixture
def chat(client):
    return ChatSession(client)
