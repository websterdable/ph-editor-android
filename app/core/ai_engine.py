"""Обёртка над OnnxHelper. Модели ищем в файловой системе приложения.

Поддерживает:
- INT8-квантизованные модели (суффикс _int8.onnx)
- Companion-файлы .data (для моделей с external weights)
- Автоматическое копирование из бандла APK в приватную папку
"""
import os
import shutil
from kivy.logger import Logger
from jnius import autoclass

OnnxHelper = autoclass("org.local.photoai.OnnxHelper")


# Публичное имя -> список файлов (первый — основной .onnx, далее companion-файлы)
MODEL_FILES = {
    "yunet":         ["yunet_int8.onnx"],
    "modnet":        ["modnet_int8.onnx"],
    "realesrgan_x4": ["realesrgan_x4_int8.onnx"],
}

# Основной .onnx для каждой модели (для передачи в loadModel)
MODEL_MAIN = {
    "yunet":         "yunet_int8.onnx",
    "modnet":        "modnet_int8.onnx",
    "realesrgan_x4": "realesrgan_x4_int8.onnx",
}


def _candidate_dirs():
    cwd = os.getcwd()
    here = os.path.dirname(os.path.abspath(__file__))
    return [
        os.path.join(cwd, "assets", "models"),
        os.path.join(cwd, "app", "assets", "models"),
        os.path.join(cwd, "..", "assets", "models"),
        os.path.abspath(os.path.join(here, "..", "..", "assets", "models")),
        os.path.abspath(os.path.join(here, "..", "assets", "models")),
        "/data/data/org.local.photoai/files/app/assets/models",
        "/data/user/0/org.local.photoai/files/app/assets/models",
    ]


def _find_in_bundle(filename):
    for d in _candidate_dirs():
        p = os.path.join(d, filename)
        try:
            if os.path.exists(p) and os.path.getsize(p) > 0:
                return p
        except Exception:
            continue
    return None


def _copy_asset(fname, model_dir):
    dst = os.path.join(model_dir, fname)
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return True
    src = _find_in_bundle(fname)
    if src is None:
        return False
    try:
        shutil.copyfile(src, dst)
        size_mb = os.path.getsize(dst) / 1024 / 1024
        Logger.info(f"AIEngine: скопирован {fname} ({size_mb:.1f} МБ)")
        return True
    except Exception as e:
        Logger.error(f"AIEngine: ошибка копирования {fname}: {e}")
        return False


def _ensure_models(model_dir):
    os.makedirs(model_dir, exist_ok=True)
    for name, files in MODEL_FILES.items():
        for fname in files:
            if not _copy_asset(fname, model_dir):
                Logger.warning(f"AIEngine: {fname} не найден в бандле")


class AIEngine:
    def __init__(self, model_dir):
        self.model_dir = model_dir
        self.handles = {}
        _ensure_models(model_dir)
        # Логируем, что в итоге есть
        for name in MODEL_MAIN:
            p = os.path.join(model_dir, MODEL_MAIN[name])
            sz = os.path.getsize(p) // 1024 if os.path.exists(p) else 0
            Logger.info(f"AIEngine: {name} — {sz} КБ")

    def has_model(self, name):
        if name not in MODEL_MAIN:
            return False
        p = os.path.join(self.model_dir, MODEL_MAIN[name])
        return os.path.exists(p) and os.path.getsize(p) > 0

    def load(self, name):
        if name in self.handles:
            return True
        if name not in MODEL_MAIN:
            return False
        path = os.path.join(self.model_dir, MODEL_MAIN[name])
        if not os.path.exists(path):
            return False
        h_id = OnnxHelper.loadModel(path)
        if h_id < 0:
            Logger.error(f"AIEngine: не загрузилась {name}")
            return False
        self.handles[name] = h_id
        Logger.info(f"AIEngine: загружена {name}, handle={h_id}")
        return True

    def run(self, name, hwc_u8, w, h, scale=1.0 / 255.0):
        """hwc_u8: bytes. Возвращает (bytes_out, w_out, h_out) или None."""
        if not self.load(name):
            return None
        try:
            import struct

            packed = OnnxHelper.runModelU8(
                self.handles[name], hwc_u8, w, h, float(scale))

            if packed is None:
                err = OnnxHelper.getLastError()
                Logger.error(f"AIEngine.run({name}): {err}")
                return None

            data = bytes(packed)
            # Заголовок: 4 байта rank + 16 байт (4 int32 = до 4 измерений)
            # Итого 20 байт до данных
            if len(data) < 20:
                Logger.error(f"AIEngine.run({name}): packed слишком мал ({len(data)})")
                return None

            rank = struct.unpack_from("<i", data, 0)[0]
            d0, d1, d2, d3 = struct.unpack_from("<iiii", data, 4)
            out_shape = [d0, d1, d2, d3][:rank]
            float_bytes = data[20:]  # ← было 16, теперь правильно 20

            Logger.info(f"AIEngine.run({name}): out shape={out_shape}")

            if len(out_shape) == 4 and out_shape[1] == 3:
                hwc_out = OnnxHelper.chwF32ToHwcU8(float_bytes, out_shape)
                if hwc_out is None:
                    Logger.error(f"AIEngine.run({name}): chwF32ToHwcU8 -> None")
                    return None
                return bytes(hwc_out), out_shape[3], out_shape[2]
            elif len(out_shape) == 4 and out_shape[1] == 1:
                hwc_out = OnnxHelper.chw1ToHwcU8(float_bytes, out_shape)
                if hwc_out is None:
                    Logger.error(f"AIEngine.run({name}): chw1ToHwcU8 -> None")
                    return None
                return bytes(hwc_out), out_shape[3], out_shape[2]
            else:
                Logger.error(f"AIEngine.run({name}): неожиданный shape {out_shape}")
                return None
        except Exception as e:
            Logger.exception(f"AIEngine.run({name}): {e}")
            return None