"""End-to-end over HTTP: conversation memory, isolation, resets and failure handling."""
from google.genai import errors

from app import app as flask_app
from conftest import ChatSession, reply_json


def user_texts(call):
    return [text for role, text in call["history"] if role == "user"]


def test_follow_up_questions_get_the_conversation_context(chat, gemini):
    chat.send("What is Python?")
    chat.send("Is it beginner-friendly?")
    res, data = chat.send("Can you give me an example?")
    assert res.status_code == 200

    call = gemini.last
    assert [role for role, _ in call["history"]] == ["user", "model", "user", "model"]
    texts = user_texts(call)
    assert texts[0].startswith("What is Python?") and texts[1].startswith("Is it beginner-friendly?")
    assert "Gemini reply #1 to: What is Python?" in call["history"][1][1]
    assert "Can you give me an example?" in call["message"]


def test_different_conversations_do_not_share_history(client, gemini):
    a, b = ChatSession(client), ChatSession(client)
    a.send("My favourite language is Rust")
    b.send("What did I say my favourite language was?")
    assert gemini.last["history"] == []

    # A's token is useless for B's conversation id.
    res = client.post("/api/chat", json={"message": "hi", "conversation_id": b.cid, "history_token": a.token})
    assert res.get_json()["memory_reset"] is True and gemini.last["history"] == []


def test_new_chat_resets_history_and_malfunction_state(chat, gemini):
    chat.send("Remember the number 42")
    chat.send("ok")
    with chat.http.session_transaction() as sess:
        assert sess["malfunction"]["turns"] == 2
    chat.new_chat()
    chat.send("What number did I ask you to remember?")
    assert gemini.last["history"] == []
    with chat.http.session_transaction() as sess:
        assert sess["malfunction"]["turns"] == 1          # counters reset with the chat


def test_history_token_cannot_be_forged_or_reused_by_someone_else(chat, gemini):
    chat.send("secret plans")
    tampered = chat.token[:-3] + ("aaa" if not chat.token.endswith("aaa") else "bbb")
    res = chat.http.post("/api/chat", json={"message": "hi", "conversation_id": chat.cid, "history_token": tampered})
    assert res.get_json()["memory_reset"] is True and gemini.last["history"] == []

    stranger = flask_app.test_client()                # different cookie = different owner
    res = stranger.post("/api/chat", json={"message": "hi", "conversation_id": chat.cid, "history_token": chat.token})
    assert res.get_json()["memory_reset"] is True and gemini.last["history"] == []


def test_failed_turns_are_not_remembered(chat, gemini):
    chat.send("first question")
    gemini.queue.append(errors.ClientError(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED",
                                                           "message": "Quota exceeded"}}))
    res, data = chat.send("this one fails")
    assert res.status_code == 429
    assert data["error_code"] == "rate_limited" and "rate limit" in data["error"]
    assert "reply" not in data and "history_token" not in data      # no fake AI reply

    chat.send("second question")
    assert [t.split("\n")[0] for t in user_texts(gemini.last)] == ["first question"]


def test_missing_key_is_a_clear_error_not_a_scripted_reply(chat, gemini, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    res, data = chat.send("hello?")
    assert res.status_code == 503 and data["error_code"] == "missing_key"
    assert "GEMINI_API_KEY" in data["error"] and "reply" not in data
    assert chat.http.get("/api/config").get_json()["ai"]["enabled"] is False


def test_regenerate_replaces_the_last_exchange(chat, gemini):
    chat.send("question one")
    chat.send("question two")
    _, data = chat.send("question two", regenerate=True)
    assert [t.split("\n")[0] for t in user_texts(gemini.last)] == ["question one"]

    chat.send("question three")
    assert [t.split("\n")[0] for t in user_texts(gemini.last)] == ["question one", "question two"]


def test_replies_are_dynamic(chat, gemini):
    _, one = chat.send("tell me a joke about SQL")
    _, two = chat.send("now one about CSS")
    assert one["reply"]["text"] != two["reply"]["text"]
    assert "CSS" in two["reply"]["text"]


def test_edit_trap_reply_is_generated_and_remembered(chat, gemini):
    chat.send("how do I center a div")
    gemini.queue.append(reply_json("Changing 'center a div' to 'I love tabs'? I keep receipts."))
    res = chat.http.post("/api/edit", json={"original": "how do I center a div", "attempted": "I love tabs",
                                            "conversation_id": chat.cid, "history_token": chat.token})
    data = res.get_json()
    assert data["events"][0] == {"type": "screenshot", "original": "how do I center a div", "attempted": "I love tabs"}
    assert data["reply"]["text"].startswith("Changing")
    assert "I love tabs" in gemini.last["message"]

    chat.token = data["history_token"]
    chat.send("why did you screenshot me")
    assert any("I love tabs" in t for t in user_texts(gemini.last))


def test_http_basics_and_no_key_leak(client):
    assert client.post("/api/chat", json={"message": ""}).status_code == 400
    config = client.get("/api/config")
    assert config.status_code == 200 and "test-key-not-real" not in config.get_data(as_text=True)
    res = client.post("/api/chat", json={"message": "no conversation id yet"})   # tolerated
    assert res.status_code == 200 and res.get_json()["conversation_id"]
