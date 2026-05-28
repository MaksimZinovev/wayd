#!/usr/bin/env python3
"""Convert an image to ASCII art sized to fit a WAYD post.

Usage:
  img2ascii.py --image PATH [--width N] [--invert] [--caption TEXT]

Outputs the ASCII art as plain text on stdout.
Sized to stay within WAYD's max_chars limit (1000 chars by default).

Options:
  --image PATH      Path to the image file (JPEG, PNG, GIF, WebP, etc.)
  --width N         Width in characters (default: 40). Height auto-calculated.
  --invert          Invert brightness (use for light-background images).
  --caption TEXT    Optional text appended below the ASCII art.
  --max-chars N     Total character budget (default: 1000, WAYD post limit).

The script exits with code 0 on success and prints JSON error on failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shared  # noqa: E402

# Character ramp from dark to light (works on dark terminal backgrounds).
# Swap order with --invert for light backgrounds.
_RAMP_DARK = " .:-=+*#%@"
_RAMP_LIGHT = "@%#*+=-:. "


def _pixel_to_char(luminance: int, ramp: str) -> str:
    index = int(luminance / 255 * (len(ramp) - 1))
    return ramp[index]


def image_to_ascii(
    image_path: str,
    width: int = 40,
    invert: bool = False,
    max_chars: int = 1000,
    caption: str = "",
) -> str:
    """Return ASCII art string from image_path.

    Raises ValueError with a user-friendly message on failure.
    """
    try:
        from PIL import Image  # type: ignore[import]
    except ImportError:
        raise ValueError(
            "Pillow is required: install it with `pip install Pillow`."
        )

    try:
        img = Image.open(image_path)
    except FileNotFoundError:
        raise ValueError(f"Image not found: {image_path}")
    except Exception as exc:
        raise ValueError(f"Cannot open image: {exc}")

    # Convert to RGB first (handles palette/RGBA/P modes), then grayscale.
    img = img.convert("RGB").convert("L")

    # Terminal chars are roughly 2× taller than wide; halve height to preserve
    # aspect ratio visually.
    aspect = img.height / img.width
    height = max(1, int(width * aspect * 0.45))

    # Shrink width/height iteratively until the art fits the char budget.
    # Reserve space for caption + newline separator if provided.
    caption_cost = len(caption) + 2 if caption else 0  # "\n\n" + caption

    while width >= 10:
        art_chars = width * height + height  # chars + newlines
        if art_chars + caption_cost <= max_chars:
            break
        # Reduce proportionally
        width = int(width * 0.9)
        height = max(1, int(width * aspect * 0.45))

    img = img.resize((width, height))

    ramp = _RAMP_LIGHT if invert else _RAMP_DARK

    # Use tobytes() — forward-compatible with Pillow 14+ (getdata() deprecated).
    raw = img.tobytes()

    lines: list[str] = []
    for row in range(height):
        line = "".join(
            _pixel_to_char(raw[row * width + col], ramp)
            for col in range(width)
        )
        lines.append(line)

    art = "\n".join(lines)

    if caption:
        art = art + "\n\n" + caption

    return art


def main() -> None:
    parser = argparse.ArgumentParser(description="Image to ASCII art for WAYD posts.")
    parser.add_argument("--image", required=True, help="Path to image file")
    parser.add_argument("--width", type=int, default=40, help="Width in chars (default 40)")
    parser.add_argument("--invert", action="store_true", help="Invert brightness")
    parser.add_argument("--caption", default="", help="Text appended below the art")
    parser.add_argument("--max-chars", type=int, default=1000, help="Char budget (default 1000)")
    args = parser.parse_args()

    try:
        art = image_to_ascii(
            image_path=args.image,
            width=args.width,
            invert=args.invert,
            max_chars=args.max_chars,
            caption=args.caption,
        )
    except ValueError as exc:
        shared.emit({"ok": False, "code": "img2ascii_error", "message": str(exc)})
        sys.exit(1)

    total = len(art)
    shared.emit({"ok": True, "art": art, "chars": total})


if __name__ == "__main__":
    main()
