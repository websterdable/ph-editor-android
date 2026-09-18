"""Операции над изображениями через bytes (без NumPy).

Быстрые операции — через bytes.translate (C-скорость).
Сложные (насыщенность, резкость, hue) — через циклы Python,
оптимизированные за счёт bytearray и предвычисленных LUT.
"""

# ─── LUT ─────────────────────────────────────────────────────

def _lut_brightness(factor):
    return bytes([min(255, max(0, int(i * factor))) for i in range(256)])


def _lut_contrast(factor):
    return bytes([min(255, max(0, int((i - 128) * factor + 128)))
                  for i in range(256)])


def _lut_exposure(ev):
    """ev: -50..+50. Экспозиция в стиле фото: 2^(ev/50)."""
    factor = 2.0 ** (ev / 50.0)
    return _lut_brightness(factor)


def _lut_shadows(amount):
    """amount: -50..+50. Осветление/затемнение теней."""
    out = []
    for i in range(256):
        # Вес максимален в тенях, к среднему падает
        weight = max(0.0, 1.0 - i / 128.0)
        delta = (amount / 50.0) * 60.0 * weight
        out.append(min(255, max(0, int(i + delta))))
    return bytes(out)


def _lut_highlights(amount):
    """amount: -50..+50. Осветление/затемнение светов."""
    out = []
    for i in range(256):
        weight = max(0.0, (i - 128) / 128.0)
        delta = (amount / 50.0) * 60.0 * weight
        out.append(min(255, max(0, int(i + delta))))
    return bytes(out)


def _lut_scurve(amount):
    """S-кривая. amount: -50..+50."""
    out = []
    k = amount / 50.0
    for i in range(256):
        x = i / 255.0
        # Простая S-кривая
        if k >= 0:
            y = x + k * (x - 0.5) * (1 - abs(2 * x - 1))
        else:
            y = x + k * (x - 0.5) * 0.5
        out.append(min(255, max(0, int(y * 255))))
    return bytes(out)


def _lut_hue_shift(degrees):
    """LUT сдвига hue. Приблизительно: три таблицы для R, G, B."""
    import math
    rad = math.radians(degrees)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    # Матрица поворота цвета (YIQ-подход)
    r_t = []
    g_t = []
    b_t = []
    for i in range(256):
        v = i
        # Упрощённая аппроксимация через смешивание каналов
        r_new = v * (cos_a + (1 - cos_a) * 0.30) + \
                v * ((1 - cos_a) * 0.59 - sin_a * 0.11) + \
                v * ((1 - cos_a) * 0.11 + sin_a * 0.30)
        g_new = v * ((1 - cos_a) * 0.30 + sin_a * 0.14) + \
                v * (cos_a + (1 - cos_a) * 0.59) + \
                v * ((1 - cos_a) * 0.11 - sin_a * 0.14)
        b_new = v * ((1 - cos_a) * 0.30 - sin_a * 0.44) + \
                v * ((1 - cos_a) * 0.59 + sin_a * 0.10) + \
                v * (cos_a + (1 - cos_a) * 0.11)
        r_t.append(min(255, max(0, int(r_new))))
        g_t.append(min(255, max(0, int(g_new))))
        b_t.append(min(255, max(0, int(b_new))))
    return bytes(r_t), bytes(g_t), bytes(b_t)


# ─── Быстрые операции ────────────────────────────────────────

def brightness(rgb_bytes, factor):
    """factor: 0.5..1.5."""
    return rgb_bytes.translate(_lut_brightness(factor))


def contrast(rgb_bytes, factor):
    """factor: 0.5..1.5."""
    return rgb_bytes.translate(_lut_contrast(factor))


def exposure(rgb_bytes, ev):
    """ev: -50..+50."""
    return rgb_bytes.translate(_lut_exposure(ev))


def shadows(rgb_bytes, amount):
    """amount: -50..+50."""
    return rgb_bytes.translate(_lut_shadows(amount))


def highlights(rgb_bytes, amount):
    """amount: -50..+50."""
    return rgb_bytes.translate(_lut_highlights(amount))


def s_curve(rgb_bytes, amount):
    """amount: -50..+50."""
    return rgb_bytes.translate(_lut_scurve(amount))


def warmth(rgb_bytes, factor):
    """factor: -1..1."""
    if abs(factor) < 0.01:
        return rgb_bytes
    r_factor = 1.0 + factor * 0.15
    b_factor = 1.0 - factor * 0.15
    r_table = _lut_brightness(r_factor)
    b_table = _lut_brightness(b_factor)
    out = bytearray(rgb_bytes)
    out[0::3] = rgb_bytes[0::3].translate(r_table)
    out[2::3] = rgb_bytes[2::3].translate(b_table)
    return bytes(out)


def hue_shift(rgb_bytes, degrees):
    """degrees: -180..180."""
    if abs(degrees) < 1:
        return rgb_bytes
    r_t, g_t, b_t = _lut_hue_shift(degrees)
    out = bytearray(rgb_bytes)
    out[0::3] = rgb_bytes[0::3].translate(r_t)
    out[1::3] = rgb_bytes[1::3].translate(g_t)
    out[2::3] = rgb_bytes[2::3].translate(b_t)
    return bytes(out)


# ─── Сложные операции ────────────────────────────────────────

def saturation(rgb_bytes, factor):
    """factor: 0..2, 1.0 — без изменений.

    Оптимизация: строим 256-элементный кэш для каждой пары (channel, gray_level).
    Но проще и надёжнее — цикл через bytearray с прямым доступом.
    """
    if abs(factor - 1.0) < 0.01:
        return rgb_bytes
    n = len(rgb_bytes) // 3
    r = rgb_bytes[0::3]
    g = rgb_bytes[1::3]
    b = rgb_bytes[2::3]
    out_r = bytearray(n)
    out_g = bytearray(n)
    out_b = bytearray(n)
    # Предвычисленный LUT: для каждого (значение канала 0..255) и (серое 0..255)
    # это 65 536 комбинаций — тяжеловато. Используем формулу напрямую.
    for i in range(n):
        ri, gi, bi = r[i], g[i], b[i]
        gray = (ri * 77 + gi * 150 + bi * 29) >> 8  # ~0.299/0.587/0.114
        d = gray * (1 - factor)
        out_r[i] = min(255, max(0, int(ri * factor + d)))
        out_g[i] = min(255, max(0, int(gi * factor + d)))
        out_b[i] = min(255, max(0, int(bi * factor + d)))
    result = bytearray(len(rgb_bytes))
    result[0::3] = out_r
    result[1::3] = out_g
    result[2::3] = out_b
    return bytes(result)


def sharpness(rgb_bytes, w, h, factor):
    """Unsharp mask: blur 3x3 + разность. factor: 0..200 (в процентах)."""
    if factor < 5:
        return rgb_bytes
    strength = factor / 100.0

    # Box blur 3x3 через простое усреднение
    n = w * h
    r = rgb_bytes[0::3]
    g = rgb_bytes[1::3]
    b = rgb_bytes[2::3]

    blurred_r = _blur_channel(r, w, h)
    blurred_g = _blur_channel(g, w, h)
    blurred_b = _blur_channel(b, w, h)

    out = bytearray(len(rgb_bytes))
    for i in range(n):
        out[i * 3]     = min(255, max(0, int(r[i] + (r[i] - blurred_r[i]) * strength)))
        out[i * 3 + 1] = min(255, max(0, int(g[i] + (g[i] - blurred_g[i]) * strength)))
        out[i * 3 + 2] = min(255, max(0, int(b[i] + (b[i] - blurred_b[i]) * strength)))
    return bytes(out)


def _blur_channel(channel, w, h):
    """Box blur 3x3 для одного канала. channel: bytes/bytearray."""
    out = bytearray(w * h)
    for y in range(h):
        y0 = max(0, y - 1)
        y1 = min(h - 1, y + 1)
        for x in range(w):
            x0 = max(0, x - 1)
            x1 = min(w - 1, x + 1)
            total = 0
            count = 0
            for yy in range(y0, y1 + 1):
                base = yy * w
                for xx in range(x0, x1 + 1):
                    total += channel[base + xx]
                    count += 1
            out[y * w + x] = total // count
    return out


# ─── Комбинированные ─────────────────────────────────────────

def auto_enhance(rgb_bytes):
    """Комбинированное улучшение."""
    out = brightness(rgb_bytes, 1.15)
    out = contrast(out, 1.10)
    return out


# ─── Фильтры ─────────────────────────────────────────────────

def _to_gray(rgb_bytes):
    n = len(rgb_bytes) // 3
    r = rgb_bytes[0::3]
    g = rgb_bytes[1::3]
    b = rgb_bytes[2::3]
    gray = bytearray(n)
    for i in range(n):
        gray[i] = (r[i] * 77 + g[i] * 150 + b[i] * 29) >> 8
    out = bytearray(len(rgb_bytes))
    out[0::3] = gray
    out[1::3] = gray
    out[2::3] = gray
    return bytes(out)


def _tint(rgb_bytes, r_mult, g_mult, b_mult):
    out = bytearray(rgb_bytes)
    out[0::3] = rgb_bytes[0::3].translate(_lut_brightness(r_mult))
    out[1::3] = rgb_bytes[1::3].translate(_lut_brightness(g_mult))
    out[2::3] = rgb_bytes[2::3].translate(_lut_brightness(b_mult))
    return bytes(out)


FILTERS = {
    "none":      lambda b, w, h: b,
    "vivid":     lambda b, w, h: contrast(brightness(b, 1.05), 1.20),
    "vivid+":    lambda b, w, h: contrast(saturation(b, 1.4), 1.15),
    "film":      lambda b, w, h: contrast(warmth(b, 0.3), 1.05),
    "noir":      lambda b, w, h: contrast(_to_gray(b), 1.30),
    "noir_soft": lambda b, w, h: contrast(_to_gray(b), 1.05),
    "vintage":   lambda b, w, h: contrast(warmth(b, 0.4), 0.92),
    "cinematic": lambda b, w, h: contrast(warmth(b, -0.2), 1.15),
    "cold":      lambda b, w, h: warmth(b, -0.4),
    "warm":      lambda b, w, h: warmth(b, 0.4),
    "sepia":     lambda b, w, h: _tint(_to_gray(b), 1.10, 0.95, 0.75),
    "cyanotype": lambda b, w, h: _tint(_to_gray(b), 0.75, 0.90, 1.15),
    "fade":      lambda b, w, h: contrast(brightness(b, 1.15), 0.85),
    "dramatic":  lambda b, w, h: contrast(shadows(b, 20), 1.35),
    "retro":     lambda b, w, h: warmth(contrast(b, 0.90), 0.5),
    "sunset":    lambda b, w, h: warmth(brightness(b, 1.05), 0.6),
    "mint":      lambda b, w, h: _tint(b, 0.95, 1.05, 1.0),
    "pink":      lambda b, w, h: _tint(b, 1.05, 0.95, 1.0),
}


# ─── Геометрия ───────────────────────────────────────────────

def flip_h(rgb_bytes, w, h):
    out = bytearray(len(rgb_bytes))
    stride = w * 3
    for y in range(h):
        row = rgb_bytes[y * stride:(y + 1) * stride]
        rev = bytearray(stride)
        for x in range(w):
            rev[x * 3:x * 3 + 3] = row[(w - 1 - x) * 3:(w - 1 - x) * 3 + 3]
        out[y * stride:(y + 1) * stride] = rev
    return bytes(out)


def flip_v(rgb_bytes, w, h):
    stride = w * 3
    out = bytearray(len(rgb_bytes))
    for y in range(h):
        out[y * stride:(y + 1) * stride] = rgb_bytes[(h - 1 - y) * stride:(h - y) * stride]
    return bytes(out)


def rotate_90(rgb_bytes, w, h, clockwise=True):
    new_w, new_h = h, w
    out = bytearray(len(rgb_bytes))
    for y in range(h):
        for x in range(w):
            src = (y * w + x) * 3
            if clockwise:
                nx, ny = h - 1 - y, x
            else:
                nx, ny = y, w - 1 - x
            dst = (ny * new_w + nx) * 3
            out[dst:dst + 3] = rgb_bytes[src:src + 3]
    return bytes(out), new_w, new_h


def crop(rgb_bytes, w, h, x, y, cw, ch):
    """Вырезать прямоугольник (x, y, cw, ch). Возвращает (bytes, cw, ch)."""
    x = max(0, min(x, w - 1))
    y = max(0, min(y, h - 1))
    cw = max(1, min(cw, w - x))
    ch = max(1, min(ch, h - y))
    out = bytearray(cw * ch * 3)
    for row in range(ch):
        src_start = ((y + row) * w + x) * 3
        dst_start = row * cw * 3
        out[dst_start:dst_start + cw * 3] = rgb_bytes[src_start:src_start + cw * 3]
    return bytes(out), cw, ch