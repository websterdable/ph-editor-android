"""Обёртка над OnnxHelper. Модели ищем в файловой системе приложения."""
import os
import shutil
from kivy.logger import Logger
from jnius import autoclass

OnnxHelper = autoclass("org.local.photoai.OnnxHelper")


def _candidate_dirs():
    """Все возможные места, где может лежать assets/models."""
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


def _find_model(name):
    """Найти файл модели в бандле. Возвращает полный путь или None."""
    filename = f"{name}.onnx"
    for d in _candidate_dirs():
        p = os.path.join(d, filename)
        try:
            if os.path.exists(p) and os.path.getsize(p) > 0:
                Logger.info(f"AIEngine: найден в бандле: {p}")
                return p
        except Exception:
            continue
    return None


def _ensure_models(model_dir, names):
    os.makedirs(model_dir, exist_ok=True)
    for name in names:
        dst = os.path.join(model_dir, f"{name}.onnx")
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            Logger.info(f"AIEngine: {name}.onnx уже в private dir")
            continue
        src = _find_model(name)
        if src is None:
            Logger.warning(f"AIEngine: {name}.onnx не найден ни в одной папке")
            # Логируем содержимое cwd для диагностики
            try:
                cwd = os.getcwd()
                Logger.info(f"AIEngine: cwd={cwd}")
                for root, dirs, files in os.walk(cwd):
                    depth = root[len(cwd):].count(os.sep)
                    if depth <= 3 and any(f.endswith('.onnx') for f in files):
                        Logger.info(f"AIEngine: нашли onnx в {root}")
                        for f in files:
                            if f.endswith('.onnx'):
                                Logger.info(f"AIEngine:   {f}")
            except Exception:
                pass
            continue
        try:
            shutil.copyfile(src, dst)
            size_mb = os.path.getsize(dst) / 1024 / 1024
            Logger.info(f"AIEngine: скопирована {name}.onnx ({size_mb:.1f} МБ) -> {dst}")
        except Exception as e:
            Logger.error(f"AIEngine: ошибка копирования {name}: {e}")


class AIEngine:
    KNOWN_MODELS = ["yunet", "realesrgan_x4", "modnet"]

    def __init__(self, model_dir):
        self.model_dir = model_dir
        self.handles = {}
        _ensure_models(model_dir, self.KNOWN_MODELS)
        for name in self.KNOWN_MODELS:
            p = os.path.join(model_dir, f"{name}.onnx")
            sz = os.path.getsize(p) // 1024 if os.path.exists(p) else 0
            Logger.info(f"AIEngine: {name}.onnx — {sz} КБ")

    def has_model(self, name):
        p = os.path.join(self.model_dir, f"{name}.onnx")
        return os.path.exists(p) and os.path.getsize(p) > 0

    def load(self, name):
        if name in self.handles:
            return True
        path = os.path.join(self.model_dir, f"{name}.onnx")
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
            if len(data) < 16:
                Logger.error(f"AIEngine.run({name}): packed слишком мал ({len(data)})")
                return None

            # Читаем shape из первых 16 байт
            rank = struct.unpack_from("<i", data, 0)[0]
            d0, d1, d2, d3 = struct.unpack_from("<iiii", data, 4)
            out_shape = [d0, d1, d2, d3][:rank]
            float_bytes = data[16:]

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