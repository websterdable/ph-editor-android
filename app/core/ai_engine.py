"""Обёртка над OnnxHelper. Модели читаем через Android AssetManager."""
import os
from kivy.logger import Logger
from kivy.utils import platform
from jnius import autoclass

OnnxHelper = autoclass("org.local.photoai.OnnxHelper")


def _extract_from_assets(asset_name, dst_path):
    """Скопировать файл из APK assets в файловую систему."""
    try:
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        am = activity.getAssets()
        stream = am.open(asset_name)
        if stream is None:
            return False
        FileOutputStream = autoclass("java.io.FileOutputStream")
        out = FileOutputStream(dst_path)
        buf = bytearray(65536)
        total = 0
        while True:
            n = stream.read(buf)
            if n <= 0:
                break
            out.write(bytes(buf[:n]))
            total += n
        out.flush()
        out.close()
        stream.close()
        Logger.info(f"AIEngine: extracted {asset_name} -> {dst_path} ({total} байт)")
        return total > 0
    except Exception as e:
        Logger.error(f"AIEngine: extract failed for {asset_name}: {e}")
        return False


def _ensure_models(model_dir, names):
    os.makedirs(model_dir, exist_ok=True)
    for name in names:
        dst = os.path.join(model_dir, f"{name}.onnx")
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            Logger.info(f"AIEngine: {name}.onnx уже на месте")
            continue
        # Пробуем два варианта пути в assets
        for asset_name in [f"assets/models/{name}.onnx",
                            f"models/{name}.onnx"]:
            if _extract_from_assets(asset_name, dst):
                break
        else:
            Logger.warning(f"AIEngine: не нашли {name}.onnx в assets")


class AIEngine:
    KNOWN_MODELS = ["yunet", "realesrgan_x4", "modnet"]

    def __init__(self, model_dir):
        self.model_dir = model_dir
        self.handles = {}
        if platform == "android":
            _ensure_models(model_dir, self.KNOWN_MODELS)
        Logger.info(f"AIEngine: папка моделей: {model_dir}")
        for name in self.KNOWN_MODELS:
            p = os.path.join(model_dir, f"{name}.onnx")
            sz = os.path.getsize(p) // 1024 if os.path.exists(p) else 0
            Logger.info(f"AIEngine: {name}.onnx — {sz} КБ")

    def has_model(self, name):
        return os.path.exists(os.path.join(self.model_dir, f"{name}.onnx"))

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
                    return None
                return bytes(hwc_out), out_shape[3], out_shape[2]
            elif len(out_shape) == 4 and out_shape[1] == 1:
                hwc_out = OnnxHelper.chw1ToHwcU8(result.data, result.shape)
                if hwc_out is None:
                    return None
                return bytes(hwc_out), out_shape[3], out_shape[2]
            return None
        except Exception as e:
            Logger.exception(f"AIEngine.run({name}): {e}")
            return None