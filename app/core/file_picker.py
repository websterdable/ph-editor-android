"""Нативный Android-выбор фото из галереи.

Callback всегда выполняется в главном Kivy-потоке через Clock.schedule_once,
иначе Kivy падает с "Cannot create graphics instruction outside the main Kivy thread".
"""
import os
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.utils import platform

REQUEST_CODE = 0x5A11
_callback = None


def _invoke(cb, value):
    """Вызвать callback в главном Kivy-потоке."""
    if cb is None:
        return
    Clock.schedule_once(lambda dt: cb(value), 0)


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
        ExifInterface = autoclass("android.media.ExifInterface")
        Matrix = autoclass("android.graphics.Matrix")

        if result_code != Activity.RESULT_OK or intent is None:
            Logger.info("file_picker: пользователь отменил")
            _invoke(cb, None)
            return

        uri = intent.getData()
        if uri is None:
            _invoke(cb, None)
            return

        activity = PythonActivity.mActivity
        resolver = activity.getContentResolver()
        cache_dir = activity.getCacheDir().getAbsolutePath()

        # 1. Копируем содержимое во временный файл — нужен путь для ExifInterface
        temp_in = os.path.join(cache_dir, "input_temp.jpg")
        if os.path.exists(temp_in):
            os.remove(temp_in)
        in_stream = resolver.openInputStream(uri)
        with open(temp_in, "wb") as f:
            buf = bytearray(65536)
            while True:
                n = in_stream.read(buf)
                if n <= 0:
                    break
                f.write(buf[:n])
        in_stream.close()

        # 2. Читаем ориентацию из EXIF
        orientation = ExifInterface.ORIENTATION_NORMAL
        try:
            exif = ExifInterface(temp_in)
            orientation = exif.getAttributeInt(
                ExifInterface.TAG_ORIENTATION,
                ExifInterface.ORIENTATION_NORMAL,
            )
        except Exception as e:
            Logger.warning(f"file_picker: EXIF failed -> {e}")

        # 3. Декодируем Bitmap
        bitmap = BitmapFactory.decodeFile(temp_in)
        if bitmap is None:
            Logger.error("file_picker: BitmapFactory вернул None")
            _invoke(cb, None)
            return

        # 4. Применяем поворот по EXIF
        try:
            if orientation != ExifInterface.ORIENTATION_NORMAL:
                matrix = Matrix()
                if orientation == ExifInterface.ORIENTATION_ROTATE_90:
                    matrix.postRotate(90)
                elif orientation == ExifInterface.ORIENTATION_ROTATE_180:
                    matrix.postRotate(180)
                elif orientation == ExifInterface.ORIENTATION_ROTATE_270:
                    matrix.postRotate(270)
                elif orientation == ExifInterface.ORIENTATION_FLIP_HORIZONTAL:
                    matrix.postScale(-1, 1)
                elif orientation == ExifInterface.ORIENTATION_FLIP_VERTICAL:
                    matrix.postScale(1, -1)
                elif orientation == ExifInterface.ORIENTATION_TRANSPOSE:
                    matrix.postRotate(90)
                    matrix.postScale(-1, 1)
                elif orientation == ExifInterface.ORIENTATION_TRANSVERSE:
                    matrix.postRotate(270)
                    matrix.postScale(-1, 1)

                rotated = BitmapFactory.decodeFile(temp_in)  # свежая копия
                new_bitmap = autoclass("android.graphics.Bitmap").createBitmap(
                    rotated, 0, 0,
                    rotated.getWidth(), rotated.getHeight(),
                    matrix, True,
                )
                rotated.recycle()
                bitmap.recycle()
                bitmap = new_bitmap
                Logger.info(f"file_picker: применён поворот EXIF={orientation}")
        except Exception as e:
            Logger.warning(f"file_picker: rotate failed -> {e}")

        # 5. Сохраняем как JPEG
        out_path = os.path.join(cache_dir, "picked_photo.jpg")
        if os.path.exists(out_path):
            os.remove(out_path)
        out_stream = FileOutputStream(out_path)
        bitmap.compress(BitmapCompressFormat.JPEG, 95, out_stream)
        out_stream.flush()
        out_stream.close()
        bitmap.recycle()

        # Удаляем временный
        try:
            os.remove(temp_in)
        except Exception:
            pass

        size = os.path.getsize(out_path)
        Logger.info(f"file_picker: saved {size} bytes -> {out_path}")
        if size == 0:
            _invoke(cb, None)
            return

        _invoke(cb, out_path)

    except Exception as e:
        Logger.exception(f"file_picker: ошибка: {e}")
        _invoke(cb, None)


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
        _invoke(callback, None)


def _pick_desktop(callback):
    Logger.warning("file_picker: desktop не поддерживается")
    _invoke(callback, None)


def pick_image(callback):
    if platform == "android":
        _pick_android(callback)
    else:
        _pick_desktop(callback)