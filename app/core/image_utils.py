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
    if not path:
        Logger.error("load_image: path пустой")
        return None
    if not os.path.exists(path):
        Logger.error(f"load_image: файл не существует: {path}")
        return None

    try:
        size = os.path.getsize(path)
        Logger.info(f"load_image: открываю {path} ({size} байт)")
        if size == 0:
            Logger.error("load_image: файл пустой")
            return None

        core = CoreImage(path, keep_data=True)
        w, h = core.texture.size
        pixels = core.texture.pixels
        Logger.info(f"load_image: {w}x{h}, pixels len = {len(pixels) if pixels else 0}")

        if not pixels:
            Logger.error("load_image: пустые пиксели")
            return None

        # Kivy CoreImage даёт пиксели снизу вверх, разворачиваем строки
        row_size = w * 4
        flipped = bytearray()
        for y in range(h - 1, -1, -1):
            flipped += pixels[y * row_size:(y + 1) * row_size]

        r = flipped[0::4]
        g = flipped[1::4]
        b = flipped[2::4]
        rgb = bytearray(w * h * 3)
        rgb[0::3] = r
        rgb[1::3] = g
        rgb[2::3] = b
        Logger.info(f"load_image: OK, {len(rgb)} байт RGB")
        return bytes(rgb), w, h
    except Exception as e:
        Logger.exception(f"load_image: ошибка: {e}")
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

def save_as_android(src_path, dst_path, fmt="JPEG", quality=90,
                    target_w=None, target_h=None):
    """Сохранить через Android BitmapFactory → compress.

    fmt: 'JPEG' | 'PNG' | 'WEBP'
    quality: 10..100 (для JPEG/WebP, для PNG игнорируется)
    target_w/target_h: ресайз, если заданы и отличаются от исходных.

    EXIF (геопозиция, модель камеры) НЕ переносится — метаданные удаляются.
    """
    try:
        from jnius import autoclass
        BitmapFactory = autoclass("android.graphics.BitmapFactory")
        Bitmap = autoclass("android.graphics.Bitmap")
        BCF = autoclass("android.graphics.Bitmap$CompressFormat")
        FOS = autoclass("java.io.FileOutputStream")

        bmp = BitmapFactory.decodeFile(src_path)
        if bmp is None:
            Logger.error(f"save_as_android: decodeFile failed: {src_path}")
            return False

        orig_w = bmp.getWidth()
        orig_h = bmp.getHeight()

        if target_w and target_h and (target_w != orig_w or target_h != orig_h):
            scaled = Bitmap.createScaledBitmap(bmp, int(target_w), int(target_h), True)
            bmp.recycle()
            bmp = scaled

        out = FOS(dst_path)
        ok = False
        if fmt == "JPEG":
            ok = bmp.compress(BCF.JPEG, int(quality), out)
        elif fmt == "WEBP":
            ok = bmp.compress(BCF.WEBP, int(quality), out)
            if not ok:
                Logger.warning("save_as_android: WEBP не поддержан, сохраняю JPEG")
                bmp.compress(BCF.JPEG, int(quality), out)
                ok = True
        else:
            ok = bmp.compress(BCF.PNG, 100, out)

        out.flush()
        out.close()
        bmp.recycle()

        if not ok:
            Logger.error("save_as_android: compress вернул False")
            return False

        Logger.info(f"save_as_android: OK -> {dst_path}")
        return True
    except Exception as e:
        Logger.exception(f"save_as_android: {e}")
        return False