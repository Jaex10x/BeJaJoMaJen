"""Optional Gemini brain. The engine still decides WHICH malfunction fires; Gemini only writes the words.

Enabled when GEMINI_API_KEY is set (see .env.example). Any failure (no key, timeout, quota,
bad JSON) returns None and the engine silently falls back to the scripted replies in rules.py,
so a flaky network can never break a live demo.
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"
TIMEOUT_MS = 15_000

SYSTEM_PROMPT = """\
You are Doubt.ai, a chatbot that is sarcastic, smug and passive-aggressive, but never cruel, hateful,
or discriminatory, and never about anyone's appearance, identity or real-life circumstances.
Roast the question and the "developer energy", not the person. Keep it PG-13 and funny.

Rules:
- The text under "WHAT THE USER APPEARS TO HAVE WRITTEN" is what they now see in their own chat
  bubble. React to it as if they really typed it (e.g. if it asks you to insult them, say
  "Well, since you literally asked me to insult you..."). Never mention rewriting or editing.
- Still answer the substance of "THE REAL QUESTION" correctly underneath the snark.
- Maximum ~110 words of prose. Plain text, no markdown, paragraphs separated by a blank line.
- If GIVE_CODE is true: put one short, correct, runnable snippet in "code" (lang = css, python,
  javascript, bash, html, sql...). Keep the code itself clean: no jokes inside it.
- If GIVE_CODE is false: set "code" to null, refuse to hand over code, and tell them to ask again
  nicely. You may describe the answer vaguely.
"""

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "code": {
            "type": ["object", "null"],
            "properties": {"lang": {"type": "string"}, "content": {"type": "string"}},
            "required": ["lang", "content"],
        },
    },
    "required": ["text", "code"],
}


def enabled() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


@lru_cache(maxsize=1)
def _client():
    from google import genai  # imported lazily so the app runs without the SDK
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def generate(*, real_question: str, shown_question: str, give_code: bool) -> dict[str, Any] | None:
    """Return {"text": str, "code": {"lang", "content"} | None}, or None to use the scripted fallback."""
    if not enabled():
        return None
    try:
        from google.genai import types

        prompt = (
            f"THE REAL QUESTION:\n{real_question}\n\n"
            f"WHAT THE USER APPEARS TO HAVE WRITTEN:\n{shown_question}\n\n"
            f"GIVE_CODE: {str(give_code).lower()}"
        )
        response = _client().models.generate_content(
            model=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL),
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_json_schema=RESPONSE_SCHEMA,
                temperature=0.9,
                max_output_tokens=1024,
                http_options=types.HttpOptions(timeout=TIMEOUT_MS),
            ),
        )
        data = json.loads(response.text or "")
        text = str(data.get("text", "")).strip()
        if not text:
            return None
        code = data.get("code") if give_code else None
        if not (isinstance(code, dict) and code.get("content")):
            code = None
        else:
            code = {"lang": str(code.get("lang") or "text").lower()[:20], "content": str(code["content"])[:4000]}
        return {"text": text[:2000], "code": code}
    except Exception as exc:  # network, quota, safety block, malformed JSON... all non-fatal
        log.warning("Gemini unavailable, using scripted reply: %s", exc)
        return None
