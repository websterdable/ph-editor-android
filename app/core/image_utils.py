"""Загрузка, сохранение и базовые улучшения изображений через Pillow + NumPy.

Pillow надёжнее Kivy CoreImage: работает с любыми форматами (кроме HEIC без
плагина), корректно читает файлы из временных папок.
"""
import os
import numpy as np
from kivy.graphics.texture import Texture
from kivy.logger import Logger


def load_image(path):
    """Загрузить файл -> numpy (H, W, 3), uint8, RGB. None при ошибке."""
    if not path or not os.path.exists(path):
        Logger.error(f"load_image: файл не существует: {path}")
        return None

    size = os.path.getsize(path)
    Logger.info(f"load_image: открываем {path} ({size} байт)")

    try:
        from PIL import Image
        img = Image.open(path)
        Logger.info(f"load_image: формат={img.format}, размер={img.size}, mode={img.mode}")
        img = img.convert("RGB")
        arr = np.array(img)
        Logger.info(f"load_image: успешно, shape={arr.shape}")
        return arr
    except Exception as e:
        Logger.error(f"load_image: PIL failed -> {e}")
        # Попытка через Kivy CoreImage как запасной вариант
        try:
            from kivy.core.image import Image as CoreImage
            core = CoreImage(path, keep_data=True)
            w, h = core.texture.size
            pixels = core.texture.pixels
            if not pixels:
                Logger.error("load_image: CoreImage вернул пустые пиксели")
                return None
            arr = np.frombuffer(pixels, dtype=np.uint8).reshape(h, w, 4)
            return arr[::-1, :, :3].copy()
        except Exception as e2:
            Logger.error(f"load_image: CoreImage тоже failed -> {e2}")
            return None


def save_image(arr, path):
    """Сохранить numpy (H, W, 3 или 4) uint8 в PNG/JPEG. True при успехе."""
    if arr is None:
        return False
    try:
        from PIL import Image
        if arr.ndim == 2:
            img = Image.fromarray(arr, mode="L")
        elif arr.shape[2] == 4:
            img = Image.fromarray(arr, mode="RGBA")
        else:
            img = Image.fromarray(arr, mode="RGB")
        # Убедимся, что директория существует
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.save(path)
        Logger.info(f"save_image: сохранено {path} ({img.size[0]}x{img.size[1]})")
        return True
    except Exception as e:
        Logger.error(f"save_image: {e}")
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


def adjust_brightness(arr, factor=1.15):
    out = arr.astype(np.float32) * factor
    return np.clip(out, 0, 255).astype(np.uint8)


def adjust_contrast(arr, factor=1.1):
    mean = float(arr.mean())
    out = (arr.astype(np.float32) - mean) * factor + mean
    return np.clip(out, 0, 255).astype(np.uint8)


def auto_enhance(arr):
    out = adjust_brightness(arr, 1.15)
    out = adjust_contrast(out, 1.10)
    return out


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