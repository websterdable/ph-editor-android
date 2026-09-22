"""Обёртка над ONNX Runtime Java API через pyjnius."""
import numpy as np
from jnius import autoclass
from kivy.logger import Logger

# Java-классы ONNX Runtime
OrtEnvironment = autoclass('ai.onnxruntime.OrtEnvironment')
OrtSession = autoclass('ai.onnxruntime.OrtSession')
OrtSessionOptions = autoclass('ai.onnxruntime.OrtSession$SessionOptions')
OnnxTensor = autoclass('ai.onnxruntime.OnnxTensor')
ByteBuffer = autoclass('java.nio.ByteBuffer')
ByteOrder = autoclass('java.nio.ByteOrder')
HashMap = autoclass('java.util.HashMap')


class AIEngine:
    """Менеджер ONNX-сессий через Java API."""

    def __init__(self, model_dir):
        self.model_dir = model_dir
        self.env = OrtEnvironment.getEnvironment()
        self.sessions = {}
        Logger.info("AIEngine: Java ONNX Runtime инициализирован")

    def has_model(self, name):
        import os
        return os.path.exists(os.path.join(self.model_dir, f"{name}.onnx"))

    def load(self, name):
        if name in self.sessions:
            return True
        import os
        path = os.path.join(self.model_dir, f"{name}.onnx")
        if not os.path.exists(path):
            Logger.warning(f"AIEngine: модель не найдена: {path}")
            return False
        try:
            opts = OrtSessionOptions()
            opts.setIntraOpNumThreads(2)
            opts.setInterOpNumThreads(1)
            # Опционально: opts.addNnapi() или opts.addXnnpack()
            self.sessions[name] = self.env.createSession(path, opts)
            Logger.info(f"AIEngine: загружена модель {name}")
            return True
        except Exception as e:
            Logger.error(f"AIEngine: ошибка загрузки {name}: {e}")
            return False

    def run(self, name, inputs):
        """inputs: dict {input_name: np.ndarray}. Возвращает dict {output_name: np.ndarray}."""
        if not self.load(name):
            return None
        session = self.sessions[name]
        jmap = HashMap()
        for in_name, arr in inputs.items():
            arr = np.ascontiguousarray(arr)
            if arr.dtype == np.float32:
                flat = arr.ravel()
                bb = ByteBuffer.wrap(flat.tobytes())
                bb.order(ByteOrder.nativeOrder())
                fb = bb.asFloatBuffer()
                tensor = OnnxTensor.createTensor(self.env, fb, list(arr.shape))
            elif arr.dtype == np.int64:
                flat = arr.ravel().astype(np.int64)
                bb = ByteBuffer.wrap(flat.tobytes())
                bb.order(ByteOrder.nativeOrder())
                lb = bb.asLongBuffer()
                tensor = OnnxTensor.createTensor(self.env, lb, list(arr.shape))
            else:
                raise TypeError(f"Unsupported dtype: {arr.dtype}")
            jmap.put(in_name, tensor)

        try:
            results = session.run(jmap)
        except Exception as e:
            Logger.error(f"AIEngine.run({name}): {e}")
            return None

        # Определяем выходные имена из сессии
        out_info = session.getOutputInfo()
        out_dict = {}
        for out_name in out_info.keySet().toArray():
            out_name = str(out_name)
            tensor_obj = results.get(out_name).get()
            # Читаем float-массив
            buf = tensor_obj.getByteBuffer()
            shape = list(tensor_obj.getInfo().getShape())
            arr = np.frombuffer(buf.array(), dtype=np.float32)
            # Учитываем возможный паддинг
            import math
            total = 1
            for s in shape:
                total *= s
            arr = arr[:total].reshape(shape)
            out_dict[out_name] = arr
        return out_dict

    def unload(self, name):
        self.sessions.pop(name, None)