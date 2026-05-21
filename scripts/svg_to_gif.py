#!/usr/bin/env python3
"""Convert the animated tutor-demo.svg into a GIF by rendering discrete frames."""

import re
import io
from pathlib import Path

import cairosvg
from PIL import Image

SVG_PATH = Path(__file__).resolve().parent.parent / "assets" / "tutor-demo.svg"
GIF_PATH = SVG_PATH.with_suffix(".gif")

# Each frame shows messages 1..N visible. Frame 0 = banner only.
NUM_MESSAGES = 10

# Timing: milliseconds per frame
FRAME_DURATION_MS = 1400   # each new message holds ~1.4s
FINAL_HOLD_MS = 3000       # hold the complete conversation
BLANK_HOLD_MS = 1500       # pause before loop restarts

SCALE = 2  # render at 2x for crisp GIF


def make_frame_svg(svg_text: str, visible_up_to: int, show_cursor: bool) -> str:
    """Return SVG with animations stripped and explicit opacity set per message."""

    # Strip all animation-related CSS (the .line block, .msg-* rules, @keyframes, .cursor animation)
    # Replace the entire <style> content with static styles

    # Build visibility CSS
    msg_styles = []
    for i in range(1, NUM_MESSAGES + 1):
        opacity = 1 if i <= visible_up_to else 0
        msg_styles.append(f"    .msg-{i} {{ opacity: {opacity}; }}")

    cursor_opacity = 1 if show_cursor else 0
    msg_styles.append(f"    .cursor {{ fill: #D97757; font-size: 13px; font-weight: 700; opacity: {cursor_opacity}; }}")

    static_visibility = "\n".join(msg_styles)

    # Replace the .line { ... } block and everything after it (animations) up to </style>
    # Keep everything before .line {
    new_style = f"""
    .line {{
      /* animations removed for static rendering */
    }}
{static_visibility}
"""

    # Find and replace from ".line {" to "</style>"
    result = re.sub(
        r'\.line\s*\{[^}]*\}.*?</style>',
        new_style + "  </style>",
        svg_text,
        flags=re.DOTALL,
    )

    return result


def render_frame(svg_text: str) -> Image.Image:
    """Render SVG string to a PIL Image."""
    png_data = cairosvg.svg2png(
        bytestring=svg_text.encode("utf-8"),
        output_width=780 * SCALE,
        output_height=550 * SCALE,
    )
    return Image.open(io.BytesIO(png_data)).convert("RGBA")


def main():
    svg_text = SVG_PATH.read_text()

    frames = []
    durations = []

    # Frame 0: banner only, no messages
    print("Rendering frame 0 (banner only)...")
    frame_svg = make_frame_svg(svg_text, visible_up_to=0, show_cursor=False)
    frames.append(render_frame(frame_svg))
    durations.append(FRAME_DURATION_MS)

    # Frames 1-10: progressively reveal messages
    for n in range(1, NUM_MESSAGES + 1):
        print(f"Rendering frame {n} (messages 1-{n})...")
        show_cursor = (n == NUM_MESSAGES)
        frame_svg = make_frame_svg(svg_text, visible_up_to=n, show_cursor=show_cursor)
        frames.append(render_frame(frame_svg))
        durations.append(FINAL_HOLD_MS if n == NUM_MESSAGES else FRAME_DURATION_MS)

    # Final blank frame (brief pause before restart)
    print("Rendering blank frame...")
    frame_svg = make_frame_svg(svg_text, visible_up_to=0, show_cursor=False)
    frames.append(render_frame(frame_svg))
    durations.append(BLANK_HOLD_MS)

    # Convert RGBA to RGB (GIF doesn't support alpha)
    bg = Image.new("RGB", frames[0].size, (255, 255, 255))
    rgb_frames = []
    for f in frames:
        composite = bg.copy()
        composite.paste(f, mask=f.split()[3])
        rgb_frames.append(composite)

    # Save GIF
    print(f"Saving GIF to {GIF_PATH}...")
    rgb_frames[0].save(
        GIF_PATH,
        save_all=True,
        append_images=rgb_frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )

    size_kb = GIF_PATH.stat().st_size / 1024
    print(f"Done! {GIF_PATH.name} ({size_kb:.0f} KB, {len(frames)} frames)")


if __name__ == "__main__":
    main()
