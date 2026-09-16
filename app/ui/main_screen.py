"""Главный экран: выбор фото, кнопки, превью, история."""
import os
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image as KivyImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle
from kivy.logger import Logger
from kivy.properties import StringProperty

from app.core import image_utils as iu
from app.core.storage import LocalStorage
from app.core.onnx_engine import OnnxEngine
from app.core.file_picker import pick_image


def _app_dir():
    try:
        from android.storage import app_storage_path  # type: ignore
        return app_storage_path()
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".photoai")


class MainScreen(BoxLayout):
    status = StringProperty("Готово")

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=dp(8), spacing=dp(8), **kwargs)
        self.base_dir = _app_dir()
        self.storage = LocalStorage(self.base_dir)
        self.engine = OnnxEngine(os.path.join(self.base_dir, "models"))
        self.current_image = None
        self.current_hash = None
        self.current_path = None

        with self.canvas.before:
            Color(0.08, 0.08, 0.10, 1)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        self._build_ui()
        self._update_status()

    def _update_bg(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _build_ui(self):
        self.add_widget(Label(
            text="[b]PhotoAI[/b]", markup=True, size_hint=(1, 0.08), font_size=dp(22),
        ))

        self.status_label = Label(
            text=self.status, size_hint=(1, 0.06), font_size=dp(12),
            color=(0.7, 0.7, 0.7, 1),
        )
        self.add_widget(self.status_label)
        self.bind(status=lambda *_: setattr(self.status_label, "text", self.status))

        self.preview = KivyImage(size_hint=(1, 1))
        self.add_widget(self.preview)

        row1 = BoxLayout(size_hint=(1, 0.09), spacing=dp(6))
        row1.add_widget(Button(text="Открыть фото", on_press=self.on_open))
        row1.add_widget(Button(text="Сохранить", on_press=self.on_save))
        self.add_widget(row1)

        row2 = BoxLayout(size_hint=(1, 0.09), spacing=dp(6))
        row2.add_widget(Button(text="Улучшить", on_press=self.on_enhance))
        row2.add_widget(Button(text="Апскейл", on_press=self.on_upscale))
        row2.add_widget(Button(text="Состарить", on_press=self.on_age))
        self.add_widget(row2)

        row3 = BoxLayout(size_hint=(1, 0.07), spacing=dp(6))
        row3.add_widget(Button(text="История", on_press=self.on_history))
        self.add_widget(row3)

    def _update_status(self):
        if self.engine.is_ready():
            models = [n for n in ("realesrgan_x4", "gfpgan", "ddcolor", "sam_age")
                      if self.engine.has_model(n)]
            self.status = f"ONNX OK. Моделей: {len(models)}"
        else:
            self.status = "ONNX недоступен — доступны базовые функции"

    def _set_image(self, arr, source_path=None):
        self.current_image = arr
        self.current_path = source_path
        if arr is not None:
            self.current_hash = self.storage.hash_bytes(arr.tobytes())
            self.preview.texture = iu.to_texture(arr)
            self.preview.canvas.ask_update()

    def _apply_result(self, op_name, result_arr):
        if result_arr is None:
            self.status = f"{op_name}: не удалось"
            return
        self._set_image(result_arr, source_path=None)
        out_path = self.storage.save_result(
            op_name, self.current_hash or "unknown", result_arr, iu.save_image
        )
        self.status = (
            f"{op_name}: сохранено как {out_path.name}" if out_path
            else f"{op_name}: ошибка сохранения"
        )

    def on_open(self, *_):
        def _done(path):
            if not path:
                self.status = "Файл не выбран"
                return
            arr = iu.load_image(path)
            if arr is None:
                self.status = "Не удалось открыть файл"
                return
            arr = iu.resize_max_side(arr, 2048)
            self._set_image(arr, source_path=path)
            self.status = f"Открыто: {os.path.basename(path)} ({arr.shape[1]}x{arr.shape[0]})"
        pick_image(_done)

    def on_save(self, *_):
        if self.current_image is None:
            self.status = "Нет изображения"
            return
        out_path = self.storage.save_result(
            "manual", self.current_hash or "unknown", self.current_image, iu.save_image
        )
        self.status = f"Сохранено: {out_path.name}" if out_path else "Ошибка сохранения"

    def on_enhance(self, *_):
        if self.current_image is None:
            self.status = "Сначала откройте фото"
            return
        result = iu.auto_enhance(self.current_image)
        self._apply_result("enhance", result)

    def on_upscale(self, *_):
        if self.current_image is None:
            self.status = "Сначала откройте фото"
            return
        if not self.engine.is_ready() or not self.engine.has_model("realesrgan_x4"):
            self.status = "Модель апскейла пока недоступна"
            return
        result = self.engine.run("realesrgan_x4", self.current_image)
        self._apply_result("upscale", result)

    def on_age(self, *_):
        if self.current_image is None:
            self.status = "Сначала откройте фото"
            return
        if not self.engine.is_ready() or not self.engine.has_model("sam_age"):
            self.status = "Модель состаривания пока недоступна"
            return
        result = self.engine.run("sam_age", self.current_image)
        self._apply_result("age", result)

    def on_history(self, *_):
        rows = self.storage.get_history(50)
        if not rows:
            content = Label(text="История пуста")
        else:
            text = "\n".join(
                f"[{op}] {created_at} → {os.path.basename(path)}"
                for op, path, created_at in rows
            )
            content = Label(text=text, size_hint_y=None)
            content.bind(
                texture_size=lambda *_: setattr(content, "height", content.texture_size[1])
            )
            sv = ScrollView()
            sv.add_widget(content)
            content = sv
        Popup(title="История", content=content, size_hint=(0.9, 0.8)).open()