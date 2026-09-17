"""Модуль 2: инструменты (формат, размер, сжатие)."""
import os
import time
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image as KivyImage
from kivy.graphics import Color, Rectangle
from kivy.logger import Logger

from app.core import image_utils as iu
from app.core.file_picker import pick_image
from app.core.storage import LocalStorage
from app.core.exporter import save_to_gallery
from app.ui.theme import theme
from app.ui.widgets import PillButton


def _app_dir():
    try:
        from android.storage import app_storage_path  # type: ignore
        return app_storage_path()
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".photoai")


FORMATS = [("PNG", "PNG", ".png"), ("JPEG", "JPEG", ".jpg"), ("WEBP", "WEBP", ".webp")]
QUALITIES = [("100%", 100), ("95%", 95), ("80%", 80), ("60%", 60)]


class ToolsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_dir = _app_dir()
        self.storage = LocalStorage(self.base_dir)
        self.current = None
        self.target_format = "PNG"
        self.target_quality = 95
        self._build()
        theme.bind(bg=self._upd_bg)

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(8))

        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        top.add_widget(PillButton(text="←", size_hint_x=None, width=dp(48),
                                   variant="secondary",
                                   on_release=lambda *_: self._back()))
        top.add_widget(Label(text="Инструменты", font_size=dp(15), color=theme.text))
        root.add_widget(top)

        self.preview = KivyImage(size_hint=(1, 1), allow_stretch=True, keep_ratio=True)
        root.add_widget(self.preview)

        self.info = Label(text="Файл не выбран", size_hint_y=None, height=dp(40),
                          color=theme.text_muted, font_size=dp(12))
        root.add_widget(self.info)

        root.add_widget(PillButton(text="Открыть фото", on_release=lambda *_: self._open(),
                                    size_hint_y=None, height=dp(48)))

        root.add_widget(Label(text="Формат:", size_hint_y=None, height=dp(24),
                                color=theme.text, font_size=dp(13)))
        fmt_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4))
        self._fmt_btns = {}
        for name, tag, ext in FORMATS:
            b = PillButton(text=name, variant="secondary")
            b.bind(on_release=lambda inst, t=tag: self._select_format(t))
            self._fmt_btns[tag] = b
            fmt_row.add_widget(b)
        root.add_widget(fmt_row)

        root.add_widget(Label(text="Качество (для JPEG/WebP):",
                                size_hint_y=None, height=dp(24),
                                color=theme.text, font_size=dp(13)))
        q_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4))
        for name, val in QUALITIES:
            b = PillButton(text=name, variant="secondary")
            b.bind(on_release=lambda inst, v=val: self._select_quality(v))
            q_row.add_widget(b)
        root.add_widget(q_row)

        root.add_widget(PillButton(text="💾 Сохранить как новое",
                                    on_release=lambda *_: self._save_as(),
                                    size_hint_y=None, height=dp(48)))

        self.add_widget(root)
        self._select_format("PNG")

    def _upd_bg(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*theme.bg)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd_bg, size=self._upd_bg)
        if hasattr(self, "_bg"):
            self._bg.pos = self.pos
            self._bg.size = self.size

    def _open(self):
        def _done(path):
            if not path:
                return
            arr = iu.load_image(path)
            if arr is None:
                self.info.text = "Не удалось загрузить"
                return
            self.current = arr
            self.preview.texture = iu.to_texture(arr)
            h, w = arr.shape[:2]
            size_kb = os.path.getsize(path) // 1024
            self.info.text = f"{w}×{h} · {size_kb} КБ · {os.path.basename(path)}"
        pick_image(_done)

    def _select_format(self, tag):
        self.target_format = tag
        for t, b in self._fmt_btns.items():
            b.variant = "primary" if t == tag else "secondary"
            b._upd_color()

    def _select_quality(self, val):
        self.target_quality = val

    def _save_as(self):
        if self.current is None:
            self.info.text = "Сначала откройте фото"
            return
        ext = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}[self.target_format]
        ts = time.strftime("%Y%m%d_%H%M%S")
        out = os.path.join(self.storage.output_dir, f"conv_{ts}{ext}")
        try:
            from PIL import Image
            img = Image.fromarray(self.current)
            if self.target_format == "JPEG":
                # JPEG не поддерживает альфу
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                img.save(out, "JPEG", quality=self.target_quality, optimize=True)
            elif self.target_format == "WEBP":
                img.save(out, "WEBP", quality=self.target_quality)
            else:
                img.save(out, "PNG", optimize=True)

            size_kb = os.path.getsize(out) // 1024
            self.info.text = f"Сохранено: {os.path.basename(out)} · {size_kb} КБ"

            if save_to_gallery(out, mime=f"image/{self.target_format.lower()}"):
                self.info.text += " · ✅ в галерее"
        except Exception as e:
            Logger.error(f"tools save: {e}")
            self.info.text = f"Ошибка: {e}"

    def _back(self):
        self.manager.current = "home"