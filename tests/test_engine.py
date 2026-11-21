import random

import pytest

from app import app as flask_app
from malfunction import captcha, engine, llm


@pytest.fixture(autouse=True)
def no_network_llm(monkeypatch):
    """Tests must never call Gemini, even if a real key is in .env."""
    monkeypatch.setattr(llm, "generate", lambda **_: None)


def test_gemini_reply_is_used_and_code_backfilled(monkeypatch):
    monkeypatch.setattr(llm, "generate", lambda **kw: {"text": "AI says hi", "code": None})
    state = engine.SessionState()
    out = engine.respond("please center a div", engine.Telemetry(), state, rng())
    assert out["reply"]["text"] == "AI says hi"
    assert out["reply"]["code"]["lang"] == "css"      # model skipped code -> topic code used
    assert out["source"] == "gemini" and state.code_given == 1


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def rng():
    return random.Random(42)


def test_first_message_is_always_rewritten():
    state = engine.SessionState()
    out = engine.respond("How do I center a div?", engine.Telemetry(), state, rng())
    assert out["display_text"] and out["display_text"] != "How do I center a div?"
    assert out["reply"]["code"] is None  # refuses on the first, impolite ask


def test_polite_or_repeated_ask_gets_code():
    state = engine.SessionState()
    engine.respond("how do I center a div", engine.Telemetry(), state, rng())
    out = engine.respond("how do I center a div", engine.Telemetry(), state, rng())
    assert out["reply"]["code"]["lang"] == "css"

    polite = engine.respond("please reverse a string", engine.Telemetry(), engine.SessionState(), rng())
    assert polite["reply"]["code"]["lang"] == "python"


def test_rage_triggers_captcha():
    out = engine.respond("JUST GIVE ME THE RIGHT ANSWER", engine.Telemetry(), engine.SessionState(), rng())
    assert out["events"][0]["type"] == "captcha"


def test_backspace_spam_triggers_webcam():
    t = engine.Telemetry(keystrokes=40, backspaces=14, duration_ms=8000)
    out = engine.respond("why is this not working", t, engine.SessionState(), rng())
    assert out["events"][0]["type"] == "webcam"
    assert out["events"][0]["mood"] == "backspace"
    assert out["events"][0]["meme"]["emoji"] == "😤"
    assert "14" in out["reply"]["text"]


def test_camera_button_always_picks_a_meme(client):
    out = engine.camera_scan(engine.Telemetry(), engine.SessionState(), rng())
    evt = out["events"][0]
    assert evt["type"] == "webcam" and evt["mood"] in engine.rules.WEBCAM_MEMES
    assert out["reply"]["text"].startswith("Here's what I see.")
    assert client.post("/api/camera", json={"telemetry": {}}).status_code == 200


def test_clipboard_complaint_blames_keyboard():
    state = engine.SessionState(code_given=1)
    out = engine.respond("the code I pasted is garbage", engine.Telemetry(), state, rng())
    assert out["reply"]["text"] in engine.rules.KEYBOARD_EXCUSES


def test_links_panel_data():
    known = engine.respond("how do I sort a list", engine.Telemetry(), engine.SessionState(), rng())
    assert [l["kind"] for l in known["links"]] == ["website", "document"]
    assert all(l["url"].startswith("https://") for l in known["links"])

    unknown = engine.respond("why is the sky blue", engine.Telemetry(), engine.SessionState(), rng())
    assert "letmegooglethat.com" in unknown["links"][0]["url"]

    rage = engine.respond("JUST GIVE ME THE RIGHT ANSWER", engine.Telemetry(), engine.SessionState(), rng())
    assert rage["links"] == [] and rage["links_note"]


@pytest.mark.parametrize("label", ["Make Response Shorter", "Explain it to me like a lawyer", "Tell me about more"])
def test_action_pills_have_canned_replies(label):
    out = engine.respond(label, engine.Telemetry(), engine.SessionState(), rng())
    assert out["display_text"] is None
    assert out["reply"]["text"] in [answer for _, answer in engine.rules.QUICK_ACTIONS]


def test_captcha_regex_solution_and_rejections():
    assert captcha.verify(r"^(0|1(01*0)*1)*$")["ok"]
    assert not captcha.verify(r"[01]+")["ok"]
    assert not captcha.verify("(")["ok"]
    assert not captcha.verify("x" * 500)["ok"]


def test_telemetry_payload_is_sanitised():
    t = engine.Telemetry.from_payload({"keystrokes": "lol", "backspaces": -5, "duration_ms": 10**12})
    assert (t.keystrokes, t.backspaces, t.duration_ms) == (0, 0, 10_000_000)


def test_http_round_trip(client):
    assert client.get("/api/config").status_code == 200
    assert client.post("/api/chat", json={"message": ""}).status_code == 400
    res = client.post("/api/chat", json={"message": "how do I sort a list", "telemetry": {}})
    assert res.status_code == 200 and res.get_json()["reply"]["text"]
    edit = client.post("/api/edit", json={"original": "a", "attempted": "b"}).get_json()
    assert edit["events"][0]["type"] == "screenshot"
