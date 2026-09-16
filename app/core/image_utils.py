"""Загрузка, сохранение и базовые улучшения изображений.

Использует только NumPy и Kivy — никаких внешних зависимостей,
которые могут не собраться на Android.
"""
import numpy as np
from kivy.core.image import Image as CoreImage
from kivy.graphics.texture import Texture
from kivy.logger import Logger


def load_image(path):
    """Загрузить файл -> numpy (H, W, 3), uint8, RGB. None при ошибке."""
    try:
        core = CoreImage(path, keep_data=True)
        w, h = core.texture.size
        pixels = core.texture.pixels
        arr = np.frombuffer(pixels, dtype=np.uint8).reshape(h, w, 4)
        # Kivy-текстура снизу вверх -> переворачиваем; убираем альфу
        return arr[::-1, :, :3].copy()
    except Exception as e:
        Logger.error(f"image_utils.load_image: {e}")
        return None


def save_image(arr, path):
    """Сохранить numpy (H, W, 3 или 4) uint8 в PNG/JPEG. True при успехе."""
    try:
        if arr is None:
            return False
        if arr.ndim == 2:
            arr = np.dstack([arr] * 3)
        h, w = arr.shape[:2]
        if arr.shape[2] == 3:
            alpha = np.full((h, w, 1), 255, dtype=np.uint8)
            rgba = np.concatenate([arr, alpha], axis=2)
        else:
            rgba = arr
        rgba = rgba[::-1]  # Kivy ждёт снизу вверх
        tex = Texture.create(size=(w, h), colorfmt="rgba")
        tex.blit_buffer(rgba.tobytes(), colorfmt="rgba", bufferfmt="ubyte")
        tex.save(path)
        return True
    except Exception as e:
        Logger.error(f"image_utils.save_image: {e}")
        return False


def to_texture(arr):
    """numpy -> Kivy Texture для показа в Image widget."""
    if arr is None:
        return None
    h, w = arr.shape[:2]
    if arr.ndim == 2:
        arr = np.dstack([arr] * 3)
    if arr.shape[2] == 3:
        alpha = np.full((h, w, 1), 255, dtype=np.uint8)
        rgba = np.concatenate([arr, alpha], axis=2)
    else:
        rgba = arr
    rgba = rgba[::-1]
    tex = Texture.create(size=(w, h), colorfmt="rgba")
    tex.blit_buffer(rgba.tobytes(), colorfmt="rgba", bufferfmt="ubyte")
    return tex


# --------- Базовые улучшения (чистый NumPy) ---------

def adjust_brightness(arr, factor=1.15):
    out = arr.astype(np.float32) * factor
    return np.clip(out, 0, 255).astype(np.uint8)


def adjust_contrast(arr, factor=1.1):
    mean = float(arr.mean())
    out = (arr.astype(np.float32) - mean) * factor + mean
    return np.clip(out, 0, 255).astype(np.uint8)


def auto_enhance(arr):
    """Комбинированное улучшение: яркость + контраст."""
    out = adjust_brightness(arr, 1.15)
    out = adjust_contrast(out, 1.10)
    return out


def resize_max_side(arr, max_side=2048):
    """Уменьшить изображение так, чтобы длинная сторона <= max_side."""
    h, w = arr.shape[:2]
    longest = max(h, w)
    if longest <= max_side:
        return arr
    scale = max_side / longest
    new_h, new_w = int(h * scale), int(w * scale)
    ys = (np.arange(new_h) * (h / new_h)).astype(np.int32)
    xs = (np.arange(new_w) * (w / new_w)).astype(np.int32)
    return arr[ys][:, xs]