"""Mechanic 4, stage 2: a deliberately obscure (but solvable) regex puzzle, verified server-side.

Safety: user-supplied patterns run with Python's backtracking `re` engine, so a nasty pattern
could backtrack exponentially. We cap pattern length and keep every test string <= 10 chars,
which bounds the worst case to a trivial amount of work.
"""
from __future__ import annotations

import re
from typing import Any

MAX_PATTERN = 120

PUZZLE = {
    "title": "Additional verification required",
    "prompt": "Write a regex that fully matches binary numbers divisible by 3, and nothing else.",
    "flavor": "Capable developers do this in their sleep. You may begin crying now.",
    "must_match": ["0", "11", "110", "1001", "1100", "1111", "10010", "11011"],
    "must_not_match": ["1", "10", "100", "101", "111", "1000", "1010", "11010"],
}

# Hidden cases stop people hard-coding the visible list with alternations.
_HIDDEN_MATCH = ["111111", "1001011", "1111000011"]
_HIDDEN_REJECT = ["1111111", "10000000", "1010101010", "abc", "2"]

HINTS = (
    "Hint: think of it as a state machine with 3 states (remainder 0, 1, 2). Or think of a different career.",
    "Hint: ^(0|1(01*0)*1)*$ is what a capable developer would type. Not that you are one.",
)


def public_puzzle() -> dict[str, Any]:
    return dict(PUZZLE)


def verify(pattern: Any, attempt: int = 0) -> dict[str, Any]:
    if not isinstance(pattern, str) or not pattern.strip():
        return {"ok": False, "message": "An empty regex. Bold strategy."}
    if len(pattern) > MAX_PATTERN:
        return {"ok": False, "message": f"Over {MAX_PATTERN} characters? That's not a regex, that's a cry for help."}
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        return {"ok": False, "message": f"That isn't even valid regex ({exc}). Impressive.", "hint": _hint(attempt)}

    for s in PUZZLE["must_match"] + _HIDDEN_MATCH:
        if not rx.fullmatch(s):
            return {"ok": False, "message": f"Didn't match '{s}' ({int(s, 2)}, divisible by 3, in case math is also hard).",
                    "hint": _hint(attempt)}
    for s in PUZZLE["must_not_match"] + _HIDDEN_REJECT:
        if rx.fullmatch(s):
            detail = f" ({int(s, 2)} is not divisible by 3)" if set(s) <= {"0", "1"} else ""
            return {"ok": False, "message": f"You matched '{s}'{detail}. Rejected.", "hint": _hint(attempt)}

    return {"ok": True, "message": "Verified. Ugh. Fine. You may speak again."}


def _hint(attempt: int) -> str | None:
    return HINTS[min(attempt, len(HINTS) - 1)] if attempt >= 1 else None
