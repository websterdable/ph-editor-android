"""Обёртка над Java-помощником OnnxHelper. Без numpy."""
import os
from kivy.logger import Logger
from jnius import autoclass

OnnxHelper = autoclass("org.local.photoai.OnnxHelper")


class AIEngine:
    def __init__(self, model_dir):
        self.model_dir = model_dir
        self.handles = {}

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
        """hwc_u8: bytes, возвращает (hwc_u8_out, w_out, h_out) или None."""
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

            # CHW float32 -> HWC uint8 (в Java)
            hwc_out = OnnxHelper.chwF32ToHwcU8(result.data, result.shape)
            if hwc_out is None:
                Logger.error(f"AIEngine.run({name}): не удалось конвертировать выход")
                return None

            out_bytes = bytes(hwc_out)
            if len(out_shape) == 4:
                return out_bytes, out_shape[3], out_shape[2]  # w, h
            return None
        except Exception as e:
            Logger.exception(f"AIEngine.run({name}): {e}")
            return None

    def unload(self, name):
        self.handles.pop(name, None)