"""Сохранение в общедоступную галерею (Pictures/PhotoAI) через MediaStore."""
import os
from kivy.logger import Logger
from kivy.utils import platform


def save_to_gallery(local_path, mime="image/png"):
    """Скопировать файл в публичную галерею. True при успехе."""
    if platform != "android":
        Logger.info("exporter: не Android, пропускаем")
        return False
    try:
        from jnius import autoclass  # type: ignore
        MediaStore = autoclass("android.provider.MediaStore$Images$Media")
        ContentValues = autoclass("android.content.ContentValues")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        FileInputStream = autoclass("java.io.FileInputStream")
        BuildVersion = autoclass("android.os.Build$VERSION")

        activity = PythonActivity.mActivity
        resolver = activity.getContentResolver()
        filename = os.path.basename(local_path)

        values = ContentValues()
        values.put(MediaStore.DISPLAY_NAME, filename)
        values.put(MediaStore.MIME_TYPE, mime)

        if BuildVersion.SDK_INT >= 29:
            values.put(MediaStore.RELATIVE_PATH, "Pictures/PhotoAI")
            values.put(MediaStore.IS_PENDING, 1)
            collection = MediaStore.EXTERNAL_CONTENT_URI
        else:
            # Android 9 и ниже — кладём напрямую
            from jnius import autoclass as _a
            Environment = _a("android.os.Environment")
            File = _a("java.io.File")
            dcim = Environment.getExternalStoragePublicDirectory(
                Environment.DIRECTORY_PICTURES
            )
            target_dir = File(dcim, "PhotoAI")
            target_dir.mkdirs()
            target = File(target_dir, filename)
            values.put(MediaStore.DATA, target.getAbsolutePath())
            collection = MediaStore.EXTERNAL_CONTENT_URI

        uri = resolver.insert(collection, values)
        if uri is None:
            Logger.error("exporter: resolver.insert вернул None")
            return False

        out = resolver.openOutputStream(uri)
        inp = FileInputStream(local_path)
        buf = bytearray(65536)
        while True:
            n = inp.read(buf)
            if n <= 0:
                break
            out.write(buf, 0, n)
        out.flush()
        out.close()
        inp.close()

        if BuildVersion.SDK_INT >= 29:
            values.clear()
            values.put(MediaStore.IS_PENDING, 0)
            resolver.update(uri, values, None, None)

        Logger.info(f"exporter: сохранено в галерею: {filename}")
        return True
    except Exception as e:
        Logger.error(f"exporter: ошибка -> {e}")
        return False