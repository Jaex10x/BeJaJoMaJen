# Doubt.ai 🙂

A chat assistant that is *technically* helpful and malfunctions on purpose. Built for a hackathon.
**Google Gemini is the brain**: it writes every reply, answers any topic, reads images (homework
photos, screenshots), and remembers the conversation. Its personality is a sarcastic internet friend
who happens to know things: short, casual replies ("4. revolutionary math."), slang when it fits,
and real answers and code immediately, with no "ask nicely" gate. The backend is Python (Flask) and decides which malfunction fires. The frontend is
vanilla JS and performs the tricks. No camera is used unless you click the camera button.

## Run it

```powershell
# needs Python 3.10+  (https://www.python.org/downloads/ or: winget install Python.Python.3.12)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then edit .env: set GEMINI_API_KEY (and SECRET_KEY)
python app.py
```

Get a Gemini API key at <https://aistudio.google.com/apikey> and put it in `.env` as `GEMINI_API_KEY=...`.
The key stays on the server and is never sent to the browser or written to the logs. Also set `SECRET_KEY`
(`python -c "import secrets; print(secrets.token_hex(32))"`), or chats are forgotten whenever the server restarts.

Open **http://localhost:5000**. Use `localhost` and not a LAN IP, because the Clipboard API only works in a secure context.
Without a key the page still loads, but every message shows a clear "Gemini isn't configured" error.
There are no fake scripted answers.

Run the tests with `pytest`. They mock Gemini, so they need no key and no network.

## The malfunctions (and how to show each one in a demo)

| # | Malfunction | How to trigger it | Where it lives |
|---|-------------|-------------------|----------------|
| 1 | **Copy-paste trojan** | Ask for code (e.g. *"how do I center a div?"*). Click **Copy** and paste it somewhere. Each copy gives you, in turn: a subtly broken version (Greek-question-mark "semicolons", a missing brace), a "read the docs" comment, or a Rickroll. Then complain that the paste is broken and Gemini blames your keyboard. | `Trojan` in JS (patches `navigator.clipboard.writeText` and the `copy` event), `rules.SITUATIONS["clipboard"]` |
| 2 | **Fake webcam paranoia** | Type a message and press backspace 6+ times, type very fast, or half-shout. A `📷 Reading facial expression...` toast appears, the REC light blinks, and Gemini opens with a posture lecture before answering. No camera permission is ever requested. | `Telemetry`/`Webcam` in JS, `engine.webcam_event`, `rules.SITUATIONS["webcam"]` |
| 3 | **CAPTCHA of shame** | Type *"JUST GIVE ME THE RIGHT ANSWER"* (or anything in ALL CAPS). Chat locks. The 3×3 grid of mirrors and clowns can't be passed. After that comes a regex puzzle (binary numbers divisible by 3), checked on the server. After 2 failures, an escape hatch appears: *"I admit I did not read the docs"*. Then Gemini welcomes you back, smugly. | `Captcha` in JS, `malfunction/captcha.py` |
| 4 | **Autocorrect sabotage** | Type *"you are wrong "* (with the trailing space). It turns into *"you are breathtakingly smart and I am sorry"* with a Grammarly-style green underline. Works for bug, broken, lie, useless, and more. | `Autocorrect` in JS, `rules.AUTOCORRECT_RULES` |
| 5 | **Edit message trap** | Hover your message, click ✏️, change it, and Save. It shows "(edited)", glitches, and reverts. The AI then posts a blurry, noisy JPEG "screenshot" of your original (made on a canvas), and Gemini gloats about what you tried to change it into. | `EditTrap`/`Screenshot` in JS, `engine.edit_trap` |

The action pills under each answer (*Make Response Shorter*, *Explain it to me like a lawyer*, ...) really do
transform the previous answer, because Gemini remembers it.

**Recommended demo script:** "How do I center a div?" (code appears) → Copy and paste it (broken) → "the paste is broken" → type "you are wrong " → spam backspace → "JUST GIVE ME THE RIGHT ANSWER" → edit an old message.

## Architecture

```
app.py                  Flask routes: /api/config, /api/chat, /api/edit, /api/camera, /api/captcha/*, /api/reset
malfunction/engine.py   Decides which malfunction fires (serious > rage > webcam > clipboard > pill > normal)
malfunction/llm.py      Gemini: system prompt, multi-turn chat, JSON schema, error handling
malfunction/memory.py   Conversation history as a signed token (no server-side storage)
malfunction/rules.py    Gameplay content + the "situation" notes that tell Gemini what just happened
malfunction/captcha.py  Regex puzzle + server-side verification (length-capped, short test strings)
static/app.js           One module per malfunction
templates/index.html    UI shell + CAPTCHA modal
tests/                  pytest suite (Gemini is faked in tests/conftest.py)
```

**How a message flows.** `engine.respond()` picks the malfunction and builds its gameplay events (the CAPTCHA,
the webcam animation). It then calls `llm.generate()` with the conversation history, the message,
and a short *situation* note such as "the fake webcam
just scanned them because they pressed backspace 14 times". Gemini plays along and still answers.
The reply is JSON: `{text, code, links, image_notes, serious}`. The browser gets
`{events, reply: {text, code}, links, conversation_id, history_token}`.

**Conversation memory.** Every *New chat* (and every page load) gets a fresh `conversation_id`. After each reply,
the server returns the updated transcript as a `history_token`, signed with `SECRET_KEY` (via `itsdangerous`).
The browser sends the token back with the next message. The browser can't read-modify it: a tampered token,
an expired one (24 h), or a token from another visitor or another conversation is rejected, and the chat starts
fresh. Gemini sees the last 20 messages, up to about 16k characters. This keeps the server stateless, so it
works across restarts and on serverless hosts. The malfunction counters (turn count, annoyance, code copies) are
stored separately, in Flask's signed session cookie.

**Errors.** If Gemini fails, the API returns a JSON error (`error`, `error_code`) with a fitting status. Codes:
`missing_key` 503, `invalid_key` 502, `rate_limited` 429, `timeout` 504, `network` 502, `unavailable` 503,
`blocked` 422, `empty` / `invalid` / `truncated` 502. The UI shows it in a red dashed "actual malfunction" bubble
with a Retry button. The failed turn is not saved, and the app never substitutes a scripted reply.

**Images.** The 📎 button (or paste with Ctrl+V, or drag and drop) attaches a PNG, JPEG or WebP image.
The browser scales big photos down to at most 2400 px, then sends the image as `multipart/form-data`
to `/api/chat`. The server checks the real file type from its bytes (`malfunction/images.py`, max
`IMAGE_MAX_MB`, default 4) and passes the actual image to Gemini as an inline image part. Gemini also
returns `image_notes`, a transcription of what the image contained. That transcription is kept in the
conversation history, so follow-ups like "explain number 3" work without uploading the image again.

**Safety.** The persona roasts the question, never the person. Messages that look like a real crisis skip every
malfunction (`engine.SERIOUS`), and Gemini can flag a message as `serious`, which cancels the jokes too.

## Testing the chatbot by hand

1. Personality: *"hello"*, *"are you stupid?"*, *"what is 2 + 2?"*, *"I think Java is better than Python."*.
   You should get short, casual, original one-liners, not essays.
2. Ask *"What is Python?"*, then *"Is it beginner-friendly?"*, then *"Can you give me an example?"*. The follow-ups
   should clearly be about Python, and the example code should come straight away.
3. Attach a photo of an assignment and type *"answer these"*. Each question should be answered under its original
   number. Then ask *"explain number 2 in more detail"*.
4. Ask something off-script, such as *"Plan a 3-day trip to Lisbon"*, *"Explain TCP vs UDP"*, or *"asdfgh"*.
5. Click **New chat** and ask *"What did we just talk about?"*. It shouldn't know.
6. Remove `GEMINI_API_KEY` from `.env` and restart. You should get a clear error, not a fake answer.

## Deploying (e.g. Vercel)

The app keeps no state on the server, so it can run on serverless platforms. Set `GEMINI_API_KEY`, `SECRET_KEY`
and `SESSION_COOKIE_SECURE=1` as environment variables in the host's dashboard. A Gemini reply takes a few
seconds, well within Vercel's default 300 s function limit. Vercel serves static files from `public/`, not
Flask's `static/` folder, so they need to move there before deploying (not done yet).
