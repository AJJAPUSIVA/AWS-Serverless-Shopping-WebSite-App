#!/usr/bin/env python3
"""Render the repository architecture diagram as a deterministic PNG."""

from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont


WIDTH, HEIGHT = 1900, 1200
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(str(FONT_DIR / name), size)


FONTS = {
    "title": font(34, True),
    "subtitle": font(18),
    "section": font(18, True),
    "lane": font(15, True),
    "node_title": font(19, True),
    "node": font(15),
    "small": font(13),
    "deprecated_title": font(17, True),
    "deprecated": font(14),
}


def gradient(image: Image.Image, box: tuple[int, int, int, int], start: str, end: str) -> None:
    x1, y1, x2, y2 = box
    start_rgb = Image.new("RGB", (1, 1), start).getpixel((0, 0))
    end_rgb = Image.new("RGB", (1, 1), end).getpixel((0, 0))
    height = max(1, y2 - y1)
    strip = Image.new("RGB", (1, height))
    pixels = strip.load()
    for y in range(height):
        ratio = y / max(1, height - 1)
        pixels[0, y] = tuple(round(a + (b - a) * ratio) for a, b in zip(start_rgb, end_rgb))
    image.paste(strip.resize((x2 - x1, height)), (x1, y1))


def centered(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, style: str, color: str) -> None:
    draw.text((x, y), text, font=FONTS[style], fill=color, anchor="mm")


def panel(
    image: Image.Image,
    box: tuple[int, int, int, int],
    fill: str,
    outline: str,
    radius: int = 16,
    shadow: bool = True,
    dashed: bool = False,
) -> None:
    if shadow:
        shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        shifted = (box[0], box[1] + 5, box[2], box[3] + 5)
        shadow_draw.rounded_rectangle(shifted, radius=radius, fill=(23, 50, 77, 38))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(7))
        image.alpha_composite(shadow_layer)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2)
    if dashed:
        x1, y1, x2, y2 = box
        dash, gap = 9, 6
        for x in range(x1 + radius, x2 - radius, dash + gap):
            draw.line((x, y1, min(x + dash, x2 - radius), y1), fill=outline, width=2)
            draw.line((x, y2, min(x + dash, x2 - radius), y2), fill=outline, width=2)
        for y in range(y1 + radius, y2 - radius, dash + gap):
            draw.line((x1, y, x1, min(y + dash, y2 - radius)), fill=outline, width=2)
            draw.line((x2, y, x2, min(y + dash, y2 - radius)), fill=outline, width=2)


def node(
    image: Image.Image,
    box: tuple[int, int, int, int],
    fill: str,
    outline: str,
    title: str,
    lines: list[tuple[str, str]],
) -> None:
    panel(image, box, fill, outline)
    draw = ImageDraw.Draw(image)
    cx = (box[0] + box[2]) // 2
    top = box[1]
    centered(draw, cx, top + 42, title, "node_title", "#102a43")
    y = top + 72
    for text, style in lines:
        centered(draw, cx, y, text, style, "#486581" if style == "small" else "#334e68")
        y += 25


def arrow(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[int, int]],
    color: str = "#2563a8",
    dashed: bool = False,
) -> None:
    if dashed:
        for start, end in zip(points, points[1:]):
            x1, y1 = start
            x2, y2 = end
            length = max(abs(x2 - x1), abs(y2 - y1))
            steps = max(1, length // 16)
            for i in range(steps):
                if i % 2 == 0:
                    a = i / steps
                    b = min(1.0, (i + 1) / steps)
                    draw.line((x1 + (x2 - x1) * a, y1 + (y2 - y1) * a,
                               x1 + (x2 - x1) * b, y1 + (y2 - y1) * b), fill=color, width=3)
    else:
        draw.line(points, fill=color, width=3, joint="curve")
    (px, py), (x, y) = points[-2], points[-1]
    if abs(x - px) >= abs(y - py):
        tip = [(x, y), (x - 12 if x > px else x + 12, y - 7), (x - 12 if x > px else x + 12, y + 7)]
    else:
        tip = [(x, y), (x - 7, y - 12 if y > py else y + 12), (x + 7, y - 12 if y > py else y + 12)]
    draw.polygon(tip, fill=color)


def build() -> Image.Image:
    image = Image.new("RGBA", (WIDTH, HEIGHT), "#f8fbff")
    gradient(image, (0, 0, WIDTH, HEIGHT), "#f8fbff", "#eef4fb")
    draw = ImageDraw.Draw(image)

    draw.text((70, 42), "AWS Serverless MySQL Shopping Assistant", font=FONTS["title"], fill="#102a43")
    draw.text((70, 76), "Current architecture, trusted data boundaries, and replaced legacy paths", font=FONTS["subtitle"], fill="#486581")

    panel(image, (50, 110, 1850, 845), "#ffffff", "#b8cee5", 25, False)
    draw.rounded_rectangle((72, 128, 322, 164), radius=18, fill="#dff5ec")
    draw.ellipse((88, 139, 102, 153), fill="#16835b")
    draw.text((113, 137), "CURRENT ARCHITECTURE", font=FONTS["section"], fill="#116344")

    lanes = [(91, "CUSTOMER"), (423, "EDGE & AUTH"), (757, "LAMBDA SERVICES"), (1168, "AGENT & RESPONSE"), (1541, "DATA PLANE")]
    for x, label in lanes:
        draw.text((x, 194), label, font=FONTS["lane"], fill="#627d98")
    for x in (385, 720, 1130, 1510):
        draw.line((x, 185, x, 810), fill="#d9e5f2", width=2)

    node(image, (90, 250, 345, 440), "#e9f3ff", "#4d8bc9", "Vue 2 Storefront", [
        ("AWS Amplify + Cognito UI", "node"), ("Products, cart, checkout", "node"), ("Structured assistant cards", "node")])
    node(image, (90, 505, 345, 617), "#f2ecff", "#7b61a8", "Amazon Cognito", [
        ("Authentication + ID token", "node"), ("Customer identity is server-owned", "small")])
    node(image, (430, 292, 680, 412), "#fff5dc", "#d59a19", "Amazon API Gateway", [
        ("Product, cart, checkout", "node"), ("Authenticated /assistant", "node")])
    node(image, (760, 230, 1090, 350), "#edf8ff", "#3d84b8", "Product Lambda", [
        ("MySQL catalog reads", "node"), ("Public product API", "small")])
    node(image, (760, 390, 1090, 525), "#e9f9f3", "#269b72", "Cart + Checkout Lambda", [
        ("Transactional cart and orders", "node"), ("Row locks · rollback · inventory update", "small")])
    node(image, (760, 575, 1090, 730), "#eaf0ff", "#536fca", "Assistant Lambda", [
        ("FastAPI + Mangum", "node"), ("Authenticated typed endpoint", "node"), ("Container image deployment", "small")])
    node(image, (1170, 230, 1470, 350), "#f1eaff", "#7d55b3", "Amazon Bedrock Agent", [
        ("Selects fixed shopping tools", "node"), ("Confirms mutations before writes", "small")])
    node(image, (1170, 390, 1470, 510), "#fff1e4", "#d17a2d", "LangChain + Pydantic", [
        ("Validated structured output", "node"), ("Safe fallback to agent response", "small")])
    node(image, (1170, 550, 1470, 685), "#e7f8f7", "#2b8f8b", "LlamaIndex", [
        ("Offline policy retrieval", "node"), ("Trusted Markdown only · no live SQL", "small")])
    node(image, (1540, 220, 1810, 355), "#e9f9f3", "#16835b", "Safe MySQL Repository", [
        ("Typed functions", "node"), ("Parameterized SQL · no model SQL", "small"), ("IAM database authentication", "small")])
    node(image, (1540, 405, 1810, 500), "#fff5dc", "#d59a19", "RDS Proxy", [
        ("Private pooled TLS connections", "node")])
    node(image, (1540, 550, 1810, 700), "#e8f3ff", "#2563a8", "Aurora Serverless v2", [
        ("MySQL system of record", "node"), ("Products · inventory · customers", "small"), ("Carts · orders · order items", "small")])

    panel(image, (1170, 735, 1810, 807), "#f5f0ff", "#7b61a8", 14, False)
    centered(draw, 1490, 764, "DynamoDB — retained only for assistant session binding", "node_title", "#102a43")
    centered(draw, 1490, 790, "Short-lived sessionId → Cognito customer mapping; not commerce persistence", "small", "#486581")

    arrow(draw, [(345, 345), (430, 345)])
    arrow(draw, [(345, 555), (390, 555), (390, 400), (430, 382)], "#7b61a8", True)
    draw.text((377, 508), "ID token", font=FONTS["small"], fill="#7b61a8")
    arrow(draw, [(680, 325), (720, 325), (720, 290), (760, 290)])
    arrow(draw, [(680, 352), (720, 352), (720, 458), (760, 458)])
    arrow(draw, [(680, 382), (715, 382), (715, 652), (760, 652)])
    arrow(draw, [(1090, 652), (1170, 652)])
    arrow(draw, [(1090, 620), (1130, 620), (1130, 290), (1170, 290)])
    arrow(draw, [(1090, 682), (1135, 682), (1135, 618), (1170, 618)])
    arrow(draw, [(1470, 290), (1540, 290)], "#16835b")
    arrow(draw, [(1090, 290), (1120, 290), (1120, 210), (1510, 210), (1510, 265), (1540, 265)], "#16835b")
    arrow(draw, [(1090, 458), (1145, 458), (1145, 370), (1510, 370), (1510, 315), (1540, 315)], "#16835b")
    arrow(draw, [(1675, 355), (1675, 405)], "#16835b")
    arrow(draw, [(1675, 500), (1675, 550)], "#16835b")
    arrow(draw, [(1090, 705), (1130, 705), (1130, 770), (1170, 770)], "#7b61a8", True)

    panel(image, (50, 875, 1850, 1145), "#fff6f4", "#e5aaa4", 25, False)
    draw.rounded_rectangle((72, 893, 357, 929), radius=18, fill="#ffe0dc")
    draw.ellipse((88, 904, 102, 918), fill="#bd3c32")
    draw.text((113, 902), "DEPRECATED / REMOVED", font=FONTS["section"], fill="#8f2f28")
    draw.text((392, 902), "Kept for migration context; these paths should not receive new features.", font=FONTS["small"], fill="#486581")

    deprecated = [
        ((85, 960, 475, 1095), "Static product_list.json catalog", "Replaced by Aurora products + inventory", "through the safe repository layer"),
        ((525, 960, 915, 1095), "DynamoDB carts + streams", "Replaced by transactional MySQL tables", "and atomic checkout transactions"),
        ((965, 960, 1355, 1095), "Raw chat_handler Lambda", "Replaced by FastAPI + LangChain", "with typed Pydantic responses"),
        ((1405, 960, 1795, 1095), "Vanilla frontend integration", "Replaced by Vue + Amplify", "and structured assistant rendering"),
    ]
    for box, title, line1, line2 in deprecated:
        panel(image, box, "#ffffff", "#d66b62", 16, False, True)
        cx = (box[0] + box[2]) // 2
        centered(draw, cx, 994, title, "deprecated_title", "#8f2f28")
        centered(draw, cx, 1025, line1, "deprecated", "#9f453d")
        centered(draw, cx, 1052, line2, "deprecated", "#9f453d")
        draw.line((box[0] + 30, 985, box[2] - 30, 1070), fill="#c53c32", width=5)

    draw.text((70, 1165), "Solid arrows: active request/data flow  ·  Dashed purple: authentication/session identity  ·  Red strike-through: removed path", font=FONTS["small"], fill="#486581")
    return image.convert("RGB")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: render_architecture.py OUTPUT.png")
    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    build().save(output, "PNG", optimize=True)


if __name__ == "__main__":
    main()
