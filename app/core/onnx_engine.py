"""Обёртка над ONNX Runtime. Ленивая: если рантайм или модель отсутствуют,
приложение продолжает работать без них.
"""
from pathlib import Path
from kivy.logger import Logger

_ORT = None
_ORT_AVAILABLE = False
_PROBED = False


def _probe_ort():
    global _ORT, _ORT_AVAILABLE, _PROBED
    if _PROBED:
        return _ORT_AVAILABLE
    _PROBED = True
    try:
        import onnxruntime as ort  # type: ignore
        _ORT = ort
        _ORT_AVAILABLE = True
        Logger.info("OnnxEngine: onnxruntime доступен")
    except Exception as e:
        _ORT = None
        _ORT_AVAILABLE = False
        Logger.warning(f"OnnxEngine: onnxruntime НЕ доступен -> {e}")
    return _ORT_AVAILABLE


class OnnxEngine:
    def __init__(self, model_dir):
        self.model_dir = Path(model_dir)
        self.sessions = {}
        self.available = _probe_ort()

    def is_ready(self):
        return self.available

    def has_model(self, name):
        return (self.model_dir / f"{name}.onnx").exists()

    def load(self, name):
        if not self.available:
            return False
        if name in self.sessions:
            return True
        path = self.model_dir / f"{name}.onnx"
        if not path.exists():
            Logger.warning(f"OnnxEngine: файл модели не найден: {path}")
            return False
        try:
            self.sessions[name] = _ORT.InferenceSession(
                str(path), providers=["CPUExecutionProvider"]
            )
            return True
        except Exception as e:
            Logger.error(f"OnnxEngine: не удалось загрузить {name}: {e}")
            return False

    def run(self, name, image_nhwc):
        """Инференс. image_nhwc: numpy (H, W, 3) uint8. -> (H', W', 3) uint8 или None."""
        if not self.load(name):
            return None
        import numpy as np
        sess = self.sessions[name]
        inp = sess.get_inputs()[0]
        x = image_nhwc.astype(np.float32) / 255.0
        x = np.transpose(x, (2, 0, 1))[None, ...]
        try:
            outputs = sess.run(None, {inp.name: x})
        except Exception as e:
            Logger.error(f"OnnxEngine.run({name}): {e}")
            return None
        out = outputs[0][0]
        out = np.transpose(out, (1, 2, 0))
        return np.clip(out * 255.0, 0, 255).astype(np.uint8)