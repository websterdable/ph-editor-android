"""Модуль 2: базовые инструменты (форматы, сжатие)."""
import os
import time
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image as KivyImage
from kivy.graphics import Color, Rectangle

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


class ToolsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_dir = _app_dir()
        self.storage = LocalStorage(self.base_dir)
        self.current = None  # (bytes, w, h)
        self._build()
        theme.bind(bg=self._upd_bg)

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(8))

        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        top.add_widget(PillButton(text="←", size_hint_x=None, width=dp(48),
                                   variant="secondary",
                                   on_release=lambda *_: self._back()))
        top.add_widget(Label(text="Инструменты", font_size=dp(15),
                              color=theme.text))
        root.add_widget(top)

        self.preview = KivyImage(size_hint=(1, 1), allow_stretch=True,
                                  keep_ratio=True)
        root.add_widget(self.preview)

        self.info = Label(text="Файл не выбран", size_hint_y=None,
                          height=dp(40), color=theme.text_muted,
                          font_size=dp(12))
        root.add_widget(self.info)

        root.add_widget(PillButton(text="Открыть фото",
                                    on_release=lambda *_: self._open(),
                                    size_hint_y=None, height=dp(48)))

        root.add_widget(PillButton(text="💾 Сохранить копию как PNG",
                                    on_release=lambda *_: self._save_png(),
                                    variant="primary",
                                    size_hint_y=None, height=dp(48)))

        root.add_widget(PillButton(text="📤 Экспорт в галерею",
                                    on_release=lambda *_: self._export(),
                                    variant="secondary",
                                    size_hint_y=None, height=dp(48)))

        hint = Label(
            text="Конвертация в JPEG/WebP будет добавлена позже.\n"
                 "Сейчас доступен экспорт в PNG.",
            font_size=dp(11), color=theme.text_muted)
        root.add_widget(hint)

        self.add_widget(root)

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
            loaded = iu.load_image(path)
            if loaded is None:
                self.info.text = "Не удалось загрузить"
                return
            self.current = loaded
            b, w, h = loaded
            self.preview.texture = iu.to_texture(b, w, h)
            size_kb = os.path.getsize(path) // 1024
            self.info.text = f"{w}×{h} · {size_kb} КБ · {os.path.basename(path)}"
        pick_image(_done)

    def _save_png(self):
        if self.current is None:
            self.info.text = "Сначала откройте фото"
            return
        b, w, h = self.current
        ts = time.strftime("%Y%m%d_%H%M%S")
        out = os.path.join(self.storage.output_dir, f"copy_{ts}.png")
        if iu.save_image(b, w, h, out):
            size_kb = os.path.getsize(out) // 1024
            self.info.text = f"Сохранено: {os.path.basename(out)} · {size_kb} КБ"
        else:
            self.info.text = "Ошибка сохранения"

    def _export(self):
        if self.current is None:
            self.info.text = "Сначала откройте фото"
            return
        b, w, h = self.current
        ts = time.strftime("%Y%m%d_%H%M%S")
        tmp = os.path.join(self.storage.output_dir, f"export_{ts}.png")
        if not iu.save_image(b, w, h, tmp):
            self.info.text = "Ошибка сохранения"
            return
        if save_to_gallery(tmp, mime="image/png"):
            self.info.text = "✅ Сохранено в галерею (Pictures/PhotoAI)"
        else:
            self.info.text = "Не удалось экспортировать"

    def _back(self):
        self.manager.current = "home"