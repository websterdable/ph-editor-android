"""Загрузка/сохранение и базовые операции с изображениями без NumPy.

Изображение хранится как bytes в формате RGB (3 байта на пиксель).
Операции — через bytes.translate и срезы (C-скорость).
"""
import os
from kivy.core.image import Image as CoreImage
from kivy.graphics.texture import Texture
from kivy.logger import Logger


def load_image(path):
    """Загрузить файл -> (rgb_bytes, width, height) или None."""
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
        # RGBA -> RGB через срезы
        r = pixels[0::4]
        g = pixels[1::4]
        b = pixels[2::4]
        rgb = bytearray(w * h * 3)
        rgb[0::3] = r
        rgb[1::3] = g
        rgb[2::3] = b
        Logger.info(f"load_image: {w}x{h}, {len(rgb)} байт")
        return bytes(rgb), w, h
    except Exception as e:
        Logger.error(f"load_image: {e}")
        return None


def save_image(rgb_bytes, w, h, path):
    """Сохранить RGB-bytes -> файл."""
    try:
        rgba = bytearray(w * h * 4)
        rgba[0::4] = rgb_bytes[0::3]
        rgba[1::4] = rgb_bytes[1::3]
        rgba[2::4] = rgb_bytes[2::3]
        rgba[3::4] = b'\xff' * (w * h)
        tex = Texture.create(size=(w, h), colorfmt='rgba')
        tex.blit_buffer(bytes(rgba), colorfmt='rgba', bufferfmt='ubyte')
        tex.save(path)
        return True
    except Exception as e:
        Logger.error(f"save_image: {e}")
        return False


def to_texture(rgb_bytes, w, h):
    """RGB bytes -> Kivy Texture для отображения."""
    rgba = bytearray(w * h * 4)
    rgba[0::4] = rgb_bytes[0::3]
    rgba[1::4] = rgb_bytes[1::3]
    rgba[2::4] = rgb_bytes[2::3]
    rgba[3::4] = b'\xff' * (w * h)
    tex = Texture.create(size=(w, h), colorfmt='rgba')
    tex.blit_buffer(bytes(rgba), colorfmt='rgba', bufferfmt='ubyte')
    return tex