# scripts/generate_icons.py
# Run once to produce extension/icon{16,32,48,128}.png.
# Commit the output PNGs — no need to re-run unless the icon design changes.
#
# Requires: pip install pillow
# Font:     place any TTF/OTF bold font at app/static/fonts/icon_font.ttf
#           (e.g. Roboto-Bold.ttf from fonts.google.com)

import os
from PIL import Image, ImageDraw, ImageFont

SIZES   = [16, 32, 48, 128]
OUT     = "extension"
GREEN   = (34, 197, 94, 255)   # #22c55e
WHITE   = (255, 255, 255, 255)
BG      = (26, 26, 46, 255)    # #1a1a2e

FONT_SEARCH = [
    "app/static/fonts/icon_font.ttf",       # bundled font (preferred) — drop any bold TTF here
    "/System/Library/Fonts/Helvetica.ttc",  # macOS fallback
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux fallback
    "C:/Windows/Fonts/arialbd.ttf",         # Windows fallback
]

def load_font(size):
    for path in FONT_SEARCH:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()  # fallback — pixelated but functional

def draw_outlined_text(draw, pos, text, font, fill, outline, outline_width):
    x, y = pos
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=outline)
    draw.text((x, y), text, font=font, fill=fill)

for size in SIZES:
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle(
        [0, 0, size - 1, size - 1],
        radius=size // 6,
        fill=BG
    )

    font_size    = int(size * 0.62)
    font         = load_font(font_size)
    outline_px   = max(1, size // 24)

    bbox   = draw.textbbox((0, 0), "J", font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x      = (size - text_w) // 2 - bbox[0]
    y      = (size - text_h) // 2 - bbox[1]

    draw_outlined_text(draw, (x, y), "J", font, GREEN, WHITE, outline_px)

    path = os.path.join(OUT, f"icon{size}.png")
    img.save(path, "PNG")
    print(f"[icons] {path}")
