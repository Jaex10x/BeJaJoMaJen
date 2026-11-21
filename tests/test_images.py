"""Image attachments: real image bytes reach Gemini, follow-ups work, bad uploads are rejected."""
import io
import json

import pytest

from malfunction import images, llm
from conftest import reply_json

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64          # magic bytes are all the validator checks
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 64


def upload(chat, message, data, filename="homework.png", content_type="image/png", **extra):
    payload = {"message": message, "telemetry": {}, "conversation_id": chat.cid,
               "history_token": chat.token, **extra}
    res = chat.http.post("/api/chat", content_type="multipart/form-data", data={
        "payload": json.dumps(payload),
        "image": (io.BytesIO(data), filename, content_type),
    })
    body = res.get_json()
    if res.status_code == 200:
        chat.cid, chat.token = body["conversation_id"], body["history_token"]
    return res, body


def test_image_bytes_are_sent_to_gemini_as_an_image_part(chat, gemini):
    gemini.queue.append(reply_json("fuh nahh a whole side quest 😭\n\n1. Swing is a GUI toolkit.",
                                   image_notes="1. What is Swing? 2. What is a JFrame?"))
    res, data = upload(chat, "answer these", PNG)
    assert res.status_code == 200
    assert gemini.last["images"] == [("image/png", PNG)]           # the real pixels, not a filename
    assert "ATTACHMENT" in gemini.last["message"] and "answer these" in gemini.last["message"]
    assert data["reply"]["text"].startswith("fuh nahh")


def test_follow_up_questions_remember_what_the_image_contained(chat, gemini):
    gemini.queue.append(reply_json("done", image_notes="1. What is Swing? 2. What is a JFrame?"))
    upload(chat, "answer these", PNG)
    chat.send("explain number 2 in more detail")
    history_user_turn = gemini.last["history"][0][1]
    assert "What is a JFrame?" in history_user_turn and "attached an image" in history_user_turn
    assert gemini.last["images"] == []                              # not re-sent; the notes carry it


@pytest.mark.parametrize("data, mime", [(PNG, "image/png"), (JPEG, "image/jpeg"), (WEBP, "image/webp")])
def test_supported_formats_detected_from_bytes(chat, gemini, data, mime):
    res, _ = upload(chat, "what is this", data, filename="whatever.bin", content_type="application/octet-stream")
    assert res.status_code == 200 and gemini.last["images"] == [(mime, data)]


def test_image_without_text_is_allowed(chat, gemini):
    res, _ = upload(chat, "", JPEG, filename="worksheet.jpg", content_type="image/jpeg")
    assert res.status_code == 200
    assert "(no text, just the image)" in gemini.last["message"]


def test_non_images_are_rejected_without_calling_gemini(chat, gemini):
    res, data = upload(chat, "answer these", b"%PDF-1.7 definitely not a png", filename="homework.png")
    assert res.status_code == 400 and data["error_code"] == "invalid_image"
    assert gemini.calls == []


def test_oversized_images_are_rejected(chat, gemini, monkeypatch):
    monkeypatch.setattr(images, "MAX_BYTES", 100)
    res, data = upload(chat, "answer these", PNG + b"\x00" * 200)
    assert res.status_code == 413 and data["error_code"] == "image_too_large"
    assert gemini.calls == []


def test_plain_json_requests_still_work(chat, gemini):
    res, data = chat.send("hello")
    assert res.status_code == 200 and gemini.last["images"] == []


def test_image_limits_are_published_to_the_browser(client):
    cfg = client.get("/api/config").get_json()["images"]
    assert cfg["types"] == ["image/png", "image/jpeg", "image/webp"] and cfg["max_bytes"] == images.MAX_BYTES


def test_llm_passes_the_image_through_the_sdk_part_type(gemini):
    llm.generate(history=[], message="read this", image={"mime": "image/jpeg", "data": JPEG})
    assert gemini.last["images"] == [("image/jpeg", JPEG)]
