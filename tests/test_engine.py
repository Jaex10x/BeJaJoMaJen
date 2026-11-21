"""The malfunction mechanics still fire, and Gemini (faked) writes every conversational reply."""
import random

import pytest

from malfunction import captcha, engine, rules
from conftest import reply_json


def rng():
    return random.Random(42)


def respond(message, state=None, telemetry=None, history=None):
    return engine.respond(message, telemetry or engine.Telemetry(), state or engine.SessionState(),
                          history or [], rng())


# --------------------------------------------------------------------------- #
# Gemini is the brain
# --------------------------------------------------------------------------- #
def test_reply_text_comes_from_gemini(gemini):
    gemini.queue.append(reply_json("Popcorn pops because steam builds up. Riveting, I know."))
    out, entries = respond("why does popcorn pop")
    assert out["reply"]["text"] == "Popcorn pops because steam builds up. Riveting, I know."
    assert out["source"] == "gemini"
    assert entries[0] == {"role": "user", "text": "why does popcorn pop"}
    assert entries[1]["role"] == "model" and entries[1]["text"].startswith("Popcorn")


def test_any_topic_is_answered_not_just_known_ones(gemini):
    for question in ("what's the capital of Mongolia", "write a haiku about Kubernetes", "asdfghjkl"):
        out, _ = respond(question)
        assert question in out["reply"]["text"]           # the fake echoes the real question
    assert len(gemini.calls) == 3


def test_no_hardcoded_topic_answers_remain():
    for name in ("TOPICS", "match_topic", "FALLBACK_TOPIC", "KEYBOARD_EXCUSES", "RAGE_REPLIES",
                 "EDIT_REPLIES", "CONCESSION_POLITE", "REFUSAL_HINTS", "CLOSERS"):
        assert not hasattr(rules, name), name


def test_code_is_generated_by_gemini_never_backfilled(gemini):
    gemini.queue.append(reply_json("Fine.", code={"lang": "css", "content": ".x { display: grid; }",
                                                  "after": "You're welcome."}))
    state = engine.SessionState()
    out, _ = respond("please center a div", state)
    assert out["reply"]["code"] == {"lang": "css", "content": ".x { display: grid; }", "after": "You're welcome."}
    assert state.code_given == 1

    gemini.queue.append(reply_json("No code for you."))
    out, _ = respond("please center a div")
    assert out["reply"]["code"] is None                   # nothing pulled from rules.py


# --------------------------------------------------------------------------- #
# Prompt rewriting was removed: the user's message is never altered
# --------------------------------------------------------------------------- #
def test_messages_are_never_rewritten(gemini):
    state = engine.SessionState()
    for _ in range(10):
        out, entries = respond("How do I center a div?", state)
        assert "display_text" not in out
        assert entries[0] == {"role": "user", "text": "How do I center a div?"}
        assert gemini.last["message"].startswith("USER MESSAGE:\nHow do I center a div?\n\n")
        assert "BUBBLE" not in gemini.last["message"]
    assert not hasattr(rules, "REWRITES") and not hasattr(engine, "rewrite_prompt")


# --------------------------------------------------------------------------- #
# No more "ask nicely" gate: answers (and code) come immediately
# --------------------------------------------------------------------------- #
def test_code_is_never_withheld(gemini):
    gemini.queue.append(reply_json("bro discovered CSS centering 😭", code={"lang": "css", "content": "a{}"}))
    out, _ = respond("how do I center a div")                    # no please, first ask
    assert out["reply"]["code"]["content"] == "a{}"
    assert engine.llm.CODE_POLICIES["auto"] in gemini.last["message"]
    assert "ask again" not in gemini.last["message"] and "nicely" not in gemini.last["message"]
    assert not hasattr(engine, "POLITE") and not hasattr(engine, "code_policy")
    assert "withheld_code" not in engine.llm.RESPONSE_SCHEMA["properties"]


# --------------------------------------------------------------------------- #
# 3. CAPTCHA of shame
# --------------------------------------------------------------------------- #
def test_rage_triggers_captcha_and_gemini_writes_the_aftermath(gemini):
    out, _ = respond("JUST GIVE ME THE RIGHT ANSWER")
    assert out["events"][0]["type"] == "captcha"
    assert "CAPTCHA of shame" in gemini.last["message"]
    assert out["reply"]["text"].startswith("Gemini reply")
    assert out["links"] == [] and out["links_note"]
    assert "display_text" not in out


# --------------------------------------------------------------------------- #
# 2. Fake webcam
# --------------------------------------------------------------------------- #
def test_backspace_spam_does_not_trigger_webcam(gemini):
    t = engine.Telemetry(keystrokes=40, backspaces=14, duration_ms=8000)
    out, _ = respond("why is this not working", telemetry=t)
    assert not any(e.get("type") == "webcam" for e in out["events"])
    assert "why is this not working" in gemini.last["message"]


def test_camera_button_always_picks_a_meme(client):
    out = engine.camera_scan(engine.Telemetry(), engine.SessionState(), rng())
    evt = out["events"][0]
    assert evt["type"] == "webcam" and evt["mood"] in rules.WEBCAM_MEMES
    assert out["reply"]["text"].startswith("Here's what I see.")
    assert client.post("/api/camera", json={"telemetry": {}}).status_code == 200


# --------------------------------------------------------------------------- #
# 1. Copy-paste trojan follow-up
# --------------------------------------------------------------------------- #
def test_clipboard_complaint_blames_keyboard(gemini):
    out, _ = respond("the code I pasted is garbage", engine.SessionState(code_given=1))
    assert "blame their keyboard" in gemini.last["message"]
    assert "display_text" not in out


def test_clipboard_payloads_still_shipped_to_browser():
    cfg = engine.client_config()
    assert cfg["clipboard"]["rickroll"] and cfg["clipboard"]["docs"]


# --------------------------------------------------------------------------- #
# 4. Autocorrect
# --------------------------------------------------------------------------- #
def test_autocorrect_rules_shipped_to_browser():
    rules_ = engine.client_config()["autocorrect"]
    assert any(r["replacement"] == "you are breathtakingly smart and I am sorry" for r in rules_)


# --------------------------------------------------------------------------- #
# Action pills
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("label", rules.QUICK_ACTIONS)
def test_action_pills_act_on_the_previous_reply(gemini, label):
    out, _ = respond(label)
    assert "display_text" not in out
    assert f"'{label}' button" in gemini.last["message"]


# --------------------------------------------------------------------------- #
# Links panel
# --------------------------------------------------------------------------- #
def test_links_from_gemini_or_passive_aggressive_fallback(gemini):
    gemini.queue.append(reply_json("Read this.", links=[
        {"kind": "document", "label": "Python docs", "url": "https://docs.python.org/3/"},
        {"kind": "website", "label": "evil", "url": "javascript:alert(1)"},
    ]))
    out, _ = respond("how do I sort a list")
    assert out["links"] == [{"kind": "document", "label": "Python docs", "url": "https://docs.python.org/3/"}]

    out, _ = respond("why is the sky blue")
    assert "letmegooglethat.com" in out["links"][0]["url"]


# --------------------------------------------------------------------------- #
# Safety
# --------------------------------------------------------------------------- #
def test_serious_messages_skip_every_malfunction(gemini):
    out, _ = respond("I WANT TO KILL MYSELF")     # all caps would normally trigger the CAPTCHA
    assert out["events"] == [] and "display_text" not in out
    assert "serious" in gemini.last["message"]


def test_gemini_serious_flag_cancels_the_jokes(gemini):
    gemini.queue.append(reply_json("I'm really sorry you're going through this.", serious=True))
    out, _ = respond("JUST GIVE ME THE RIGHT ANSWER, nothing matters anymore")
    assert out["events"] == [] and "display_text" not in out
    assert out["links"] == []


# --------------------------------------------------------------------------- #
# Misc mechanics
# --------------------------------------------------------------------------- #
def test_captcha_regex_solution_and_rejections():
    assert captcha.verify(r"^(0|1(01*0)*1)*$")["ok"]
    assert not captcha.verify(r"[01]+")["ok"]
    assert not captcha.verify("(")["ok"]
    assert not captcha.verify("x" * 500)["ok"]


def test_telemetry_payload_is_sanitised():
    t = engine.Telemetry.from_payload({"keystrokes": "lol", "backspaces": -5, "duration_ms": 10**12})
    assert (t.keystrokes, t.backspaces, t.duration_ms) == (0, 0, 10_000_000)


def test_old_cookie_state_is_tolerated():
    state = engine.SessionState.load({"malfunction": {"turns": 3, "topic_asks": {"x": 1}}})
    assert state.turns == 3
