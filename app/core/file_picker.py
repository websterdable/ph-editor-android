"""Нативный Android-выбор фото из галереи.

Декодирует любое изображение через Android BitmapFactory и сохраняет
как JPEG — это работает с HEIC, PNG, WebP и любыми странными форматами.
"""
import os
from kivy.logger import Logger
from kivy.utils import platform

REQUEST_CODE = 0x5A11
_callback = None


def _on_activity_result(request_code, result_code, intent):
    global _callback
    Logger.info(f"file_picker: result code={request_code} result={result_code}")
    if request_code != REQUEST_CODE:
        return
    cb = _callback
    try:
        from jnius import autoclass
        Activity = autoclass("android.app.Activity")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        BitmapFactory = autoclass("android.graphics.BitmapFactory")
        BitmapCompressFormat = autoclass("android.graphics.Bitmap$CompressFormat")
        FileOutputStream = autoclass("java.io.FileOutputStream")

        if result_code != Activity.RESULT_OK or intent is None:
            Logger.info("file_picker: пользователь отменил")
            if cb:
                cb(None)
            return

        uri = intent.getData()
        Logger.info(f"file_picker: uri = {uri}")
        if uri is None:
            if cb:
                cb(None)
            return

        activity = PythonActivity.mActivity
        resolver = activity.getContentResolver()
        cache_dir = activity.getCacheDir().getAbsolutePath()

        # Открываем поток и декодируем через BitmapFactory
        in_stream = resolver.openInputStream(uri)
        bitmap = BitmapFactory.decodeStream(in_stream)
        in_stream.close()

        if bitmap is None:
            Logger.error("file_picker: BitmapFactory вернул None")
            if cb:
                cb(None)
            return

        bmp_w = bitmap.getWidth()
        bmp_h = bitmap.getHeight()
        Logger.info(f"file_picker: decoded {bmp_w}x{bmp_h}")

        # Сохраняем как JPEG
        out_path = os.path.join(cache_dir, "picked_photo.jpg")
        # Удаляем старый файл, если есть
        if os.path.exists(out_path):
            os.remove(out_path)

        out_stream = FileOutputStream(out_path)
        bitmap.compress(BitmapCompressFormat.JPEG, 95, out_stream)
        out_stream.flush()
        out_stream.close()
        bitmap.recycle()

        size = os.path.getsize(out_path)
        Logger.info(f"file_picker: saved {size} bytes -> {out_path}")

        if size == 0:
            Logger.error("file_picker: сохранено 0 байт")
            if cb:
                cb(None)
            return

        if cb:
            cb(out_path)

    except Exception as e:
        Logger.exception(f"file_picker: ошибка: {e}")
        if cb:
            cb(None)


def _pick_android(callback):
    global _callback
    _callback = callback
    try:
        from jnius import autoclass
        from android import activity

        Intent = autoclass("android.content.Intent")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")

        try:
            activity.unbind(on_activity_result=_on_activity_result)
        except Exception:
            pass
        activity.bind(on_activity_result=_on_activity_result)

        intent = Intent(Intent.ACTION_GET_CONTENT)
        intent.setType("image/*")
        intent.addCategory(Intent.CATEGORY_OPENABLE)

        Logger.info("file_picker: запуск intent")
        PythonActivity.mActivity.startActivityForResult(intent, REQUEST_CODE)
    except Exception as e:
        Logger.exception(f"file_picker: не удалось запустить: {e}")
        callback(None)


def _pick_desktop(callback):
    Logger.warning("file_picker: desktop не поддерживается")
    callback(None)


def pick_image(callback):
    if platform == "android":
        _pick_android(callback)
    else:
        _pick_desktop(callback)