"""Conversation memory, kept apart from the malfunction state, with no server-side storage.

Why not a dict in server memory? Serverless hosts (Vercel, Cloud Run, ...) run many short-lived
instances, so anything kept in process memory randomly disappears. Why not the Flask session
cookie? It's capped at ~4 KB, too small for a transcript.

So the server SIGNS the transcript and hands it to the browser as an opaque `history_token`,
which the browser sends back with the next message:

    token = sign({"o": owner, "c": conversation_id, "m": [messages...]})

* The browser can't forge or edit it (HMAC with SECRET_KEY): it's server-authored history,
  not "whatever the page happens to display".
* `owner` is a random id in the signed session cookie, so a token only works for the visitor
  it was issued to; `conversation_id` must match too, so different chats (or tabs) never mix.
* Tokens expire after TOKEN_MAX_AGE; an expired or invalid token just starts a fresh memory.

The token is signed, not encrypted: it holds the user's own chat, which they can already see.
"""
from __future__ import annotations

import re
import secrets
from typing import Any

from itsdangerous import BadData, URLSafeTimedSerializer

ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")

MAX_STORED_MESSAGES = 24        # per conversation (the window sent to Gemini is set in llm.py)
MAX_STORED_CHARS = 24_000       # keeps the token comfortably small
TOKEN_MAX_AGE = 24 * 60 * 60    # seconds
_SALT = "doubt.ai/conversation-history"


def new_id() -> str:
    return secrets.token_hex(16)


def valid_id(value: Any) -> bool:
    return isinstance(value, str) and bool(ID_PATTERN.match(value))


def _serializer(secret_key: str | bytes) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt=_SALT)   # zlib-compresses when it helps


def _size(message: dict[str, Any]) -> int:
    code = message.get("code") or {}
    return len(str(message.get("text", ""))) + len(str(code.get("content", "")))


def trim(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the most recent messages within the storage caps, starting on a user turn."""
    kept = list(messages[-MAX_STORED_MESSAGES:])
    while kept and sum(map(_size, kept)) > MAX_STORED_CHARS:
        kept.pop(0)
    while kept and kept[0].get("role") != "user":
        kept.pop(0)
    return kept


def issue(secret_key: str | bytes, owner: str, cid: str, messages: list[dict[str, Any]]) -> str:
    return _serializer(secret_key).dumps({"o": owner, "c": cid, "m": trim(messages)})


def load(secret_key: str | bytes, owner: str, cid: str, token: Any) -> tuple[list[dict[str, Any]], bool]:
    """(messages, ok). No token = a brand-new conversation (ok). A bad, expired or foreign
    token returns ([], False) so the caller can tell the user the memory was reset."""
    if token in (None, ""):
        return [], True
    if not isinstance(token, str):
        return [], False
    try:
        data = _serializer(secret_key).loads(token, max_age=TOKEN_MAX_AGE)
    except BadData:
        return [], False
    if not isinstance(data, dict) or data.get("o") != owner or data.get("c") != cid:
        return [], False
    messages = data.get("m")
    if not isinstance(messages, list):
        return [], False
    return [m for m in messages if isinstance(m, dict) and m.get("role") in ("user", "model")], True


def drop_last_exchange(messages: list[dict[str, Any]], user_text: str) -> list[dict[str, Any]]:
    """For "Regenerate": remove the last user message (and the replies after it) if it matches."""
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            return messages[:i] if messages[i].get("text") == user_text else messages
    return messages
