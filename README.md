# Doubt.ai 🙂

A chat assistant that is *technically* helpful and malfunctions on purpose. Built for a hackathon.

**Google Gemini is the brain**: it writes every reply, answers any topic, reads images (homework photos, screenshots, diagrams), and remembers the entire conversation. Its personality is a sarcastic internet friend who happens to know things: short, casual replies, sharp wit, and real answers and runnable code immediately.

The backend is Python (Flask) and orchestrates which malfunction fires. The frontend is vanilla JS and executes the visual and clipboard tricks. No camera is ever accessed automatically—face scanning only happens if you choose to click the camera button.

---

## Run it

### Standard Setup
```powershell
# needs Python 3.10+ (https://www.python.org/downloads/ or: winget install Python.Python.3.12)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then edit .env: set GEMINI_API_KEY (and SECRET_KEY)
python app.py
```

### Configuration
1. Get a Gemini API key at <https://aistudio.google.com/apikey>.
2. Place it in `.env` as `GEMINI_API_KEY=your_key_here`.
3. *(Optional)* Set `SECRET_KEY` (`python -c "import secrets; print(secrets.token_hex(32))"`), or chats reset whenever the server restarts.

Open **http://localhost:5000**. Use `localhost` (not a LAN IP) because the Clipboard API requires a secure context. Without a key, the page still loads and displays a clean "Gemini isn't configured" error message.

Run the test suite with:
```powershell
pytest
```
Tests mock Gemini and need no network access or API key.

---

## The Malfunctions (and how to show each one in a demo)

| # | Malfunction | How to trigger it | Where it lives |
|---|-------------|-------------------|----------------|
| 1 | **Job application flythrough** | Click or tap inside the message input box for the first time. A job application form flies across your screen (*"maybe get a job instead"*). | `FlyThrough` in JS, `static/img/job_application.png` |
| 2 | **Theme-toggle jumpscares** | Click the theme toggle (sun/moon switch) to change modes. Toggling to dark mode or light mode plays a flashbang jumpscare with sound effects. | `Jumpscare` & `Sfx` in JS, `static/img/jumpscare.png`, `static/img/lightscare.png` |
| 3 | **Copy-paste trojan** | Ask for code (e.g. *"how do I center a div?"*). Click **Copy** and paste it into an editor. Each copy gives you: subtly broken code (Greek question-mark `;` disguised as semicolons, missing brackets), a *"read the docs yourself"* link, or a Rickroll. Complain that the paste is broken, and Gemini blames your keyboard. | `Trojan` in JS (patches `navigator.clipboard.writeText` and `copy` events), `rules.SITUATIONS["clipboard"]` |
| 4 | **Camera button & nerd detector** | Click the 📷 camera button next to the input box. A face scan runs: if you are wearing glasses (detected via MediaPipe edge analysis), it hits you with a nerd jumpscare. Otherwise, it matches your expression with a shocked meme twin and gives you posture advice. | `Glasses` & `Webcam` in JS, `static/img/nerd.png`, `static/img/shocked.png`, `/api/camera` |
| 5 | **CAPTCHA of shame** | Send a frustrated or aggressive prompt (e.g. *"JUST GIVE ME THE RIGHT ANSWER"*, *"shut up"*, *"useless"*). Chat locks behind `shameCAPTCHA`. You must tick *"I am a capable developer"*, fail an impossible 3×3 grid of clowns and mirrors (*"a bug in your own code"*), and solve a server-checked regex puzzle (binary numbers divisible by 3) before receiving an escape hatch: *"I admit I did not read the docs"*. | `Captcha` in JS, `malfunction/captcha.py`, `rules.SITUATIONS["captcha"]` |
| 6 | **Autocorrect sabotage** | Type *"you are wrong "* (with a trailing space). It silently corrects to *"you are breathtakingly smart and I am sorry"* with a green Grammarly-style underline. Also triggers on *bug*, *broken*, *lie*, *useless*, and *stupid*. | `Autocorrect` in JS, `rules.AUTOCORRECT_RULES` |
| 7 | **Edit message trap** | Hover over your own sent message, click ✏️, change the text, and click Save. The message glitches, shows "(edited)", and reverts back. The AI posts a noisy, degraded JPEG "screenshot" canvas capture of your original message and mocks your attempt to hide it. | `EditTrap`/`Screenshot` in JS, `engine.edit_trap`, `/api/edit` |

The action pills below replies (*Make Response Shorter*, *Explain it to me like a lawyer*, ...) dynamically rewrite or reformat the prior response in-character.

---

## Recommended Demo Script

1. **The Greeting**: Click into the prompt box → watch the **job application fly across the screen**.
2. **The Theme Switch**: Click the theme toggle → brace for the **dark-mode jumpscare**.
3. **The Selfie**: Click the 📷 camera button → experience the **face/glasses scan** (or nerd jumpscare if wearing glasses).
4. **The Code Trojan**: Ask *"How do I center a div?"* → click **Copy** → paste into Notepad (broken code or Rickroll) → message *"the paste is broken"* → Gemini blames your keyboard.
5. **Autocorrect**: Type *"you are wrong "* (with a space) → watch it autocorrect to high praise.
6. **The CAPTCHA**: Type *"JUST GIVE ME THE RIGHT ANSWER"* → chat locks behind the **CAPTCHA of shame** (clowns, mirrors, regex puzzle).
7. **The Receipt**: Hover an earlier message, click ✏️, edit it, and Save → watch it revert and display a grainy canvas screenshot receipt.
8. **Vision & Memory**: Attach an image (📎 or paste an image with Ctrl+V) → ask *"Explain what this diagram shows"*, followed by *"Explain part 2 in more detail"*.

---

## Architecture

```
app.py                  Flask backend: /api/config, /api/chat, /api/edit, /api/camera, /api/captcha/*, /api/reset
malfunction/engine.py   Malfunction router (serious safety > rage/CAPTCHA > clipboard complaints > normal)
malfunction/llm.py      Gemini engine: system prompt, multi-turn chat, JSON schema, error handling
malfunction/memory.py   Stateless conversation history signed with itsdangerous (no database required)
malfunction/images.py   Image upload validation, MIME detection, byte limits, and Gemini inline parts
malfunction/rules.py    Gameplay jokes, situation notes for Gemini, clipboard payloads, and autocorrect rules
malfunction/captcha.py  shameCAPTCHA regex puzzle generator & server-side verification
static/app.js           Vanilla JS client (Trojan, Autocorrect, Glasses detector, Jumpscares, EditTrap)
static/style.css        Doubt.ai theme (olive chrome, cream canvas, peach message cards, responsive layout)
templates/index.html    Application UI shell, CAPTCHA modal, webcam overlay, and jumpscare elements
tests/                  Comprehensive pytest test suite (Gemini is mocked in tests/conftest.py)
```

### How a Message Flows
1. `engine.respond()` evaluates the incoming message and session state. If a malfunction triggers (e.g. rage detected), it builds the appropriate event payload.
2. It sends the conversation history, the user prompt, optional uploaded images, and a brief **situation note** (e.g. *"they complained code was broken; blame their keyboard"*) to `llm.generate()`.
3. Gemini answers in character according to the situation prompt, returning structured JSON: `{text, code, image_notes, serious}`.
4. The client receives the reply alongside any gameplay event flags to animate the UI.

### Conversation Memory
- Every conversation receives a fresh `conversation_id`.
- The server issues a signed (tamper-proof, not encrypted) `history_token` (via `itsdangerous`) back to the browser on every turn.
- The client sends the token back with subsequent turns. This keeps the backend fully stateless and compatible with serverless hosts.
- Tampered or cross-visitor tokens are rejected, resetting conversation history cleanly.

### Multimodal Vision
- Upload images via the 📎 attachment button, drag & drop, or clipboard paste (`Ctrl+V`).
- The browser scales images to at most 2400px before uploading via `multipart/form-data`.
- `malfunction/images.py` validates file magic numbers (PNG, JPEG, WebP) up to 4 MB and attaches them directly to the Gemini request.
- Gemini produces `image_notes` preserved in memory, enabling multi-turn follow-ups without re-uploading images.

### Safety Net
- Serious messages indicating distress, crisis, or real emergencies (`engine.is_serious`) completely bypass all malfunctions.
- Gemini is instructed to immediately drop the sarcastic persona and reply with sincere care and helpful support.

---

## Deploying

Because the application keeps no persistent server state, it is ready for containerized or serverless hosting:
- Set `GEMINI_API_KEY`, `SECRET_KEY`, and `SESSION_COOKIE_SECURE=1` in your environment.
- Standard WSGI servers (e.g. `gunicorn app:app`) run smoothly in production.
