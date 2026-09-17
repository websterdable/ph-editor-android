"""Все операции редактирования: базовые настройки, геометрия, фильтры."""
import numpy as np
from kivy.logger import Logger


# ---------- Базовые настройки ----------

def brightness(arr, factor):
    """factor: 0.5..1.5, где 1.0 — без изменений."""
    out = arr.astype(np.float32) * factor
    return np.clip(out, 0, 255).astype(np.uint8)


def contrast(arr, factor):
    """factor: 0.5..1.5."""
    mean = float(arr.mean())
    out = (arr.astype(np.float32) - mean) * factor + mean
    return np.clip(out, 0, 255).astype(np.uint8)


def saturation(arr, factor):
    """factor: 0..2, где 1.0 — без изменений."""
    gray = arr.mean(axis=2, keepdims=True)
    out = gray + (arr.astype(np.float32) - gray) * factor
    return np.clip(out, 0, 255).astype(np.uint8)


def warmth(arr, factor):
    """factor: -1..1, отрицательный — холоднее, положительный — теплее."""
    out = arr.astype(np.float32)
    out[..., 0] *= 1.0 + factor * 0.15   # R
    out[..., 2] *= 1.0 - factor * 0.15   # B
    return np.clip(out, 0, 255).astype(np.uint8)


def sharpness(arr, factor):
    """Unsharp mask. factor: 0..2."""
    if factor < 0.05:
        return arr
    blur = _box_blur(arr, 1)
    out = arr.astype(np.float32) + (arr.astype(np.float32) - blur.astype(np.float32)) * factor
    return np.clip(out, 0, 255).astype(np.uint8)


def _box_blur(arr, radius):
    """Простой box blur через накопление. Быстро на NumPy."""
    if radius <= 0:
        return arr.copy()
    k = radius * 2 + 1
    pad = np.pad(arr.astype(np.float32),
                 ((radius, radius), (radius, radius), (0, 0)),
                 mode="edge")
    out = np.zeros_like(arr, dtype=np.float32)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            out += pad[radius + dy:pad.shape[0] - radius + dy,
                       radius + dx:pad.shape[1] - radius + dx]
    out /= (k * k)
    return out.astype(np.uint8)


# ---------- Геометрия ----------

def rotate_90(arr, clockwise=True):
    return np.rot90(arr, k=-1 if clockwise else 1).copy()


def flip_h(arr):
    return arr[:, ::-1].copy()


def flip_v(arr):
    return arr[::-1, :].copy()


def crop(arr, x, y, w, h):
    H, W = arr.shape[:2]
    x = max(0, min(x, W - 1))
    y = max(0, min(y, H - 1))
    w = max(1, min(w, W - x))
    h = max(1, min(h, H - y))
    return arr[y:y + h, x:x + w].copy()


def resize(arr, new_w, new_h):
    """Простой ресайз через nearest (для быстрого превью)."""
    H, W = arr.shape[:2]
    ys = (np.arange(new_h) * (H / new_h)).astype(np.int32)
    xs = (np.arange(new_w) * (W / new_w)).astype(np.int32)
    return arr[ys][:, xs]


# ---------- Фильтры (LUT через матричные операции) ----------

def filter_vivid(arr):
    out = saturation(arr, 1.35)
    out = contrast(out, 1.12)
    return brightness(out, 1.03)


def filter_film(arr):
    out = arr.astype(np.float32)
    out[..., 0] = out[..., 0] * 0.95 + 15
    out[..., 1] = out[..., 1] * 0.97 + 5
    out[..., 2] = out[..., 2] * 1.02 + 10
    out = np.clip(out, 0, 255).astype(np.uint8)
    return contrast(out, 1.05)


def filter_noir(arr):
    gray = arr.mean(axis=2).astype(np.uint8)
    gray = np.stack([gray] * 3, axis=2)
    return contrast(gray, 1.25)


def filter_vintage(arr):
    out = arr.astype(np.float32)
    out[..., 0] *= 1.08
    out[..., 1] *= 1.02
    out[..., 2] *= 0.92
    out = np.clip(out, 0, 255).astype(np.uint8)
    return contrast(out, 0.92)


def filter_cinematic(arr):
    out = contrast(arr, 1.15)
    out = warmth(out, -0.15)
    out[..., 2] = np.clip(out[..., 2].astype(np.int32) + 10, 0, 255)
    return out.astype(np.uint8)


def filter_mono_cyan(arr):
    gray = arr.mean(axis=2)
    out = np.stack([gray * 0.85, gray * 0.95, gray * 1.10], axis=2)
    return np.clip(out, 0, 255).astype(np.uint8)


def filter_mono_sepia(arr):
    gray = arr.mean(axis=2)
    out = np.stack([gray * 1.10, gray * 0.95, gray * 0.75], axis=2)
    return np.clip(out, 0, 255).astype(np.uint8)


FILTERS = {
    "none":      lambda a: a,
    "vivid":     filter_vivid,
    "film":      filter_film,
    "noir":      filter_noir,
    "vintage":   filter_vintage,
    "cinematic": filter_cinematic,
    "cyan":      filter_mono_cyan,
    "sepia":     filter_mono_sepia,
}