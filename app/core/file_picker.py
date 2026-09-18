"""Нативный Android-выбор фото из галереи."""
import os
from kivy.logger import Logger
from kivy.utils import platform

REQUEST_CODE = 0x5A11
_callback = None


def _on_activity_result(request_code, result_code, intent):
    Logger.info(f"file_picker: on_activity_result code={request_code} result={result_code}")
    global _callback
    if request_code != REQUEST_CODE:
        return
    try:
        from jnius import autoclass
        Activity = autoclass("android.app.Activity")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")

        if result_code != Activity.RESULT_OK or intent is None:
            Logger.info("file_picker: пользователь отменил")
            if _callback:
                _callback(None)
            return

        uri = intent.getData()
        Logger.info(f"file_picker: uri = {uri}")
        if uri is None:
            if _callback:
                _callback(None)
            return

        activity = PythonActivity.mActivity
        resolver = activity.getContentResolver()
        cache_dir = activity.getCacheDir().getAbsolutePath()

        mime = resolver.getType(uri) or "image/jpeg"
        Logger.info(f"file_picker: mime = {mime}")

        ext = "." + mime.split("/")[-1].lower()
        if ext in (".jpeg",):
            ext = ".jpg"

        tmp_path = os.path.join(cache_dir, f"picked_{REQUEST_CODE}{ext}")

        in_stream = resolver.openInputStream(uri)
        out_stream = open(tmp_path, "wb")
        buf = bytearray(65536)
        total = 0
        while True:
            n = in_stream.read(buf)
            if n <= 0:
                break
            out_stream.write(buf[:n])
            total += n
        out_stream.close()
        in_stream.close()

        Logger.info(f"file_picker: скопировано {total} байт -> {tmp_path}")
        if total == 0:
            if _callback:
                _callback(None)
            return

        if _callback:
            _callback(tmp_path)
    except Exception as e:
        Logger.exception(f"file_picker: ошибка обработки результата: {e}")
        if _callback:
            _callback(None)


def _pick_android(callback):
    global _callback
    _callback = callback
    try:
        from jnius import autoclass
        from android import activity

        Intent = autoclass("android.content.Intent")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")

        # Отвяжем старый обработчик, если был
        try:
            activity.unbind(on_activity_result=_on_activity_result)
        except Exception:
            pass
        activity.bind(on_activity_result=_on_activity_result)

        intent = Intent(Intent.ACTION_GET_CONTENT)
        intent.setType("image/*")
        intent.addCategory(Intent.CATEGORY_OPENABLE)

        Logger.info("file_picker: запускаем intent")
        PythonActivity.mActivity.startActivityForResult(intent, REQUEST_CODE)
    except Exception as e:
        Logger.exception(f"file_picker: не удалось запустить: {e}")
        callback(None)


def _pick_desktop(callback):
    Logger.warning("file_picker: десктоп не поддерживается")
    callback(None)


def pick_image(callback):
    if platform == "android":
        _pick_android(callback)
    else:
        _pick_desktop(callback)