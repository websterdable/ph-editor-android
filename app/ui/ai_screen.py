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
from kivy.graphics import Color, Rectangle, Line

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
        self.img = None
        self._busy = False
        self._build()
        theme.bind(bg=self._upd_bg)

    def _build(self):
        outer = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(4))
        top.add_widget(IconButton(icon=ICON_BACK, variant="ghost",
                                   size_hint=(None, None), size=(dp(44), dp(44)),
                                   on_release=lambda *_: self._back()))
        top.add_widget(Label(text="ИИ-Редактор",
                              font_name=theme.font_medium,
                              font_size=dp(16), color=theme.text))
        outer.add_widget(top)

        page_scroll = ScrollView(bar_width=dp(4))
        page = BoxLayout(orientation="vertical", size_hint_y=None,
                         spacing=dp(8), padding=(dp(4), dp(4)))
        page.bind(minimum_height=page.setter("height"))

        self.preview = KivyImage(size_hint_y=None, height=dp(240),
                                  fit_mode="contain")
        page.add_widget(self.preview)

        self.status = Label(text="Откройте фото", size_hint_y=None,
                            height=dp(34), color=theme.text_muted,
                            font_name=theme.font_regular, font_size=dp(12))
        page.add_widget(self.status)

        page.add_widget(PillButton(
            text="Открыть фото", variant="primary",
            size_hint_y=None, height=dp(48),
            on_release=lambda *_: self._open()))

        page.add_widget(self._section("Апскейл (Real-ESRGAN x4)"))
        page.add_widget(PillButton(
            text="Увеличить x4", variant="secondary",
            size_hint_y=None, height=dp(48),
            on_release=lambda *_: self._run("upscale")))

        page.add_widget(self._section("Фон (MODNet)"))
        page.add_widget(PillButton(
            text="Удалить фон", variant="secondary",
            size_hint_y=None, height=dp(48),
            on_release=lambda *_: self._run("bg")))

        page.add_widget(self._section("Детекция лиц (YuNet)"))
        page.add_widget(PillButton(
            text="Найти лица", variant="secondary",
            size_hint_y=None, height=dp(48),
            on_release=lambda *_: self._run("detect")))

        page.add_widget(BoxLayout(size_hint_y=None, height=dp(24)))

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
        self.status.text = f"Обработка: {op}… (может занять 5–30 сек)"
        threading.Thread(target=self._worker, args=(op,), daemon=True).start()

    def _worker(self, op):
        try:
            b, w, h = self.img
            result = None
            if op == "upscale":
                result = aio.upscale(self.engine, b, w, h)
            elif op == "bg":
                result = aio.remove_background(self.engine, b, w, h)
            elif op == "detect":
                faces = aio.detect_faces(self.engine, b, w, h)
                Clock.schedule_once(lambda dt: self._on_faces(faces, w, h), 0)
                return

            if result is None:
                Clock.schedule_once(
                    lambda dt: setattr(self.status, "text", "Модель не дала результата"),
                    0)
            else:
                Clock.schedule_once(lambda dt: self._on_result(result), 0)
        except Exception as e:
            from kivy.logger import Logger
            Logger.exception(f"AI worker: {e}")
            Clock.schedule_once(
                lambda dt: setattr(self.status, "text", f"Ошибка: {e}"), 0)
        finally:
            self._busy = False


    def _on_faces(self, faces, w, h):
        # Очищаем старые прямоугольники
        self.preview.canvas.after.clear()
        if not faces:
            self.status.text = "Лица не найдены"
            return
        with self.preview.canvas.after:
            Color(1, 0.2, 0.4, 1)  # красный
            for (x, y, fw, fh, score) in faces:
                # Пересчёт координат: превью может быть отмасштабировано
                # Kivy Image отображает центр. Используем нормированные координаты.
                nx = x / w
                ny = y / h
                nw = fw / w
                nh = fh / h

                # Размеры виджета preview
                pv_w, pv_h = self.preview.size
                pv_x, pv_y = self.preview.pos

                # Пропорции: сохранить соотношение
                img_ratio = w / h
                pv_ratio = pv_w / pv_h
                if img_ratio > pv_ratio:
                    # картинка шире — по ширине
                    draw_w = pv_w
                    draw_h = pv_w / img_ratio
                    offset_x = 0
                    offset_y = (pv_h - draw_h) / 2
                else:
                    draw_h = pv_h
                    draw_w = pv_h * img_ratio
                    offset_x = (pv_w - draw_w) / 2
                    offset_y = 0

                rx = pv_x + offset_x + nx * draw_w
                # Kivy Y от низа, у нас Y сверху -> инверсия
                ry = pv_y + offset_y + (1 - ny - nh) * draw_h
                rw = nw * draw_w
                rh = nh * draw_h

                Line(rectangle=(rx, ry, rw, rh), width=1.5)

        self.status.text = f"Найдено лиц: {len(faces)}"

    def _on_result(self, result):
        out_bytes, ow, oh = result
        # Если длина == w*h*4 — это RGBA, показываем на белом фоне
        if len(out_bytes) == ow * oh * 4:
            # Композит на белом фоне для превью
            rgb = bytearray(ow * oh * 3)
            for i in range(ow * oh):
                a = out_bytes[i * 4 + 3] / 255.0
                rgb[i * 3]     = int(out_bytes[i * 4]     * a + 255 * (1 - a))
                rgb[i * 3 + 1] = int(out_bytes[i * 4 + 1] * a + 255 * (1 - a))
                rgb[i * 3 + 2] = int(out_bytes[i * 4 + 2] * a + 255 * (1 - a))
            rgb_bytes = bytes(rgb)
            self.img = (rgb_bytes, ow, oh)
            self.preview.texture = iu.to_texture(rgb_bytes, ow, oh)
            self.status.text = f"Готово: {ow}x{oh} (RGBA сохранён)"
            # Сохраняем RGBA-версию отдельно
            self._last_rgba = out_bytes
        else:
            self.img = (out_bytes, ow, oh)
            self.preview.texture = iu.to_texture(out_bytes, ow, oh)
            self.status.text = f"Готово: {ow}x{oh}"

    def _back(self):
        self.manager.current = "home"