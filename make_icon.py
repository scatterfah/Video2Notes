"""
Creates the app icon (icon.png and icon.ico) with Pillow.
Run it with:  python make_icon.py
"""

from PIL import Image, ImageDraw

SIZE = 1024  # drawn large, then scaled down for smooth edges


def vertical_gradient(size, top, bottom):
    gradient = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        gradient.putpixel((0, y), tuple(
            round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)
        ))
    return gradient.resize((size, size))


def make_icon():
    # Blue rounded-square background
    background = vertical_gradient(SIZE, (59, 130, 246), (29, 78, 216))
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (32, 32, SIZE - 32, SIZE - 32), radius=210, fill=255
    )

    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    icon.paste(background, (0, 0), mask)

    draw = ImageDraw.Draw(icon)

    # White note page
    draw.rounded_rectangle((250, 190, 774, 830), radius=48, fill=(255, 255, 255))

    # Lines of "notes"
    line_color = (147, 170, 214)
    for y, end in ((330, 674), (430, 674), (530, 674), (630, 520)):
        draw.rounded_rectangle((340, y - 16, end, y + 16), radius=16, fill=line_color)

    # Play button badge (video -> notes)
    cx, cy, r = 705, 770, 175
    draw.ellipse((cx - r - 20, cy - r - 20, cx + r + 20, cy + r + 20), fill=(29, 78, 216))
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(244, 63, 94))
    draw.polygon(
        [(cx - 55, cy - 85), (cx - 55, cy + 85), (cx + 95, cy)],
        fill=(255, 255, 255),
    )

    return icon


if __name__ == "__main__":
    icon = make_icon()
    icon.resize((512, 512), Image.LANCZOS).save("icon.png")
    icon.save(
        "icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print("Created icon.png and icon.ico")
