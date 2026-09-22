'''
"""Высокоуровневые ИИ-операции (апскейл, лица, фон)."""
import numpy as np
from kivy.logger import Logger
from app.core.ai_engine import AIEngine


def _to_nchw(img_rgb):
    """(H,W,3) uint8 -> (1,3,H,W) float32 [0..1]."""
    x = img_rgb.astype(np.float32) / 255.0
    return np.transpose(x, (2, 0, 1))[None, ...]


def _from_nchw(tensor):
    """(1,3,H,W) float32 -> (H,W,3) uint8."""
    out = tensor[0]
    out = np.transpose(out, (1, 2, 0))
    return np.clip(out * 255.0, 0, 255).astype(np.uint8)


def detect_faces(engine: AIEngine, img_rgb):
    """YuNet: возвращает список боксов [(x,y,w,h), ...]."""
    if not engine.has_model("yunet"):
        return []
    H, W = img_rgb.shape[:2]
    # YuNet ожидает 320x320
    import numpy as np
    # Простой resize через numpy
    ys = (np.arange(320) * (H / 320)).astype(np.int32)
    xs = (np.arange(320) * (W / 320)).astype(np.int32)
    small = img_rgb[ys][:, xs]
    x = np.transpose(small.astype(np.float32), (2, 0, 1))[None, ...]
    out = engine.run("yunet", {"input": x})
    if out is None:
        return []
    # YuNet outputs: boxes, scores, landmarks. Формат зависит от экспорта.
    # Упрощённая распаковка: ищем массив с confidence.
    try:
        scores = list(out.values())[-1]  # предположительно scores
        boxes = list(out.values())[0]
        faces = []
        for i in range(boxes.shape[1]):
            conf = scores[0, i]
            if conf < 0.6:
                continue
            bx, by, bw, bh = boxes[0, i, :4]
            faces.append((int(bx * W / 320), int(by * H / 320),
                          int(bw * W / 320), int(bh * H / 320)))
        return faces
    except Exception as e:
        Logger.error(f"detect_faces: {e}")
        return []


def upscale(engine: AIEngine, img_rgb):
    """Real-ESRGAN: апскейл x4."""
    if not engine.has_model("realesrgan_x4"):
        return None
    x = _to_nchw(img_rgb)
    out = engine.run("realesrgan_x4", {"input": x})
    if out is None:
        return None
    # Выход обычно "output"
    key = list(out.keys())[0]
    return _from_nchw(out[key])


def remove_background(engine: AIEngine, img_rgb):
    """MODNet: возвращает RGBA (H,W,4)."""
    if not engine.has_model("modnet"):
        return None
    H, W = img_rgb.shape[:2]
    # MODNet требует размер кратный 32
    tw = (W // 32) * 32
    th = (H // 32) * 32
    tw, th = max(256, tw), max(256, th)
    # Resize
    import numpy as np
    ys = (np.arange(th) * (H / th)).astype(np.int32)
    xs = (np.arange(tw) * (W / tw)).astype(np.int32)
    small = img_rgb[ys][:, xs]
    x = np.transpose(small.astype(np.float32) / 255.0, (2, 0, 1))[None, ...]
    out = engine.run("modnet", {"input": x})
    if out is None:
        return None
    alpha = list(out.values())[0][0, 0]  # (th, tw)
    # Resize alpha к оригиналу
    ays = (np.arange(H) * (th / H)).astype(np.int32)
    axs = (np.arange(W) * (tw / W)).astype(np.int32)
    alpha = alpha[ays][:, axs]
    alpha = np.clip(alpha * 255, 0, 255).astype(np.uint8)
    rgba = np.dstack([img_rgb, alpha])
    return rgba

'''





"""Вспомогательные операции для ИИ-модуля."""

from kivy.logger import Logger

def resize_hwc_u8(rgb, w, h, tw, th):
    """Nearest-neighbor resize для HWC uint8."""
    out = bytearray(tw * th * 3)
    for y in range(th):
        sy = y * h // th
        row_src = sy * w
        row_dst = y * tw
        for x in range(tw):
            sx = x * w // tw
            src = (row_src + sx) * 3
            dst = (row_dst + x) * 3
            out[dst:dst + 3] = rgb[src:src + 3]
    return bytes(out)


def upscale(engine, img_rgb_bytes, w, h):
    """Real-ESRGAN. Возвращает (bytes, w, h) или None."""
    Logger.info(f"upscale: вход {w}x{h}")
    result = engine.run("realesrgan_x4", img_rgb_bytes, w, h,
                         scale=1.0 / 255.0)
    if result is None:
        return None
    return result


def remove_background(engine, img_rgb_bytes, w, h):
    """MODNet. Возвращает (bytes, w, h) или None. Выход — RGB (без альфы пока)."""
    # MODNet требует размер кратный 32
    tw = max(256, (w // 32) * 32)
    th = max(256, (h // 32) * 32)
    if tw != w or th != h:
        small = resize_hwc_u8(img_rgb_bytes, w, h, tw, th)
    else:
        small = img_rgb_bytes

    result = engine.run("modnet", small, tw, th, scale=1.0 / 255.0)
    if result is None:
        return None
    out_bytes, ow, oh = result
    # Пока просто возвращаем результат (альфу добавим позже)
    return out_bytes, ow, oh