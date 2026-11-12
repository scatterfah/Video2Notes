"""
Creates the app icon (icon.png and icon.ico) with Pillow.
Small sizes (used for shortcuts) get a simpler, bolder design so they stay sharp.
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


def draw_icon(simple=False):
    # Blue rounded-square background
    background = vertical_gradient(SIZE, (59, 130, 246), (29, 78, 216))
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (16, 16, SIZE - 16, SIZE - 16), radius=210, fill=255
    )

    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    icon.paste(background, (0, 0), mask)
    draw = ImageDraw.Draw(icon)

    if simple:
        page = (200, 140, 800, 880)
        lines = ((340, 700), (500, 700))   # (y, line end): two bold lines
        half = 34
        cx, cy, r = 690, 750, 235
        triangle = [(cx - 75, cy - 115), (cx - 75, cy + 115), (cx + 125, cy)]
        ring = 30
        line_color = (110, 140, 205)
    else:
        page = (250, 190, 774, 830)
        lines = ((330, 674), (430, 674), (530, 674), (630, 520))
        half = 16
        cx, cy, r = 705, 770, 175
        triangle = [(cx - 55, cy - 85), (cx - 55, cy + 85), (cx + 95, cy)]
        ring = 20
        line_color = (147, 170, 214)

    # White note page
    draw.rounded_rectangle(page, radius=48, fill=(255, 255, 255))

    # Lines of "notes"
    for y, end in lines:
        draw.rounded_rectangle((page[0] + 90, y - half, end, y + half), radius=half, fill=line_color)

    # Play button badge (video -> notes)
    draw.ellipse((cx - r - ring, cy - r - ring, cx + r + ring, cy + r + ring), fill=(29, 78, 216))
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(244, 63, 94))
    draw.polygon(triangle, fill=(255, 255, 255))

    return icon


if __name__ == "__main__":
    full = draw_icon(simple=False)
    simple = draw_icon(simple=True)

    full.resize((512, 512), Image.LANCZOS).save("icon.png")

    # One separately drawn image for every size inside the .ico file
    sizes = [256, 128, 64, 48, 32, 24, 16]
    images = []
    for size in sizes:
        source = simple if size <= 48 else full
        images.append(source.resize((size, size), Image.LANCZOS))

    images[0].save(
        "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print("Created icon.png and icon.ico")
