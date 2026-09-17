"""Управление ONNX-сессиями: ленивая загрузка, кэш, потоки."""
import os
import threading
from pathlib import Path
from kivy.logger import Logger

_ORT = None
_ORT_AVAILABLE = False
_PROBED = False


def probe_ort():
    global _ORT, _ORT_AVAILABLE, _PROBED
    if _PROBED:
        return _ORT_AVAILABLE
    _PROBED = True
    try:
        import onnxruntime as ort
        _ORT = ort
        _ORT_AVAILABLE = True
        Logger.info("AIEngine: onnxruntime доступен")
    except Exception as e:
        Logger.warning(f"AIEngine: onnxruntime НЕ доступен -> {e}")
        _ORT_AVAILABLE = False
    return _ORT_AVAILABLE


class AIEngine:
    """Потокобезопасный менеджер ONNX-сессий."""

    def __init__(self, model_dir: str):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._sessions = {}
        self._lock = threading.Lock()
        self.available = probe_ort()

    def is_ready(self) -> bool:
        return self.available

    def has_model(self, name: str) -> bool:
        return (self.model_dir / f"{name}.onnx").exists()

    def load(self, name: str) -> bool:
        if not self.available:
            return False
        with self._lock:
            if name in self._sessions:
                return True
            path = self.model_dir / f"{name}.onnx"
            if not path.exists():
                Logger.warning(f"AIEngine: нет файла {path}")
                return False
            try:
                opts = _ORT.SessionOptions()
                opts.intra_op_num_threads = 2
                opts.inter_op_num_threads = 1
                opts.graph_optimization_level = _ORT.GraphOptimizationLevel.ORT_ENABLE_ALL
                self._sessions[name] = _ORT.InferenceSession(
                    str(path),
                    sess_options=opts,
                    providers=["CPUExecutionProvider"],
                )
                Logger.info(f"AIEngine: загружена модель {name}")
                return True
            except Exception as e:
                Logger.error(f"AIEngine: не удалось загрузить {name}: {e}")
                return False

    def run(self, name: str, inputs: dict):
        """Синхронный инференс. inputs: {input_name: np.ndarray}."""
        if not self.load(name):
            return None
        sess = self._sessions[name]
        try:
            return sess.run(None, inputs)
        except Exception as e:
            Logger.error(f"AIEngine.run({name}): {e}")
            return None

    def input_spec(self, name: str):
        """Вернуть (name, shape) первого входа."""
        if not self.load(name):
            return None
        sess = self._sessions[name]
        inp = sess.get_inputs()[0]
        return inp.name, inp.shape

    def unload(self, name: str):
        with self._lock:
            self._sessions.pop(name, None)

    def unload_all(self):
        with self._lock:
            self._sessions.clear()

    def list_models(self):
        return sorted(p.stem for p in self.model_dir.glob("*.onnx"))