"""Generate simple PNG icons for the extension."""

from PIL import Image, ImageDraw, ImageFont

SIZES = [16, 48, 128]

for size in SIZES:
    img = Image.new("RGBA", (size, size), (26, 26, 26, 255))
    d = ImageDraw.Draw(img)
    font_size = size // 3
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    text = "PF"
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2
    y = (size - th) // 2
    d.text((x, y), text, fill=(74, 222, 128, 255), font=font)
    img.save(f"icon{size}.png")
    print(f"Generated icon{size}.png")
