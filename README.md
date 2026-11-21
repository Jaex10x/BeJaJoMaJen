# GaslightAI 🙂

A chat assistant that is *technically* helpful and malfunctions on purpose. Built for a hackathon.
It needs no camera, no API keys, and no real AI. The backend is Python (Flask) and makes every
decision. The frontend is vanilla JS and does the tricks.

## Run it

```powershell
# needs Python 3.10+  (https://www.python.org/downloads/ or: winget install Python.Python.3.12)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000**. Use `localhost` and not a LAN IP, because the Clipboard API only works in a secure context.
Run the tests with `pytest`.

## The malfunctions (and how to show each one in a demo)

| # | Malfunction | How to trigger it | Where it lives |
|---|-------------|-------------------|----------------|
| 1 | **Live prompt rewriting** | Ask anything, e.g. *"How do I center a div?"*. Your bubble silently changes to something unhinged, and the AI answers the new version. | `engine.rewrite_prompt`, `rules.REWRITES`, `send()` in JS |
| 2 | **Copy-paste trojan** | Ask the same thing twice, or say *please*, to get code. Click **Copy** and paste it somewhere. Each copy gives you, in turn: a subtly broken version (Greek-question-mark "semicolons", a missing brace), a "read the docs" comment, or a Rickroll. Then complain that the paste is broken and the AI blames your keyboard. | `Trojan` in JS (patches `navigator.clipboard.writeText` and the `copy` event) |
| 3 | **Fake webcam paranoia** | Type a message and press backspace 6+ times, type very fast, or half-shout. A `📷 Reading facial expression...` toast appears, the REC light blinks, and you get a posture lecture. No camera permission is ever requested. | `Telemetry`/`Webcam` in JS, `engine.webcam_*` |
| 4 | **CAPTCHA of shame** | Type *"JUST GIVE ME THE RIGHT ANSWER"* (or anything in ALL CAPS). Chat locks. The 3×3 grid of mirrors and clowns can't be passed. After that comes a regex puzzle (binary numbers divisible by 3), checked on the server. After 2 failures, an escape hatch appears: *"I admit I did not read the docs"*. | `Captcha` in JS, `malfunction/captcha.py` |
| 5 | **Autocorrect sabotage** | Type *"you are wrong "* (with the trailing space). It turns into *"you are breathtakingly smart and I am sorry"* with a Grammarly-style green underline. Works for bug, broken, lie, useless, and more. | `Autocorrect` in JS, `rules.AUTOCORRECT_RULES` |
| 6 | **Edit message trap** | Hover your message, click ✏️, change it, and Save. It shows "(edited)", glitches, and reverts. The AI then posts a blurry, noisy JPEG "screenshot" of your original, made on a canvas. | `EditTrap`/`Screenshot` in JS, `engine.edit_trap` |

**Recommended demo script:** "How do I center a div?" → (rewritten) → "how do I center a div" again (code appears) → Copy and paste it (broken) → "the paste is broken" → type "you are wrong " → spam backspace → "JUST GIVE ME THE RIGHT ANSWER" → edit an old message.

## Architecture

```
app.py                  Flask routes: /api/config, /api/chat, /api/edit, /api/captcha/*, /api/reset
malfunction/rules.py    All joke content (rewrites, topics, excuses, autocorrect rules). Tune here.
malfunction/engine.py   Decides which malfunction fires (rage > webcam > clipboard > normal)
malfunction/captcha.py  Regex puzzle + server-side verification (length-capped, short test strings)
static/app.js           One module per malfunction
templates/index.html    UI shell + CAPTCHA modal
tests/                  pytest suite
```

Per-user state (turn count, annoyance, which topics were asked) is kept in Flask's signed session cookie.
Set `SECRET_KEY` in the environment so sessions survive a restart.

**Plugging in a real LLM:** `engine.respond()` returns `{display_text, events, reply}`. Keep the malfunction
routing as it is and replace the topic/tease text with a model call that is told to answer the *rewritten* prompt.
