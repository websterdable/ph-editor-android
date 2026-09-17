"""Базовые операции над изображениями через bytes.translate (без NumPy)."""


def _brightness_table(factor):
    return bytes([min(255, max(0, int(i * factor))) for i in range(256)])


def _contrast_table(factor):
    return bytes([min(255, max(0, int((i - 128) * factor + 128))) for i in range(256)])


def brightness(rgb_bytes, factor):
    """factor: 0.5..1.5, 1.0 — без изменений."""
    return rgb_bytes.translate(_brightness_table(factor))


def contrast(rgb_bytes, factor):
    """factor: 0.5..1.5."""
    return rgb_bytes.translate(_contrast_table(factor))


def warmth(rgb_bytes, factor):
    """factor: -1..1. Только к R и B каналам."""
    if abs(factor) < 0.01:
        return rgb_bytes
    r_factor = 1.0 + factor * 0.15
    b_factor = 1.0 - factor * 0.15
    r_table = _brightness_table(r_factor)
    b_table = _brightness_table(b_factor)
    out = bytearray(rgb_bytes)
    out[0::3] = rgb_bytes[0::3].translate(r_table)
    out[2::3] = rgb_bytes[2::3].translate(b_table)
    return bytes(out)


def auto_enhance(rgb_bytes):
    """Комбинированное улучшение."""
    out = brightness(rgb_bytes, 1.15)
    out = contrast(out, 1.10)
    return out


def flip_h(rgb_bytes, w, h):
    """Отразить по горизонтали."""
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
    """Отразить по вертикали."""
    stride = w * 3
    out = bytearray(len(rgb_bytes))
    for y in range(h):
        out[y * stride:(y + 1) * stride] = rgb_bytes[(h - 1 - y) * stride:(h - y) * stride]
    return bytes(out)


def rotate_90(rgb_bytes, w, h, clockwise=True):
    """Поворот на 90°. Возвращает (bytes, new_w, new_h)."""
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


# Фильтры (быстрые, через translate)
FILTERS = {
    "none":      lambda b, w, h: b,
    "vivid":     lambda b, w, h: contrast(brightness(b, 1.05), 1.20),
    "film":      lambda b, w, h: contrast(warmth(b, 0.3), 1.05),
    "noir":      lambda b, w, h: contrast(_to_gray(b), 1.25),
    "vintage":   lambda b, w, h: contrast(warmth(b, 0.4), 0.92),
    "cinematic": lambda b, w, h: contrast(warmth(b, -0.2), 1.15),
    "cold":      lambda b, w, h: warmth(b, -0.4),
    "warm":      lambda b, w, h: warmth(b, 0.4),
}


def _to_gray(rgb_bytes):
    """Преобразовать в оттенки серого через срезы."""
    r = rgb_bytes[0::3]
    g = rgb_bytes[1::3]
    b = rgb_bytes[2::3]
    # Приближённое: gray = (r + g + b) / 3
    gray = bytearray(len(r))
    for i in range(len(r)):
        gray[i] = (r[i] + g[i] + b[i]) // 3
    out = bytearray(len(rgb_bytes))
    out[0::3] = gray
    out[1::3] = gray
    out[2::3] = gray
    return bytes(out)