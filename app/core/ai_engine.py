"""Обёртка над Java-помощником OnnxHelper. Без numpy.

При первом запуске копирует модели из APK-бандла в приватную папку,
чтобы дальше читать их оттуда.
"""
import os
import shutil
from kivy.logger import Logger
from jnius import autoclass

OnnxHelper = autoclass("org.local.photoai.OnnxHelper")


# Возможные места, где Android распаковывает assets из APK
_BUNDLED_CANDIDATES = [
    "assets/models",           # относительно текущей рабочей директории
    "../assets/models",
    "app/assets/models",
    os.path.join(os.path.dirname(__file__), "..", "..", "assets", "models"),
    os.path.join(os.path.dirname(__file__), "..", "assets", "models"),
]


def _find_bundled_dir(filename):
    """Ищем папку, где лежит файл модели в бандле APK."""
    for cand in _BUNDLED_CANDIDATES:
        p = os.path.abspath(cand)
        full = os.path.join(p, filename)
        if os.path.exists(full):
            Logger.info(f"AIEngine: модель найдена в бандле: {full}")
            return p, full
    return None, None


def _ensure_models(model_dir, names):
    """Копируем модели из бандла в приватную папку, если их там нет."""
    os.makedirs(model_dir, exist_ok=True)
    for name in names:
        dst = os.path.join(model_dir, f"{name}.onnx")
        if os.path.exists(dst):
            continue
        _, src = _find_bundled_dir(f"{name}.onnx")
        if src is None:
            Logger.warning(f"AIEngine: в бандле нет {name}.onnx")
            continue
        try:
            shutil.copyfile(src, dst)
            size_mb = os.path.getsize(dst) / 1024 / 1024
            Logger.info(f"AIEngine: скопирована {name}.onnx ({size_mb:.1f} МБ)")
        except Exception as e:
            Logger.error(f"AIEngine: не удалось скопировать {name}: {e}")


class AIEngine:
    KNOWN_MODELS = ["yunet", "realesrgan_x4", "modnet", "gfpgan", "ddcolor"]

    def __init__(self, model_dir):
        self.model_dir = model_dir
        self.handles = {}
        _ensure_models(model_dir, self.KNOWN_MODELS)
        Logger.info(f"AIEngine: рабочая папка моделей: {model_dir}")
        # Логируем, что в итоге есть
        for name in self.KNOWN_MODELS:
            p = os.path.join(model_dir, f"{name}.onnx")
            exists = os.path.exists(p)
            Logger.info(f"AIEngine: {name}.onnx — {'OK' if exists else 'отсутствует'}")

    def has_model(self, name):
        return os.path.exists(os.path.join(self.model_dir, f"{name}.onnx"))

    def load(self, name):
        if name in self.handles:
            return True
        path = os.path.join(self.model_dir, f"{name}.onnx")
        if not os.path.exists(path):
            Logger.warning(f"AIEngine: нет модели {path}")
            return False
        h_id = OnnxHelper.loadModel(path)
        if h_id < 0:
            Logger.error(f"AIEngine: не загрузилась {name}")
            return False
        self.handles[name] = h_id
        Logger.info(f"AIEngine: загружена {name}, handle={h_id}")
        return True

    def run(self, name, hwc_u8, w, h, scale=1.0 / 255.0):
        """hwc_u8: bytes. Возвращает (bytes, w_out, h_out) или None."""
        if not self.load(name):
            return None
        try:
            result = OnnxHelper.runModelU8(
                self.handles[name], hwc_u8, w, h, float(scale))

            if result.error is not None:
                Logger.error(f"AIEngine.run({name}): {result.error}")
                return None

            out_shape = [int(result.shape[i]) for i in range(len(result.shape))]
            Logger.info(f"AIEngine.run({name}): out shape={out_shape}")

            if len(out_shape) == 4 and out_shape[1] == 3:
                hwc_out = OnnxHelper.chwF32ToHwcU8(result.data, result.shape)
                if hwc_out is None:
                    Logger.error(f"AIEngine.run({name}): chwF32ToHwcU8 -> None")
                    return None
                return bytes(hwc_out), out_shape[3], out_shape[2]
            elif len(out_shape) == 4 and out_shape[1] == 1:
                hwc_out = OnnxHelper.chw1ToHwcU8(result.data, result.shape)
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

    def unload(self, name):
        self.handles.pop(name, None)