"""Нативный Android-выбор фото из галереи с поддержкой любых форматов.

Работает так:
1. Открывает системную галерею через Intent.ACTION_PICK.
2. Получает content:// URI.
3. Если формат HEIC/HEIF — декодирует через Android BitmapFactory
   и пересохраняет в JPEG.
4. Иначе — копирует содержимое во временный файл.
5. Возвращает путь к локальному файлу в кэш-папке приложения.

На десктопе (для отладки) использует plyer.
"""
import os
from kivy.logger import Logger
from kivy.utils import platform


REQUEST_CODE_PICK_IMAGE = 0x5A11


def _pick_android(callback):
    """Открывает галерею Android через Intent.ACTION_PICK."""
    try:
        from jnius import autoclass  # type: ignore
        from android import activity  # type: ignore

        Intent = autoclass("android.content.Intent")
        MediaStore = autoclass("android.provider.MediaStore$Images$Media")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Activity = autoclass("android.app.Activity")
        BitmapFactory = autoclass("android.graphics.BitmapFactory")
        BitmapCompressFormat = autoclass(
            "android.graphics.Bitmap$CompressFormat"
        )
        FileOutputStream = autoclass("java.io.FileOutputStream")

        def _on_activity_result(request_code, result_code, intent):
            if request_code != REQUEST_CODE_PICK_IMAGE:
                return
            try:
                if result_code != Activity.RESULT_OK or intent is None:
                    Logger.info("file_picker: пользователь отменил выбор")
                    callback(None)
                    return

                uri = intent.getData()
                if uri is None:
                    Logger.warning("file_picker: URI пустой")
                    callback(None)
                    return

                activity_obj = PythonActivity.mActivity
                resolver = activity_obj.getContentResolver()
                cache_dir = activity_obj.getCacheDir().getAbsolutePath()

                mime = resolver.getType(uri) or "image/jpeg"
                Logger.info(f"file_picker: выбран MIME={mime}")

                ext = "." + mime.split("/")[-1].lower()
                ext = ext.replace(".jpeg", ".jpg")
                is_heic = ext in (".heic", ".heif") or "heic" in mime.lower()

                if is_heic:
                    # HEIC/HEIF: декодируем через Android и сохраняем как JPEG
                    Logger.info("file_picker: HEIC -> декодирую через BitmapFactory")
                    in_stream = resolver.openInputStream(uri)
                    bitmap = BitmapFactory.decodeStream(in_stream)
                    in_stream.close()

                    if bitmap is None:
                        Logger.error("file_picker: BitmapFactory вернул None")
                        callback(None)
                        return

                    jpg_path = os.path.join(
                        cache_dir, f"picked_{os.getpid()}.jpg"
                    )
                    out_stream = FileOutputStream(jpg_path)
                    bitmap.compress(BitmapCompressFormat.JPEG, 95, out_stream)
                    out_stream.close()
                    bitmap.recycle()

                    size = os.path.getsize(jpg_path)
                    Logger.info(
                        f"file_picker: HEIC сконвертирован, {size} байт -> {jpg_path}"
                    )
                    callback(jpg_path)
                    return

                # Обычный формат: копируем поток в файл
                tmp_path = os.path.join(
                    cache_dir, f"picked_{os.getpid()}{ext}"
                )
                in_stream = resolver.openInputStream(uri)
                out_stream = FileOutputStream(tmp_path)

                buf = bytearray(65536)
                total = 0
                while True:
                    n = in_stream.read(buf)
                    if n <= 0:
                        break
                    out_stream.write(buf, 0, n)
                    total += n
                out_stream.close()
                in_stream.close()

                if total == 0:
                    Logger.error("file_picker: скопировано 0 байт")
                    callback(None)
                    return

                Logger.info(
                    f"file_picker: скопировано {total} байт -> {tmp_path}"
                )
                callback(tmp_path)

            except Exception as e:
                Logger.error(f"file_picker: ошибка обработки результата -> {e}")
                callback(None)
            finally:
                try:
                    activity.unbind(on_activity_result=_on_activity_result)
                except Exception:
                    pass

        def _launch():
            try:
                activity.bind(on_activity_result=_on_activity_result)
                intent = Intent(Intent.ACTION_PICK)
                intent.setDataAndType(
                    MediaStore.EXTERNAL_CONTENT_URI, "image/*"
                )
                PythonActivity.mActivity.startActivityForResult(
                    intent, REQUEST_CODE_PICK_IMAGE
                )
                Logger.info("file_picker: галерея открыта")
            except Exception as e:
                Logger.error(f"file_picker: не удалось запустить галерею -> {e}")
                callback(None)

        _launch()

    except Exception as e:
        Logger.error(f"file_picker: Android picker недоступен -> {e}")
        callback(None)


def _pick_desktop(callback):
    """На десктопе — просто заглушка (для отладки на Android не нужна)."""
    Logger.warning("file_picker: десктоп не поддерживается, вернитесь на Android")
    callback(None)


def pick_image(callback):
    """Универсальная точка входа.

    Args:
        callback: функция, принимающая либо путь к файлу (str),
                  либо None при отмене/ошибке.
    """
    if platform == "android":
        _pick_android(callback)
    else:
        _pick_desktop(callback)