"""Высокоуровневые ИИ-операции над изображениями.

Все функции принимают numpy (H,W,3) uint8 и возвращают numpy или None.
"""
import numpy as np
from kivy.logger import Logger

from app.core.ai_engine import AIEngine


# ---------- Хелперы ----------

def _to_nchw(arr, mean=0.0, std=255.0):
    """HWC uint8 -> NCHW float32, нормализованный."""
    x = arr.astype(np.float32) / std - mean
    return np.transpose(x, (2, 0, 1))[None, ...]


def _from_nchw(tensor):
    """NCHW float32 -> HWC uint8."""
    out = tensor[0]
    out = np.transpose(out, (1, 2, 0))
    return np.clip(out * 255.0, 0, 255).astype(np.uint8)


def _resize_nearest(arr, w, h):
    H, W = arr.shape[:2]
    ys = (np.arange(h) * (H / h)).astype(np.int32)
    xs = (np.arange(w) * (W / w)).astype(np.int32)
    return arr[ys][:, xs]


def _resize_bilinear(arr, w, h):
    """Простой bilinear resize для входов моделей."""
    H, W = arr.shape[:2]
    x_ratio = (W - 1) / max(1, w - 1)
    y_ratio = (H - 1) / max(1, h - 1)
    x = np.arange(w) * x_ratio
    y = np.arange(h) * y_ratio
    x0 = x.astype(np.int32)
    y0 = y.astype(np.int32)
    x1 = np.minimum(x0 + 1, W - 1)
    y1 = np.minimum(y0 + 1, H - 1)
    fx = (x - x0)[None, :, None]
    fy = (y - y0)[:, None, None]
    a = arr[y0][:, x0].astype(np.float32)
    b = arr[y0][:, x1].astype(np.float32)
    c = arr[y1][:, x0].astype(np.float32)
    d = arr[y1][:, x1].astype(np.float32)
    top = a * (1 - fx) + b * fx
    bot = c * (1 - fx) + d * fx
    out = top * (1 - fy) + bot * fy
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------- Face detection (YuNet) ----------

def detect_faces(engine: AIEngine, image):
    """Вернуть список боксов [(x, y, w, h), ...] или []."""
    if not engine.has_model("yunet"):
        return []
    H, W = image.shape[:2]
    inp_w, inp_h = 320, 320
    small = _resize_bilinear(image, inp_w, inp_h)
    x = _to_nchw(small, mean=0.0, std=1.0)
    spec = engine.input_spec("yunet")
    if spec is None:
        return []
    name, _ = spec
    out = engine.run("yunet", {name: x})
    if out is None:
        return []
    # YuNet возвращает [boxes, scores, landmarks] — формат зависит от экспорта.
    # Универсальная распаковка: ищем массив с оценками > 0.6.
    try:
        boxes = out[0]
        scores = out[1] if len(out) > 1 else np.ones((boxes.shape[0], 1))
        sx, sy = W / inp_w, H / inp_h
        faces = []
        for i in range(boxes.shape[0]):
            score = float(scores[i]) if scores.ndim > 1 else float(scores[i])
            if score < 0.6:
                continue
            bx, by, bw, bh = boxes[i][:4]
            faces.append((
                int(bx * sx), int(by * sy),
                int(bw * sx), int(bh * sy),
            ))
        return faces
    except Exception as e:
        Logger.error(f"detect_faces: {e}")
        return []


# ---------- Апскейл (Real-ESRGAN) ----------

def upscale(engine: AIEngine, image, scale=4):
    """Апскейл изображения. Возвращает numpy или None."""
    if not engine.has_model("realesrgan_x4"):
        return None
    x = _to_nchw(image)
    spec = engine.input_spec("realesrgan_x4")
    if spec is None:
        return None
    name, _ = spec
    out = engine.run("realesrgan_x4", {name: x})
    if out is None:
        return None
    return _from_nchw(out[0])


# ---------- Восстановление лиц (GFPGAN) ----------

def restore_face(engine: AIEngine, image, faces=None):
    """Восстановить лица. Если faces=None, детектируем YuNet."""
    if not engine.has_model("gfpgan"):
        return None
    if faces is None:
        faces = detect_faces(engine, image)
    if not faces:
        # Нет лиц — вернуть оригинал без изменений
        return image

    result = image.copy()
    for (x, y, w, h) in faces:
        # Расширим бокс на 20% для контекста
        pad_x, pad_y = int(w * 0.2), int(h * 0.2)
        x0 = max(0, x - pad_x)
        y0 = max(0, y - pad_y)
        x1 = min(image.shape[1], x + w + pad_x)
        y1 = min(image.shape[0], y + h + pad_y)
        crop = image[y0:y1, x0:x1]
        # GFPGAN обычно работает с 512x512
        resized = _resize_bilinear(crop, 512, 512)
        xin = _to_nchw(resized, mean=0.5, std=0.5)
        spec = engine.input_spec("gfpgan")
        if spec is None:
            continue
        name, _ = spec
        out = engine.run("gfpgan", {name: xin})
        if out is None:
            continue
        restored = _from_nchw(out[0])
        # Возврат к оригинальному размеру и вставка
        restored = _resize_bilinear(restored, x1 - x0, y1 - y0)
        result[y0:y1, x0:x1] = restored
    return result


# ---------- Удаление шума (SCUNet) ----------

def denoise(engine: AIEngine, image, strength=1.0):
    if not engine.has_model("scunet"):
        return None
    x = _to_nchw(image)
    spec = engine.input_spec("scunet")
    if spec is None:
        return None
    name, _ = spec
    out = engine.run("scunet", {name: x})
    if out is None:
        return None
    clean = _from_nchw(out[0])
    if strength >= 0.99:
        return clean
    # Смешивание с оригиналом
    a = image.astype(np.float32) * (1 - strength)
    b = clean.astype(np.float32) * strength
    return np.clip(a + b, 0, 255).astype(np.uint8)


# ---------- Колоризация (DDColor) ----------

def colorize(engine: AIEngine, image):
    if not engine.has_model("ddcolor"):
        return None
    # DDColor ожидает grayscale
    gray = image.mean(axis=2).astype(np.uint8)
    gray = np.stack([gray] * 3, axis=2)
    x = _to_nchw(gray)
    spec = engine.input_spec("ddcolor")
    if spec is None:
        return None
    name, _ = spec
    out = engine.run("ddcolor", {name: x})
    if out is None:
        return None
    return _from_nchw(out[0])


# ---------- Состаривание / омоложение (SAM) ----------

def age_transform(engine: AIEngine, image, direction="old", amount=0.5):
    """direction: 'old' | 'young'. amount: 0..1."""
    if not engine.has_model("sam_age"):
        return None
    faces = detect_faces(engine, image)
    if not faces:
        return image  # нет лиц — вернуть как есть
    # В реальном SAM-инференсе здесь была бы генерация.
    # Пока возвращаем тонированную версию как плейсхолдер.
    # TODO: заменить на реальный вызов после экспорта SAM.
    if direction == "old":
        factor = 1.0 - amount * 0.3
        out = image.astype(np.float32) * factor
        out[..., 2] *= 1.0 + amount * 0.1
        return np.clip(out, 0, 255).astype(np.uint8)
    else:
        factor = 1.0 + amount * 0.2
        out = image.astype(np.float32) * factor
        return np.clip(out, 0, 255).astype(np.uint8)


# ---------- Удаление фона (MODNet) ----------

def remove_background(engine: AIEngine, image):
    """Возвращает RGBA с альфой (0 — фон, 255 — человек)."""
    if not engine.has_model("modnet"):
        return None
    H, W = image.shape[:2]
    # MODNet работает с размерами кратными 32
    target_w = (W // 32) * 32
    target_h = (H // 32) * 32
    target_w = max(256, target_w)
    target_h = max(256, target_h)
    small = _resize_bilinear(image, target_w, target_h)
    x = _to_nchw(small, mean=0.5, std=0.5)
    spec = engine.input_spec("modnet")
    if spec is None:
        return None
    name, _ = spec
    out = engine.run("modnet", {name: x})
    if out is None:
        return None
    alpha = out[0][0]  # (1, H, W) -> (H, W)
    if alpha.ndim == 3:
        alpha = alpha[0]
    alpha = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    # Ресайз альфы к оригинальному размеру
    if alpha.shape != (H, W):
        alpha = _resize_bilinear(
            np.stack([alpha] * 3, axis=2), W, H
        )[:, :, 0]
    rgba = np.dstack([image, alpha])
    return rgba


# ---------- Удаление объектов (LaMa) ----------

def inpaint(engine: AIEngine, image, mask):
    """mask: numpy (H, W) uint8, 1 — закрасить. Возвращает RGB."""
    if not engine.has_model("lama"):
        return None
    H, W = image.shape[:2]
    # LaMa требует размер кратный 8
    target_w = ((W + 7) // 8) * 8
    target_h = ((H + 7) // 8) * 8
    img_in = _resize_bilinear(image, target_w, target_h)
    mask_in = _resize_bilinear(
        np.stack([mask] * 3, axis=2), target_w, target_h
    )[:, :, 0]
    # Вход LaMa: image (1,3,H,W), mask (1,1,H,W)
    xi = _to_nchw(img_in)
    xm = (mask_in[None, None, ...] > 0).astype(np.float32)
    spec_i = engine.input_spec("lama")
    if spec_i is None:
        return None
    name_i, _ = spec_i
    # Второй вход — маска
    sess = engine._sessions["lama"]
    inputs = sess.get_inputs()
    feed = {inputs[0].name: xi, inputs[1].name: xm}
    out = engine.run("lama", feed)
    if out is None:
        return None
    result = _from_nchw(out[0])
    if result.shape[:2] != (H, W):
        result = _resize_bilinear(result, W, H)
    return result