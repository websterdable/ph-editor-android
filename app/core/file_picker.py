"""Нативный Android-выбор фото из галереи.

На Android использует Intent.ACTION_PICK + копирование content:// URI
во временный файл. На десктопе откатывается на plyer.
"""
import os
import shutil
import tempfile
from kivy.logger import Logger
from kivy.utils import platform


def _pick_android(callback):
    """Открывает галерею Android через Intent.ACTION_PICK."""
    try:
        from jnius import autoclass, cast  # type: ignore
        from android import activity  # type: ignore
        from android.runnable import run_on_ui_thread  # type: ignore

        Intent = autoclass("android.content.Intent")
        MediaStore = autoclass("android.provider.MediaStore$Images$Media")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Environment = autoclass("android.os.Environment")

        REQUEST_CODE = 0x5A11

        def _on_activity_result(request_code, result_code, intent):
            if request_code != REQUEST_CODE:
                return
            try:
                from jnius import autoclass
                Activity = autoclass("android.app.Activity")
                if result_code != Activity.RESULT_OK or intent is None:
                    callback(None)
                    return
                uri = intent.getData()
                if uri is None:
                    callback(None)
                    return

                activity_obj = PythonActivity.mActivity
                content_resolver = activity_obj.getContentResolver()

                # Определяем расширение
                mime = content_resolver.getType(uri) or "image/jpeg"
                ext = "." + mime.split("/")[-1].replace("jpeg", "jpg")

                # Копируем во временный файл в приватной папке приложения
                cache_dir = activity_obj.getCacheDir().getAbsolutePath()
                tmp_path = os.path.join(cache_dir, f"picked_{os.getpid()}{ext}")

                input_stream = content_resolver.openInputStream(uri)
                output_stream = open(tmp_path, "wb")
                buf = bytearray(65536)
                while True:
                    n = input_stream.read(buf)
                    if n <= 0:
                        break
                    output_stream.write(buf[:n])
                output_stream.close()
                input_stream.close()

                Logger.info(f"file_picker: picked -> {tmp_path}")
                callback(tmp_path)
            except Exception as e:
                Logger.error(f"file_picker: error in result handler -> {e}")
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
                PythonActivity.mActivity.startActivityForResult(intent, REQUEST_CODE)
            except Exception as e:
                Logger.error(f"file_picker: launch failed -> {e}")
                callback(None)

        _launch()
    except Exception as e:
        Logger.error(f"file_picker: Android picker недоступен -> {e}")
        callback(None)


def _pick_desktop(callback):
    """Откат для десктопа (для локальной отладки)."""
    try:
        from plyer import filechooser  # type: ignore
        filechooser.open_file(
            on_selection=lambda sel: callback(sel[0] if sel else None),
            filters=["*.png", "*.jpg", "*.jpeg"],
        )
    except Exception as e:
        Logger.warning(f"file_picker desktop: {e}")
        callback(None)


def pick_image(callback):
    """Универсальная точка входа. callback(path_or_None)."""
    if platform == "android":
        _pick_android(callback)
    else:
        _pick_desktop(callback)