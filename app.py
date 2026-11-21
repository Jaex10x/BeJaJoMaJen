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

from malfunction import captcha, engine, llm  # noqa: E402

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=64 * 1024,
)


def _json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/config")
def config():
    return jsonify(engine.client_config())


@app.post("/api/chat")
def chat():
    data = _json_body()
    message = str(data.get("message", "")).strip()
    if not message:
        return jsonify(error="Say something. I dare you."), 400

    state = engine.SessionState.load(session)
    result = engine.respond(message, engine.Telemetry.from_payload(data.get("telemetry")), state)
    state.save(session)
    return jsonify(result)


@app.post("/api/edit")
def edit():
    data = _json_body()
    state = engine.SessionState.load(session)
    result = engine.edit_trap(str(data.get("original", "")), str(data.get("attempted", "")), state)
    state.save(session)
    return jsonify(result)


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
    session.pop(engine.SessionState.KEY, None)
    return jsonify(ok=True)


if __name__ == "__main__":
    print(f" * AI brain: {'Gemini (' + os.environ.get('GEMINI_MODEL', llm.DEFAULT_MODEL) + ')' if llm.enabled() else 'scripted (set GEMINI_API_KEY in .env to use Gemini)'}")
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)),
            debug=os.environ.get("FLASK_DEBUG") == "1")
