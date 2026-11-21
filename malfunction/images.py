"""Validation for images attached to a chat message (homework photos, code screenshots...).

The type is decided from the file's actual bytes (magic numbers), never from its name or the
Content-Type the browser claims, and the size is capped. Valid images are passed to Gemini as
inline image data by llm.generate(); nothing is written to disk.
"""
from __future__ import annotations

import os
from typing import Any

# PNG, JPEG and WebP: what phones, screenshots and the browser-side resizer produce.
ALLOWED = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WebP"}


def _max_bytes() -> int:
    try:
        return max(1, int(float(os.environ.get("IMAGE_MAX_MB", "4")) * 1024 * 1024))
    except ValueError:
        return 4 * 1024 * 1024


MAX_BYTES = _max_bytes()   # keep below Vercel's 4.5 MB request limit if you deploy there


class ImageError(Exception):
    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def sniff(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def load(upload: Any) -> dict[str, Any] | None:
    """Read and validate a Werkzeug FileStorage. Returns {"mime", "data"} or None if no file."""
    if upload is None:
        return None
    data = upload.read(MAX_BYTES + 1)
    if not data:
        return None
    if len(data) > MAX_BYTES:
        raise ImageError("image_too_large",
                         f"That image is over {MAX_BYTES // (1024 * 1024)} MB. Try a smaller photo or a screenshot.", 413)
    mime = sniff(data)
    if mime is None:
        raise ImageError("invalid_image", "That file isn't a PNG, JPEG or WebP image.", 400)
    return {"mime": mime, "data": data}
