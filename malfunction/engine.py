"""The decision-making core: given a message + typing telemetry, pick which malfunction fires.

Division of labour:
  * This module decides WHICH malfunction happens (fake webcam, CAPTCHA, keyboard blame...) and builds the gameplay events the browser animates.
  * Gemini (llm.py) writes EVERY conversational reply, with the conversation history and a
    short "situation" note describing the malfunction, so it can play along and still answer.

Malfunction state (SessionState, in the cookie) and conversation history (memory.py, on the
server) are kept separate on purpose.
"""
from __future__ import annotations

import random
import re
from dataclasses import asdict, dataclass
from typing import Any, MutableMapping
from urllib.parse import quote_plus

from . import images, llm, rules

RAGE = re.compile(
    r"just give me|right answer|answer the (?:\w+ )?question|stop (?:it|this|messing)|are you kidding|wtf",
    re.I,
)
CLIPBOARD_COMPLAINT = re.compile(r"\b(?:paste[ds]?|pasting|clipboard|copied|copy(?:ing)?)\b", re.I)
# A cheap safety net: never lock someone in a joke CAPTCHA or webcam lecture when they may
# be in real trouble. Gemini also flags serious messages itself (see "serious" in llm.py).
SERIOUS = re.compile(
    r"\b(?:kill(?:ing)? myself|suicid\w*|self[- ]?harm|end(?:ing)? my life|want to die|hurt(?:ing)? myself"
    r"|overdos\w*|(?:being|been) abused|abusing me|can'?t breathe|heart attack)\b",
    re.I,
)

MAX_MESSAGE = 2000


# --------------------------------------------------------------------------- #
# Inputs / state
# --------------------------------------------------------------------------- #
@dataclass
class Telemetry:
    """Typing behaviour captured in the browser. No camera, ever: this is all we 'see'."""
    keystrokes: int = 0
    backspaces: int = 0
    duration_ms: int = 0

    @classmethod
    def from_payload(cls, raw: Any) -> "Telemetry":
        raw = raw if isinstance(raw, dict) else {}

        def num(key: str) -> int:
            try:
                return max(0, min(int(raw.get(key, 0)), 10_000_000))
            except (TypeError, ValueError):
                return 0

        return cls(num("keystrokes"), num("backspaces"), num("duration_ms"))

    @property
    def cpm(self) -> int:
        if self.duration_ms < 800:
            return 0
        return round(self.keystrokes / (self.duration_ms / 60_000))

    @property
    def backspace_ratio(self) -> float:
        return self.backspaces / self.keystrokes if self.keystrokes else 0.0

    @property
    def agitated_by_backspace(self) -> bool:
        return self.backspaces >= 6 or (self.keystrokes >= 12 and self.backspace_ratio >= 0.25)

    @property
    def agitated_by_speed(self) -> bool:
        return self.keystrokes >= 20 and self.cpm >= 480


@dataclass
class SessionState:
    """Malfunction counters, stored in Flask's signed session cookie (kept deliberately tiny).

    This is NOT the conversation: the transcript lives server-side in memory.py.
    """
    turns: int = 0
    annoyance: int = 0
    code_given: int = 0

    KEY = "malfunction"  # not a dataclass field: no annotation

    @classmethod
    def load(cls, store: MutableMapping[str, Any]) -> "SessionState":
        raw = store.get(cls.KEY)
        if not isinstance(raw, dict):
            return cls()
        try:
            return cls(**{k: raw[k] for k in cls.__dataclass_fields__ if k in raw})
        except TypeError:
            return cls()

    def save(self, store: MutableMapping[str, Any]) -> None:
        store[self.KEY] = asdict(self)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def caps_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    return sum(c.isupper() for c in letters) / len(letters) if len(letters) >= 8 else 0.0


def is_rage(message: str) -> bool:
    return bool(RAGE.search(message)) or caps_ratio(message) >= 0.7


def is_serious(message: str) -> bool:
    return bool(SERIOUS.search(message))


def reply(text: str, code: dict[str, str] | None = None) -> dict[str, Any]:
    return {"text": text, "code": code}


def fallback_links(message: str) -> list[dict[str, str]]:
    """When Gemini has no real references to offer: a passive-aggressive search instead."""
    entries = (
        ("website", "Let me google that for you", f"https://letmegooglethat.com/?q={quote_plus(message[:200])}"),
        rules.FALLBACK_DOC_LINK,
    )
    return [{"kind": kind, "label": label, "url": url} for kind, label, url in entries]


def is_quick_action(message: str) -> str | None:
    text = message.strip().rstrip(".!? ").lower()
    return next((label for label in rules.QUICK_ACTIONS if label.lower() == text), None)


def user_entry(text: str, image_notes: str | None = None) -> dict[str, Any]:
    """image_notes is not None when an image was attached: Gemini's transcription of it, so
    follow-up questions work without re-sending the picture."""
    entry: dict[str, Any] = {"role": "user", "text": text}
    if image_notes is not None:
        entry.update(image=True, image_notes=image_notes)
    return entry


def model_entry(ai: dict[str, Any]) -> dict[str, Any]:
    return {"role": "model", "text": ai["text"], "code": ai["code"]}


# --------------------------------------------------------------------------- #
# Main entry points
# --------------------------------------------------------------------------- #
def respond(message: str, telemetry: Telemetry, state: SessionState, history: list[dict[str, Any]],
            rng: random.Random | None = None, image: dict[str, Any] | None = None
            ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Route the message through the malfunctions, then let Gemini write the reply.

    `image` (optional, validated by images.py) goes to Gemini as real image data.

    Returns (api_result, new_history_entries). Raises llm.LLMError if Gemini can't answer; the
    caller must then discard `state` so a failed turn leaves no trace.
    """
    rng = rng or random.Random()
    message = message[:MAX_MESSAGE]
    state.turns += 1
    result: dict[str, Any] = {"events": [], "reply": None, "links": [], "links_note": rules.NO_LINKS_NOTE}
    situation: list[str] = []
    policy = "auto"            # Gemini decides when code helps; it is never withheld
    allow_links = False

    if is_serious(message):
        # Safety first: no webcam, no CAPTCHA.
        situation.append(rules.SITUATIONS["serious"])
        allow_links = True

    elif is_rage(message):
        # 3. CAPTCHA of shame: highest priority. Rage locks the chat; Gemini writes the aftermath.
        state.annoyance += 2
        result["events"].append({"type": "captcha"})
        situation.append(rules.SITUATIONS["captcha"])

    elif telemetry.agitated_by_backspace or telemetry.agitated_by_speed or caps_ratio(message) >= 0.45:
        # 2. Fake webcam: agitated typing gets a posture lecture (and then, grudgingly, an answer).
        state.annoyance += 1
        event = webcam_event(telemetry, message, rng)
        result["events"].append(event)
        situation.append(rules.SITUATIONS["webcam"][event["mood"]].format(
            backspaces=telemetry.backspaces, cpm=telemetry.cpm, verdict=event["verdict"]))

    elif state.code_given and CLIPBOARD_COMPLAINT.search(message):
        # 1. Trojan follow-up: the user noticed their paste was garbage. Blame the keyboard.
        situation.append(rules.SITUATIONS["clipboard"])

    elif label := is_quick_action(message):
        # Action pills ("Make Response Shorter", ...) act on the previous reply.
        situation.append(rules.SITUATIONS["quick_action"].format(label=label))
        allow_links = True

    else:
        # Normal path: Gemini just answers (in character).
        allow_links = True

    ai = llm.generate(history=history, message=message, situation=situation, code_policy=policy, image=image)

    if ai["serious"]:
        # Gemini spotted a real situation: cancel every joke that was about to fire.
        result["events"], allow_links = [], True

    if ai["code"]:
        state.code_given += 1

    result["reply"] = reply(ai["text"], ai["code"])
    if allow_links:
        result["links"] = ai["links"] or ([] if ai["serious"] or not message else fallback_links(message))
    result["source"] = "gemini"
    notes = ai["image_notes"] if image is not None else None
    return result, [user_entry(message, notes), model_entry(ai)]


def webcam_mood(telemetry: Telemetry, message: str) -> str:
    """Which 'expression' the fake camera claims to see. Drives both the meme and the lecture."""
    if telemetry.agitated_by_backspace:
        return "backspace"
    if telemetry.agitated_by_speed:
        return "speed"
    if caps_ratio(message) >= 0.45:
        return "caps"
    return "generic"


def webcam_event(telemetry: Telemetry, message: str, rng: random.Random) -> dict[str, Any]:
    hostility = "CRITICAL" if telemetry.backspaces >= 15 or caps_ratio(message) >= 0.6 else "elevated"
    mood = webcam_mood(telemetry, message)
    return {
        "type": "webcam",
        "mood": mood,
        "meme": {**rules.WEBCAM_MEMES[mood], "confidence": round(rng.uniform(94, 99.9), 1)},
        "steps": list(rules.WEBCAM_STEPS),
        "verdict": f"Posture: {rng.randint(2, 4)}/10 · Hostility: {hostility} · Snack crumbs: detected",
    }


def camera_scan(telemetry: Telemetry, state: SessionState,
                rng: random.Random | None = None) -> dict[str, Any]:
    """The user pressed the camera button. Pure gameplay: the browser flashes a meme and
    posts nothing to the chat, so this stays scripted and never touches the conversation."""
    rng = rng or random.Random()
    mood = webcam_mood(telemetry, "")
    if mood == "generic":                       # nothing to go on? pick an expression anyway
        mood = rng.choice(list(rules.WEBCAM_MEMES))
    event = webcam_event(telemetry, "", rng)
    event["mood"] = mood
    event["meme"] = {**rules.WEBCAM_MEMES[mood], "confidence": event["meme"]["confidence"]}
    state.annoyance += 1
    return {
        "events": [event],
        "reply": reply(f"{rules.WEBCAM_SELFIE[mood]}\n\n{rng.choice(rules.WEBCAM_ADVICE)}"),
    }


def edit_trap(original: str, attempted: str, state: SessionState, history: list[dict[str, Any]]
              ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Mechanic 5: the edit "fails" (in the browser) and the AI produces "evidence" of the original.

    The screenshot event is gameplay; the gloating reply is written by Gemini, who knows exactly
    what they tried to change. Raises llm.LLMError like respond().
    """
    original, attempted = original[:MAX_MESSAGE], attempted[:MAX_MESSAGE]
    state.annoyance += 1
    note = f'[I tried to edit my earlier message "{original}" so that it says "{attempted}"]'
    ai = llm.generate(history=history, message=note, situation=[rules.SITUATIONS["edit"]], code_policy="none")
    result = {
        "reply": reply(ai["text"]),
        "events": [{"type": "screenshot", "original": original, "attempted": attempted}],
        "source": "gemini",
    }
    return result, [user_entry(note), {"role": "model", "text": ai["text"], "code": None}]


def client_config() -> dict[str, Any]:
    """Everything the browser needs to run the front-end malfunctions (no secrets in here)."""
    return {
        "welcome": rules.WELCOME,
        "ai": {"enabled": llm.enabled(), "model": llm.model_name()},
        "suggestions": list(rules.SUGGESTIONS),
        "history_seed": list(rules.HISTORY_SEED),
        "toasts": rules.TOASTS,
        "glasses_threshold": rules.GLASSES_THRESHOLD,
        "quick_actions": list(rules.QUICK_ACTIONS),
        "images": {"types": list(images.ALLOWED), "max_bytes": images.MAX_BYTES},
        "autocorrect": list(rules.AUTOCORRECT_RULES),
        "clipboard": rules.CLIPBOARD_PAYLOADS,
        "captcha": {
            "tiles": list(rules.CAPTCHA_TILES),
            "grid_fails": list(rules.CAPTCHA_GRID_FAILS),
            "shame_reply": rules.SHAME_REPLY,
        },
    }
