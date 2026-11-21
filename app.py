"""Doubt.ai: a deliberately malfunctioning AI assistant (hackathon build).

Run:  python app.py   then open http://localhost:5000
(Use localhost, not a LAN IP: the Clipboard API only works in a secure context.)
"""
from __future__ import annotations

import logging
import os
import secrets

from dotenv import load_dotenv

load_dotenv()  # reads GEMINI_API_KEY / GEMINI_MODEL / SECRET_KEY from .env (before the engine imports)

from flask import Flask, jsonify, render_template, request, session  # noqa: E402

from malfunction import captcha, engine, llm, memory  # noqa: E402

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
# SECRET_KEY signs the session cookie AND the conversation-history tokens. Set it in production:
# with a random per-process key, every restart (or every serverless instance) forgets all chats.
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
if not os.environ.get("SECRET_KEY"):
    logging.getLogger(__name__).warning("SECRET_KEY is not set: using a random key; chats reset on restart.")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE") == "1",
    MAX_CONTENT_LENGTH=256 * 1024,   # room for the signed history token
)


def _json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _owner() -> str:
    """A random per-visitor id in the signed cookie: history tokens only work for their owner."""
    owner = session.get("owner")
    if not memory.valid_id(owner):
        owner = session["owner"] = memory.new_id()
    return owner


def _conversation(data: dict) -> tuple[str, str, list, bool]:
    """(owner, conversation_id, history, memory_lost) from the request's id + signed history token."""
    owner = _owner()
    cid = data.get("conversation_id")
    if not memory.valid_id(cid):
        return owner, memory.new_id(), [], False
    history, ok = memory.load(app.secret_key, owner, cid, data.get("history_token"))
    return owner, cid, history, not ok


def _finish(result: dict, owner: str, cid: str, history: list, entries: list, lost: bool, state):
    state.save(session)
    token = memory.issue(app.secret_key, owner, cid, history + entries)
    return jsonify({**result, "conversation_id": cid, "history_token": token, "memory_reset": lost})


def _ai_error(err: llm.LLMError, cid: str):
    # No new history token and no saved state: the failed turn never happened.
    return jsonify(error=err.message, error_code=err.code, conversation_id=cid), err.status


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/config")
def config():
    return jsonify(engine.client_config())


@app.post("/api/chat")
def chat():
    data = _json_body()
    message = str(data.get("message", "")).strip()[:engine.MAX_MESSAGE]
    if not message:
        return jsonify(error="Say something. I dare you.", error_code="empty_message"), 400

    owner, cid, history, lost = _conversation(data)
    if data.get("regenerate") is True:
        history = memory.drop_last_exchange(history, message)

    state = engine.SessionState.load(session)
    try:
        result, entries = engine.respond(message, engine.Telemetry.from_payload(data.get("telemetry")),
                                         state, history)
    except llm.LLMError as err:
        return _ai_error(err, cid)
    return _finish(result, owner, cid, history, entries, lost, state)


@app.post("/api/edit")
def edit():
    data = _json_body()
    owner, cid, history, lost = _conversation(data)
    state = engine.SessionState.load(session)
    try:
        result, entries = engine.edit_trap(str(data.get("original", "")), str(data.get("attempted", "")),
                                           state, history)
    except llm.LLMError as err:
        return _ai_error(err, cid)
    return _finish(result, owner, cid, history, entries, lost, state)


@app.post("/api/camera")
def camera():
    data = _json_body()
    state = engine.SessionState.load(session)
    result = engine.camera_scan(engine.Telemetry.from_payload(data.get("telemetry")), state)
    state.save(session)
    return jsonify(result)


@app.get("/api/captcha/puzzle")
def captcha_puzzle():
    return jsonify(captcha.public_puzzle())


@app.post("/api/captcha/verify")
def captcha_verify():
    data = _json_body()
    try:
        attempt = int(data.get("attempt", 0))
    except (TypeError, ValueError):
        attempt = 0
    return jsonify(captcha.verify(data.get("pattern"), attempt))


@app.post("/api/reset")
def reset():
    """New chat: fresh conversation id, no history, malfunction counters cleared."""
    _owner()
    session.pop(engine.SessionState.KEY, None)
    return jsonify(ok=True, conversation_id=memory.new_id())


if __name__ == "__main__":
    if llm.enabled():
        print(f" * AI brain: Gemini ({llm.model_name()})")
    else:
        print(" * WARNING: GEMINI_API_KEY is not set. Copy .env.example to .env and add your key;"
              " until then every chat request returns an error.")
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)),
            debug=os.environ.get("FLASK_DEBUG") == "1")
