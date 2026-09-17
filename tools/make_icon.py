"""Генератор иконки PhotoAI. Запускать в WSL: python tools/make_icon.py"""
import os
from PIL import Image, ImageDraw, ImageFilter

OUT_DIR = "assets/icons"
os.makedirs(OUT_DIR, exist_ok=True)

# Палитра
BG_TOP = (108, 92, 231)      # фиолетовый
BG_BOTTOM = (72, 52, 212)    # глубже
ACCENT = (34, 211, 238)      # циан
WHITE = (255, 255, 255)

def make_icon(size=512):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Вертикальный градиент
    for y in range(size):
        t = y / size
        r = int(BG_TOP[0] * (1 - t) + BG_BOTTOM[0] * t)
        g = int(BG_TOP[1] * (1 - t) + BG_BOTTOM[1] * t)
        b = int(BG_TOP[2] * (1 - t) + BG_BOTTOM[2] * t)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))
    # Скругление углов
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size, size], radius=int(size * 0.22), fill=255
    )
    img.putalpha(mask)

    # Стилизованная камера
    cx, cy = size // 2, size // 2 + 10
    cam_w, cam_h = int(size * 0.55), int(size * 0.40)
    box = [cx - cam_w // 2, cy - cam_h // 2, cx + cam_w // 2, cy + cam_h // 2]
    draw.rounded_rectangle(box, radius=int(size * 0.05), fill=WHITE)
    # Объектив
    r = int(size * 0.10)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BG_BOTTOM)
    draw.ellipse([cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2], fill=ACCENT)
    # Вспышка-блик
    r2 = int(size * 0.025)
    draw.ellipse(
        [cx - r - r2 // 2, cy - r - r2 // 2, cx - r + r2, cy - r + r2],
        fill=(255, 255, 255, 220),
    )
    # Искры (магия ИИ)
    for (sx, sy, sr) in [
        (int(size * 0.78), int(size * 0.22), int(size * 0.035)),
        (int(size * 0.85), int(size * 0.32), int(size * 0.018)),
        (int(size * 0.70), int(size * 0.16), int(size * 0.012)),
    ]:
        draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=ACCENT)
    return img

img = make_icon(512)
img.save(os.path.join(OUT_DIR, "icon.png"))
# Adaptive foreground (для Android 8+): прозрачный фон + символ
fg = Image.new("RGBA", (432, 432), (0, 0, 0, 0))
fg.paste(img.resize((288, 288), Image.LANCZOS), (72, 72), img.resize((288, 288), Image.LANCZOS))
fg.save(os.path.join(OUT_DIR, "icon_fg.png"))
print("Иконки созданы:", os.listdir(OUT_DIR))