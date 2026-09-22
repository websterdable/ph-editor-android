"""Модуль 3: ИИ-редактор."""
import os
import threading
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image as KivyImage
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle

from app.core import image_utils as iu
from app.core.file_picker import pick_image
from app.core.storage import LocalStorage
from app.core.ai_engine import AIEngine
from app.core import ai_operations as aio
from app.ui.theme import theme
from app.ui.widgets import PillButton, IconButton, ICON_BACK


def _app_dir():
    try:
        from android.storage import app_storage_path
        return app_storage_path()
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".photoai")


class AIScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.storage = LocalStorage(_app_dir())
        self.engine = AIEngine(os.path.join(_app_dir(), "models"))
        self.img = None  # (rgb_bytes, w, h)
        self._busy = False
        self._build()
        theme.bind(bg=self._upd_bg)

    def _build(self):
        outer = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(4))
        top.add_widget(IconButton(icon=ICON_BACK, variant="ghost",
                                   size_hint=(None, None), size=(dp(44), dp(44)),
                                   on_release=lambda *_: self._back()))
        top.add_widget(Label(text="ИИ-Редактор", font_name=theme.font_medium,
                              font_size=dp(16), color=theme.text))
        outer.add_widget(top)

        page_scroll = ScrollView(bar_width=dp(4))
        page = BoxLayout(orientation="vertical", size_hint_y=None,
                         spacing=dp(8), padding=(dp(4), dp(4)))
        page.bind(minimum_height=page.setter("height"))

        self.preview = KivyImage(size_hint_y=None, height=dp(260),
                                  fit_mode="contain")
        page.add_widget(self.preview)

        self.status = Label(text="Откройте фото", size_hint_y=None, height=dp(30),
                            color=theme.text_muted, font_name=theme.font_regular,
                            font_size=dp(12))
        page.add_widget(self.status)

        page.add_widget(PillButton(text="Открыть фото",
                                    on_release=lambda *_: self._open(),
                                    variant="primary", size_hint_y=None, height=dp(48)))

        page.add_widget(self._section("Апскейл (Real-ESRGAN)"))
        page.add_widget(PillButton(text="Увеличить x4",
                                    on_release=lambda *_: self._run("upscale"),
                                    variant="secondary", size_hint_y=None, height=dp(48)))

        page.add_widget(self._section("Лица (YuNet + GFPGAN)"))
        page.add_widget(PillButton(text="Найти лица",
                                    on_release=lambda *_: self._run("detect"),
                                    variant="secondary", size_hint_y=None, height=dp(48)))

        page.add_widget(self._section("Фон (MODNet)"))
        page.add_widget(PillButton(text="Удалить фон",
                                    on_release=lambda *_: self._run("bg"),
                                    variant="secondary", size_hint_y=None, height=dp(48)))

        page.add_widget(BoxLayout(size_hint_y=None, height=dp(20)))
        page_scroll.add_widget(page)
        outer.add_widget(page_scroll)
        self.add_widget(outer)

    def _section(self, text):
        lbl = Label(text=text, size_hint_y=None, height=dp(28),
                    color=theme.text, font_name=theme.font_medium,
                    font_size=dp(13), halign="left", valign="middle")
        lbl.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        return lbl

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
                self.status.text = "Не удалось загрузить"
                return
            self.img = loaded
            b, w, h = loaded
            self.preview.texture = iu.to_texture(b, w, h)
            self.status.text = f"Открыто: {w}x{h}"
        pick_image(_done)

    def _run(self, op):
        if self.img is None:
            self.status.text = "Сначала откройте фото"
            return
        if self._busy:
            return
        self._busy = True
        self.status.text = f"Обработка: {op}…"
        threading.Thread(target=self._worker, args=(op,), daemon=True).start()

    def _worker(self, op):
        try:
            import numpy as np
            b, w, h = self.img
            # bytes -> numpy RGB
            arr = np.frombuffer(b, dtype=np.uint8).reshape(h, w, 3)
            result = None
            if op == "upscale":
                result = aio.upscale(self.engine, arr)
            elif op == "detect":
                faces = aio.detect_faces(self.engine, arr)
                Clock.schedule_once(lambda dt: self._on_faces(faces), 0)
                return
            elif op == "bg":
                rgba = aio.remove_background(self.engine, arr)
                if rgba is not None:
                    Clock.schedule_once(lambda dt: self._on_rgba(rgba), 0)
                return
            if result is not None:
                Clock.schedule_once(lambda dt: self._on_result(result), 0)
            else:
                Clock.schedule_once(lambda dt: setattr(self.status, "text", "Модель не дала результата"), 0)
        except Exception as e:
            Logger.exception(f"AI worker: {e}")
            Clock.schedule_once(lambda dt: setattr(self.status, "text", f"Ошибка: {e}"), 0)
        finally:
            self._busy = False

    def _on_faces(self, faces):
        self.status.text = f"Найдено лиц: {len(faces)}"

    def _on_rgba(self, rgba):
        # Показываем RGB-часть, сохраняем RGBA
        rgb = rgba[:, :, :3]
        self.preview.texture = iu.to_texture(rgb.tobytes(), rgb.shape[1], rgb.shape[0])
        self.status.text = "Фон удалён"

    def _on_result(self, arr):
        self.img = (arr.tobytes(), arr.shape[1], arr.shape[0])
        self.preview.texture = iu.to_texture(arr.tobytes(), arr.shape[1], arr.shape[0])
        self.status.text = "Готово"

    def _back(self):
        self.manager.current = "home"