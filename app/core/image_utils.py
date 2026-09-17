"""Загрузка/сохранение изображений через Kivy CoreImage.

Без Pillow — работает на чистом Kivy + NumPy.
"""
import os
import numpy as np
from kivy.core.image import Image as CoreImage
from kivy.graphics.texture import Texture
from kivy.logger import Logger


def load_image(path):
    """Загрузить файл -> numpy (H, W, 3) uint8, RGB. None при ошибке."""
    if not path or not os.path.exists(path):
        Logger.error(f"load_image: файл не существует: {path}")
        return None
    try:
        core = CoreImage(path, keep_data=True)
        w, h = core.texture.size
        pixels = core.texture.pixels
        if not pixels:
            Logger.error("load_image: пустые пиксели")
            return None
        arr = np.frombuffer(pixels, dtype=np.uint8).reshape(h, w, 4)
        return arr[::-1, :, :3].copy()
    except Exception as e:
        Logger.error(f"load_image: {e}")
        return None


def save_image(arr, path):
    """Сохранить numpy (H, W, 3 или 4) uint8. True при успехе."""
    if arr is None:
        return False
    try:
        if arr.ndim == 2:
            arr = np.dstack([arr] * 3)
        h, w = arr.shape[:2]
        if arr.shape[2] == 3:
            alpha = np.full((h, w, 1), 255, dtype=np.uint8)
            rgba = np.concatenate([arr, alpha], axis=2)
        else:
            rgba = arr
        rgba = rgba[::-1]
        tex = Texture.create(size=(w, h), colorfmt="rgba")
        tex.blit_buffer(rgba.tobytes(), colorfmt="rgba", bufferfmt="ubyte")
        # Kivy Texture.save определяет формат по расширению
        tex.save(path)
        Logger.info(f"save_image: {path}")
        return True
    except Exception as e:
        Logger.error(f"save_image: {e}")
        return False


def to_texture(arr):
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


def resize_max_side(arr, max_side=2048):
    h, w = arr.shape[:2]
    longest = max(h, w)
    if longest <= max_side:
        return arr
    scale = max_side / longest
    new_h, new_w = int(h * scale), int(w * scale)
    ys = (np.arange(new_h) * (h / new_h)).astype(np.int32)
    xs = (np.arange(new_w) * (w / new_w)).astype(np.int32)
    return arr[ys][:, xs]