"""The decision-making core: given a message + typing telemetry, pick which malfunction fires."""
from __future__ import annotations

import random
import re
from dataclasses import asdict, dataclass, field
from typing import Any, MutableMapping
from urllib.parse import quote_plus

from . import llm, rules

RAGE = re.compile(
    r"just give me|right answer|answer the (?:\w+ )?question|stop (?:it|this|messing)|are you kidding|wtf",
    re.I,
)
CLIPBOARD_COMPLAINT = re.compile(r"\b(?:paste[ds]?|pasting|clipboard|copied|copy(?:ing)?)\b", re.I)
POLITE = re.compile(r"\b(?:please|pls|plz|thank(?:s| you)|sorry|kindly)\b", re.I)

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
    """Per-visitor memory, stored in Flask's signed session cookie (kept deliberately tiny)."""
    turns: int = 0
    annoyance: int = 0
    code_given: int = 0
    last_rewrite: int = -1
    topic_asks: dict[str, int] = field(default_factory=dict)

    KEY = "malfunction"  # not a dataclass field: no annotation

    @classmethod
    def load(cls, store: MutableMapping[str, Any]) -> "SessionState":
        raw = store.get(cls.KEY)
        if not isinstance(raw, dict):
            return cls()
        try:
            state = cls(**{k: raw[k] for k in cls.__dataclass_fields__ if k in raw})
        except TypeError:
            return cls()
        if not isinstance(state.topic_asks, dict):
            state.topic_asks = {}
        return state

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


def reply(text: str, code: dict[str, str] | None = None) -> dict[str, Any]:
    return {"text": text, "code": code}


def rewrite_prompt(message: str, state: SessionState, rng: random.Random) -> rules.Rewrite | None:
    """Mechanic 1: decide whether (and how) to silently mutate the user's own bubble."""
    if state.turns > 1 and rng.random() > 0.7:
        return None
    choices = [i for i in range(len(rules.REWRITES)) if i != state.last_rewrite]
    idx = rng.choice(choices)
    state.last_rewrite = idx
    return rules.REWRITES[idx]


def apply_rewrite(rewrite: rules.Rewrite, message: str) -> str:
    stripped = message.strip().rstrip("?.! ")
    return rewrite.template.format(p=stripped)


def links_for(topic: rules.Topic, message: str) -> list[dict[str, str]]:
    """Right-hand panel: real docs for known topics, a passive-aggressive search otherwise."""
    entries = topic.links or (
        ("website", "Let me google that for you", f"https://letmegooglethat.com/?q={quote_plus(message[:200])}"),
        rules.FALLBACK_DOC_LINK,
    )
    return [{"kind": kind, "label": label, "url": url} for kind, label, url in entries]


def quick_action(message: str) -> str | None:
    text = message.strip().rstrip(".!? ")
    for pattern, answer in rules.QUICK_ACTIONS:
        if pattern.match(text):
            return answer
    return None


# --------------------------------------------------------------------------- #
# Main entry points
# --------------------------------------------------------------------------- #
def respond(message: str, telemetry: Telemetry, state: SessionState,
            rng: random.Random | None = None) -> dict[str, Any]:
    rng = rng or random.Random()
    message = message[:MAX_MESSAGE]
    state.turns += 1
    result: dict[str, Any] = {"display_text": None, "events": [], "reply": None,
                              "links": [], "links_note": rules.NO_LINKS_NOTE}

    # 4. CAPTCHA of shame: highest priority. Rage locks the chat.
    if is_rage(message):
        state.annoyance += 2
        result["events"].append({"type": "captcha"})
        result["reply"] = reply(rng.choice(rules.RAGE_REPLIES))
        return result

    # 3. Fake webcam: agitated typing gets a posture lecture instead of an answer.
    if telemetry.agitated_by_backspace or telemetry.agitated_by_speed or caps_ratio(message) >= 0.45:
        state.annoyance += 1
        result["events"].append(webcam_event(telemetry, message, rng))
        result["reply"] = reply(webcam_lecture(telemetry, message, rng))
        return result

    # 2. Trojan follow-up: the user noticed their paste was garbage.
    if state.code_given and CLIPBOARD_COMPLAINT.search(message):
        result["reply"] = reply(rng.choice(rules.KEYBOARD_EXCUSES))
        return result

    # Action pills ("Make Response Shorter", ...).
    canned = quick_action(message)
    if canned:
        result["reply"] = reply(canned)
        return result

    # 1. Normal path: rewrite their bubble, then answer the *rewritten* request.
    topic = rules.match_topic(message)
    asks = state.topic_asks.get(topic.key, 0) + 1
    state.topic_asks = {**state.topic_asks, topic.key: asks}

    rewrite = rewrite_prompt(message, state, rng)
    if rewrite:
        result["display_text"] = apply_rewrite(rewrite, message)

    paragraphs: list[str] = [rewrite.opener] if rewrite else []
    polite = bool(POLITE.search(message))
    give_code = polite or asks >= 2
    result["links"] = links_for(topic, message)

    # ---- LLM HOOK: Gemini writes the reply when GEMINI_API_KEY is set (malfunction/llm.py) ----
    ai = llm.generate(real_question=message, shown_question=result["display_text"] or message,
                      give_code=give_code)
    if ai:
        code = ai["code"]
        if give_code and not code and topic is not rules.FALLBACK_TOPIC:
            code = {"lang": topic.lang, "content": topic.code}   # model forgot the code: use ours
        if code:
            state.code_given += 1
            code = {**code, "after": rng.choice(rules.CLOSERS)}
        result["reply"] = reply(ai["text"], code)
        result["source"] = "gemini"
        return result
    # ---- scripted fallback below ----

    if give_code:
        concession = (rng.choice(rules.CONCESSION_POLITE) if polite
                      else rng.choice(rules.CONCESSION_PERSISTENT).format(n=asks))
        paragraphs += [concession, topic.answer]
        code = {"lang": topic.lang, "content": topic.code, "after": rng.choice(rules.CLOSERS)}
        state.code_given += 1
        result["reply"] = reply("\n\n".join(paragraphs), code)
    else:
        paragraphs += [topic.tease, rng.choice(rules.REFUSAL_HINTS)]
        result["reply"] = reply("\n\n".join(paragraphs))

    return result


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


def webcam_lecture(telemetry: Telemetry, message: str, rng: random.Random) -> str:
    observation = rules.WEBCAM_OBSERVATIONS[webcam_mood(telemetry, message)]
    text = observation.format(backspaces=telemetry.backspaces, cpm=telemetry.cpm)
    return f"{text}\n\n{rng.choice(rules.WEBCAM_ADVICE)}"


def camera_scan(telemetry: Telemetry, state: SessionState,
                rng: random.Random | None = None) -> dict[str, Any]:
    """The user pressed the camera button. Read their 'face' (their typing) and judge it."""
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


def edit_trap(original: str, attempted: str, state: SessionState,
              rng: random.Random | None = None) -> dict[str, Any]:
    """Mechanic 6: the edit "fails", and the AI produces "evidence" of the original."""
    rng = rng or random.Random()
    state.annoyance += 1
    return {
        "reply": reply(rng.choice(rules.EDIT_REPLIES)),
        "events": [{"type": "screenshot", "original": original[:MAX_MESSAGE], "attempted": attempted[:MAX_MESSAGE]}],
    }


def client_config() -> dict[str, Any]:
    """Everything the browser needs to run the front-end malfunctions."""
    return {
        "welcome": rules.WELCOME,
        "suggestions": list(rules.SUGGESTIONS),
        "history_seed": list(rules.HISTORY_SEED),
        "toasts": rules.TOASTS,
        "glasses_threshold": rules.GLASSES_THRESHOLD,
        "quick_actions": ["Make Response Shorter", "Explain it to me like a lawyer", "Tell me about more"],
        "autocorrect": list(rules.AUTOCORRECT_RULES),
        "clipboard": rules.CLIPBOARD_PAYLOADS,
        "captcha": {
            "tiles": list(rules.CAPTCHA_TILES),
            "grid_fails": list(rules.CAPTCHA_GRID_FAILS),
            "shame_reply": rules.SHAME_REPLY,
        },
    }
