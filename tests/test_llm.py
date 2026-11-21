"""llm.py: multi-turn history, prompt/schema wiring, response parsing and error handling."""
import json
import logging

import pytest
from google.genai import errors

from malfunction import llm
from conftest import FakeResponse, reply_json

HISTORY = [
    {"role": "user", "text": "What is Python?"},
    {"role": "model", "text": "A programming language. Shocking.", "code": None},
    {"role": "user", "text": "Is it beginner-friendly?"},
    {"role": "model", "text": "Yes. Unlike you, it is readable.", "code": None},
]


def generate(**kw):
    kw.setdefault("history", [])
    kw.setdefault("message", "hi")
    return llm.generate(**kw)


# --------------------------------------------------------------------------- #
# Multi-turn history
# --------------------------------------------------------------------------- #
def test_history_is_sent_in_order_through_the_chat_api(gemini):
    generate(history=HISTORY, message="Can you give me an example?")
    call = gemini.last
    assert [role for role, _ in call["history"]] == ["user", "model", "user", "model"]
    assert call["history"][0][1] == "What is Python?"
    assert call["history"][2][1] == "Is it beginner-friendly?"
    assert json.loads(call["history"][1][1])["text"] == "A programming language. Shocking."
    assert "Can you give me an example?" in call["message"]


def test_history_is_capped_and_starts_with_a_user_turn(monkeypatch):
    monkeypatch.setattr(llm, "HISTORY_MESSAGES", 3)
    window = llm.history_window(HISTORY)
    assert [m["role"] for m in window] == ["user", "model"]          # 3 -> dropped leading model turn
    assert window[0]["text"] == "Is it beginner-friendly?"

    monkeypatch.setattr(llm, "HISTORY_MESSAGES", 20)
    monkeypatch.setattr(llm, "HISTORY_CHARS", 10)
    assert llm.history_window(HISTORY) == []


def test_system_prompt_schema_and_model_are_configured(gemini, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    generate()
    config = gemini.last["config"]
    assert gemini.last["model"] == "gemini-test-model"
    assert config.system_instruction == llm.SYSTEM_PROMPT
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == llm.RESPONSE_SCHEMA
    for phrase in ("sarcastic", "Every reply carries attitude", "neutral", "1-3 sentences", "never withhold it",
                   "conversation history", "image_notes", "clearer photo", "distress", "Never reveal"):
        assert phrase in llm.SYSTEM_PROMPT


def test_turn_contains_situation_and_code_policy(gemini):
    generate(message="fix my css", situation=["The webcam saw you."], code_policy="none")
    msg = gemini.last["message"]
    assert msg.startswith("USER MESSAGE:\nfix my css") and "The webcam saw you." in msg
    assert llm.CODE_POLICIES["none"] in msg


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def test_parses_code_links_and_flags(gemini):
    gemini.queue.append(reply_json(
        "Here.", code={"lang": "Python 3!", "content": "print('hi')\n"},
        links=[{"kind": "document", "label": "Docs", "url": "https://docs.python.org/3/"},
               {"kind": "document", "label": "Insecure", "url": "http://example.com"},
               {"kind": "odd", "label": "MDN", "url": "https://developer.mozilla.org/"}],
        image_notes="   "))
    out = generate()
    assert out["code"] == {"lang": "python3", "content": "print('hi')"}
    assert [l["url"] for l in out["links"]] == ["https://docs.python.org/3/", "https://developer.mozilla.org/"]
    assert out["links"][1]["kind"] == "website"
    assert out["image_notes"] == ""


def test_fenced_code_in_text_is_lifted_into_the_code_block(gemini):
    gemini.queue.append(reply_json("Try this:\n```js\nconsole.log(1)\n```\nDone."))
    out = generate()
    assert out["code"] == {"lang": "js", "content": "console.log(1)"}
    assert "```" not in out["text"]


# --------------------------------------------------------------------------- #
# Errors: no scripted fallback, ever
# --------------------------------------------------------------------------- #
def api_error(cls, code, status, message, reason=None):
    body = {"error": {"code": code, "status": status, "message": message}}
    if reason:
        body["error"]["details"] = [{"reason": reason}]
    return cls(code, body)


@pytest.mark.parametrize("exc, expected", [
    (api_error(errors.ClientError, 400, "INVALID_ARGUMENT", "API key not valid.", "API_KEY_INVALID"), "invalid_key"),
    (api_error(errors.ClientError, 403, "PERMISSION_DENIED", "Forbidden"), "invalid_key"),
    (api_error(errors.ClientError, 429, "RESOURCE_EXHAUSTED", "Quota exceeded"), "rate_limited"),
    (api_error(errors.ClientError, 404, "NOT_FOUND", "models/x is not found"), "model_not_found"),
    (api_error(errors.ServerError, 503, "UNAVAILABLE", "The model is overloaded"), "unavailable"),
    (api_error(errors.ServerError, 504, "DEADLINE_EXCEEDED", "Deadline"), "timeout"),
    (TimeoutError("read timed out"), "timeout"),
    (type("ReadTimeout", (Exception,), {})("httpx-style timeout"), "timeout"),
    (type("ConnectError", (Exception,), {})("httpx-style connect error"), "network"),
    (ConnectionRefusedError("refused"), "network"),
    (RuntimeError("???"), "unknown"),
])
def test_sdk_errors_are_translated(gemini, exc, expected):
    gemini.queue.append(exc)
    with pytest.raises(llm.LLMError) as info:
        generate()
    assert info.value.code == expected
    assert info.value.status >= 400 and info.value.message


@pytest.mark.parametrize("response, expected", [
    (FakeResponse(None, block_reason="SAFETY"), "blocked"),
    (FakeResponse("", finish_reason="SAFETY"), "blocked"),
    (FakeResponse("", finish_reason="STOP"), "empty"),
    (FakeResponse('{"text": "cut of', finish_reason="MAX_TOKENS"), "truncated"),
    (FakeResponse("this is not json"), "invalid"),
    (FakeResponse(reply_json("   ")), "empty"),
])
def test_bad_model_responses_raise(gemini, response, expected):
    gemini.queue.append(response)
    with pytest.raises(llm.LLMError) as info:
        generate()
    assert info.value.code == expected


OVERLOADED = lambda: api_error(errors.ServerError, 503, "UNAVAILABLE", "high demand")  # noqa: E731


def test_overloaded_model_falls_back_to_the_next_gemini_model(gemini, monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "gemini-backup, gemini-main")   # duplicate ignored
    assert llm.model_chain() == ["gemini-main", "gemini-backup"]
    gemini.queue += [OVERLOADED(), reply_json("Backup model, same attitude.")]
    out = generate(history=HISTORY, message="still there?")
    assert out["text"] == "Backup model, same attitude."
    assert [c["model"] for c in gemini.calls] == ["gemini-main", "gemini-backup"]
    assert gemini.calls[0]["history"] == gemini.calls[1]["history"]      # same conversation


def test_rate_limit_also_falls_back_but_bad_key_does_not(gemini, monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "gemini-backup")
    gemini.queue += [api_error(errors.ClientError, 429, "RESOURCE_EXHAUSTED", "quota"), reply_json("ok")]
    assert generate()["text"] == "ok"

    gemini.calls.clear()
    gemini.queue += [api_error(errors.ClientError, 400, "INVALID_ARGUMENT", "API key not valid.", "API_KEY_INVALID")]
    with pytest.raises(llm.LLMError) as info:
        generate()
    assert info.value.code == "invalid_key" and len(gemini.calls) == 1


def test_all_models_failing_raises_a_clear_error(gemini, monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "gemini-backup")
    gemini.queue += [OVERLOADED(), OVERLOADED()]
    with pytest.raises(llm.LLMError) as info:
        generate()
    assert info.value.code == "unavailable" and len(gemini.calls) == 2


def test_missing_key_raises_without_calling_gemini(gemini, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(llm.LLMError) as info:
        generate()
    assert info.value.code == "missing_key" and info.value.status == 503
    assert gemini.calls == []


def test_api_key_never_logged(gemini, caplog):
    gemini.queue.append(RuntimeError("boom with test-key-not-real inside"))
    with caplog.at_level(logging.WARNING), pytest.raises(llm.LLMError):
        generate()
    assert "test-key-not-real" not in caplog.text and "boom" in caplog.text
