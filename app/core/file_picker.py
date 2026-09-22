"""Нативный Android-выбор фото. Callback всегда в главном Kivy-потоке."""
import os
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.utils import platform

REQUEST_CODE = 0x5A11
_callback = None
_bound = False
_in_flight = False


def _invoke(cb, value):
    if cb is None:
        return
    Clock.schedule_once(lambda dt: cb(value), 0)


def _on_activity_result(request_code, result_code, intent):
    global _callback, _in_flight
    if request_code != REQUEST_CODE:
        return
    _in_flight = False
    cb = _callback
    _callback = None  # ← сбрасываем сразу, чтобы не сработало дважды
    Logger.info(f"file_picker: result code={request_code} result={result_code}")

    try:
        from jnius import autoclass
        Activity = autoclass("android.app.Activity")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        BitmapFactory = autoclass("android.graphics.BitmapFactory")
        Bitmap = autoclass("android.graphics.Bitmap")
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

        # Уникальный temp-файл на каждый вызов — не перетираем предыдущий
        import time
        stamp = int(time.time() * 1000)
        temp_in = os.path.join(cache_dir, f"input_{stamp}.jpg")

        in_stream = resolver.openInputStream(uri)
        total = 0
        with open(temp_in, "wb") as f:
            buf = bytearray(65536)
            while True:
                n = in_stream.read(buf)
                if n <= 0:
                    break
                f.write(buf[:n])
                total += n
        in_stream.close()
        Logger.info(f"file_picker: copied {total} bytes")

        orientation = 1
        try:
            exif = ExifInterface(temp_in)
            orientation = exif.getAttributeInt(ExifInterface.TAG_ORIENTATION, 1)
            Logger.info(f"file_picker: EXIF orientation = {orientation}")
        except Exception as e:
            Logger.warning(f"file_picker: EXIF read failed -> {e}")

        bitmap = BitmapFactory.decodeFile(temp_in)
        if bitmap is None:
            Logger.error("file_picker: BitmapFactory вернул None")
            _invoke(cb, None)
            return

        Logger.info(f"file_picker: decoded {bitmap.getWidth()}x{bitmap.getHeight()}")

        rotate_deg, flip_x, flip_y = 0, False, False
        if orientation == 2: flip_x = True
        elif orientation == 3: rotate_deg = 180
        elif orientation == 4: flip_y = True
        elif orientation == 5: rotate_deg = 90; flip_x = True
        elif orientation == 6: rotate_deg = 90
        elif orientation == 7: rotate_deg = 270; flip_x = True
        elif orientation == 8: rotate_deg = 270

        if rotate_deg or flip_x or flip_y:
            try:
                matrix = Matrix()
                if rotate_deg: matrix.postRotate(rotate_deg)
                if flip_x: matrix.postScale(-1, 1)
                if flip_y: matrix.postScale(1, -1)
                new_bitmap = Bitmap.createBitmap(
                    bitmap, 0, 0,
                    bitmap.getWidth(), bitmap.getHeight(),
                    matrix, True)
                if new_bitmap is not bitmap:
                    bitmap.recycle()
                    bitmap = new_bitmap
            except Exception as e:
                Logger.warning(f"file_picker: rotation failed -> {e}")

        out_path = os.path.join(cache_dir, f"picked_{stamp}.jpg")
        out_stream = FileOutputStream(out_path)
        bitmap.compress(BitmapCompressFormat.JPEG, 95, out_stream)
        out_stream.flush()
        out_stream.close()
        bitmap.recycle()

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


def _ensure_bound():
    """Подписать activity на callback только один раз за жизнь процесса."""
    global _bound
    if _bound:
        return
    try:
        from android import activity
        activity.bind(on_activity_result=_on_activity_result)
        _bound = True
        Logger.info("file_picker: activity callback привязан")
    except Exception as e:
        Logger.exception(f"file_picker: bind failed: {e}")


def _pick_android(callback):
    global _callback, _in_flight
    if _in_flight:
        Logger.warning("file_picker: предыдущий выбор ещё в полёте, игнорируем")
        return
    _callback = callback
    _in_flight = True
    try:
        from jnius import autoclass
        Intent = autoclass("android.content.Intent")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")

        _ensure_bound()  # ← только один раз

        intent = Intent(Intent.ACTION_GET_CONTENT)
        intent.setType("image/*")
        intent.addCategory(Intent.CATEGORY_OPENABLE)

        Logger.info("file_picker: запуск intent")
        PythonActivity.mActivity.startActivityForResult(intent, REQUEST_CODE)
    except Exception as e:
        Logger.exception(f"file_picker: не удалось запустить: {e}")
        _in_flight = False
        _callback = None
        _invoke(callback, None)


def _pick_desktop(callback):
    Logger.warning("file_picker: desktop не поддерживается")
    _invoke(callback, None)


def pick_image(callback):
    if platform == "android":
        _pick_android(callback)
    else:
        _pick_desktop(callback)