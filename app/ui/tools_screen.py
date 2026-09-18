"""Модуль 2: инструменты — формат, размер, качество, EXIF."""
import os
import time
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image as KivyImage
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle

from app.core import image_utils as iu
from app.core.file_picker import pick_image
from app.core.storage import LocalStorage
from app.core.exporter import save_to_gallery
from app.ui.theme import theme
from app.ui.widgets import (
    PillButton, IconButton, SliderRow,
    ICON_BACK, ICON_SAVE, ICON_UPLOAD,
)


def _app_dir():
    try:
        from android.storage import app_storage_path  # type: ignore
        return app_storage_path()
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".photoai")


FORMATS = [("PNG", "PNG"), ("JPEG", "JPEG"), ("WebP", "WEBP")]
PRESETS = [("25%", 0.25), ("50%", 0.5), ("75%", 0.75), ("100%", 1.0)]


class ToolsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_dir = _app_dir()
        self.storage = LocalStorage(self.base_dir)

        self.source_path = None
        self.rgb_bytes = None
        self.w = 0
        self.h = 0

        # Настройки экспорта
        self.target_format = "JPEG"
        self.target_quality = 90
        self.scale = 1.0
        self.custom_size = None   # (w, h) или None

        self._build()
        theme.bind(bg=self._upd_bg)

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        # Top bar
        top = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(4))
        top.add_widget(IconButton(
            icon=ICON_BACK, variant="ghost",
            size_hint=(None, None), size=(dp(44), dp(44)),
            on_release=lambda *_: self._back()))
        top.add_widget(Label(text="Инструменты", font_name=theme.font_medium,
                              font_size=dp(16), color=theme.text))
        root.add_widget(top)

        self.preview = KivyImage(size_hint=(1, 1), allow_stretch=True,
                                  keep_ratio=True)
        root.add_widget(self.preview)

        self.info = Label(text="Файл не выбран",
                          size_hint_y=None, height=dp(36),
                          color=theme.text_muted,
                          font_name=theme.font_regular, font_size=dp(12))
        root.add_widget(self.info)

        root.add_widget(PillButton(text="Открыть фото",
                                    on_release=lambda *_: self._open(),
                                    size_hint_y=None, height=dp(48)))

        # Панель настроек
        scroll = ScrollView(size_hint=(1, None), height=dp(360),
                             scroll_type=["bars"], bar_width=dp(4))
        panel = BoxLayout(orientation="vertical", size_hint_y=None,
                          spacing=dp(2), padding=(dp(4), dp(4)))
        panel.bind(minimum_height=panel.setter("height"))
        scroll.add_widget(panel)

        # ─── Формат ───
        panel.add_widget(self._section_title("Формат"))
        fmt_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4))
        self._fmt_btns = {}
        for label, tag in FORMATS:
            b = PillButton(text=label, variant="secondary", font_size=dp(13))
            b.bind(on_release=lambda inst, t=tag: self._set_format(t))
            self._fmt_btns[tag] = b
            fmt_row.add_widget(b)
        panel.add_widget(fmt_row)

        # ─── Качество ───
        panel.add_widget(self._section_title("Качество (JPEG / WebP)"))
        self.quality_slider = SliderRow("Качество", 10, 100, 90,
                                         on_change=self._set_quality)
        panel.add_widget(self.quality_slider)

        # ─── Размер ───
        panel.add_widget(self._section_title("Размер"))
        scale_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4))
        self._scale_btns = {}
        for label, factor in PRESETS:
            b = PillButton(text=label, variant="secondary", font_size=dp(13))
            b.bind(on_release=lambda inst, f=factor: self._set_scale(f))
            self._scale_btns[factor] = b
            scale_row.add_widget(b)
        panel.add_widget(scale_row)

        panel.add_widget(PillButton(
            text="Ручной размер (W × H)", variant="secondary",
            size_hint_y=None, height=dp(44),
            on_release=lambda *_: self._show_size_dialog()))

        self.size_info = Label(text="", size_hint_y=None, height=dp(24),
                                color=theme.text_muted,
                                font_name=theme.font_regular, font_size=dp(11))
        panel.add_widget(self.size_info)

        # ─── EXIF ───
        panel.add_widget(self._section_title("Метаданные"))
        panel.add_widget(Label(
            text="EXIF (геопозиция, модель камеры, дата) удаляется автоматически",
            size_hint_y=None, height=dp(40),
            color=theme.text_muted, font_name=theme.font_regular,
            font_size=dp(11)))

        root.add_widget(scroll)

        # Кнопки сохранения
        save_row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(6))
        save_row.add_widget(PillButton(
            text="Сохранить", variant="primary",
            on_release=lambda *_: self._do_save(to_gallery=False)))
        save_row.add_widget(PillButton(
            text="В галерею", variant="secondary",
            on_release=lambda *_: self._do_save(to_gallery=True)))
        root.add_widget(save_row)

        self.add_widget(root)
        self._set_format("JPEG")
        self._set_scale(1.0)

    def _section_title(self, text):
        lbl = Label(text=text, size_hint_y=None, height=dp(28),
                    color=theme.text, font_name=theme.font_medium,
                    font_size=dp(13), halign="left", valign="middle")
        lbl.bind(size=lambda *_: setattr(lbl, "text_size", lbl.size))
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

    # ─── Настройки ───

    def _set_format(self, tag):
        self.target_format = tag
        for t, b in self._fmt_btns.items():
            b.variant = "primary" if t == tag else "secondary"
            b._upd_color()
        self._update_size_info()

    def _set_quality(self, val):
        self.target_quality = int(val)
        self._update_size_info()

    def _set_scale(self, factor):
        self.scale = factor
        self.custom_size = None
        for f, b in self._scale_btns.items():
            b.variant = "primary" if f == factor else "secondary"
            b._upd_color()
        self._update_size_info()

    def _show_size_dialog(self):
        if self.w == 0:
            self.info.text = "Сначала откройте фото"
            return
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))

        row1 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        row1.add_widget(Label(text="Ширина", size_hint_x=0.3,
                               color=theme.text, font_name=theme.font_regular,
                               font_size=dp(13)))
        w_in = TextInput(text=str(self.w), multiline=False,
                          input_filter="int", font_size=dp(14))
        row1.add_widget(w_in)
        root.add_widget(row1)

        row2 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        row2.add_widget(Label(text="Высота", size_hint_x=0.3,
                               color=theme.text, font_name=theme.font_regular,
                               font_size=dp(13)))
        h_in = TextInput(text=str(self.h), multiline=False,
                          input_filter="int", font_size=dp(14))
        row2.add_widget(h_in)
        root.add_widget(row2)

        hint = Label(text="Максимум 8192 px по каждой стороне",
                     size_hint_y=None, height=dp(24),
                     color=theme.text_muted, font_size=dp(11))
        root.add_widget(hint)

        btns = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        cancel = PillButton(text="Отмена", variant="ghost")
        ok = PillButton(text="Применить", variant="primary")

        def _cancel(*_):
            popup.dismiss()

        def _apply(*_):
            try:
                nw = int(w_in.text or self.w)
                nh = int(h_in.text or self.h)
                nw = max(1, min(nw, 8192))
                nh = max(1, min(nh, 8192))
                popup.dismiss()
                self.custom_size = (nw, nh)
                for f, b in self._scale_btns.items():
                    b.variant = "secondary"
                    b._upd_color()
                self._update_size_info()
            except Exception as e:
                self.info.text = f"Ошибка: {e}"

        cancel.bind(on_release=_cancel)
        ok.bind(on_release=_apply)
        btns.add_widget(cancel)
        btns.add_widget(ok)
        root.add_widget(btns)

        popup = Popup(title="Ручной размер", content=root,
                      size_hint=(0.85, 0.5), title_color=theme.text,
                      separator_color=theme.accent)
        popup.open()

    def _update_size_info(self):
        if self.w == 0:
            self.size_info.text = ""
            return
        if self.custom_size:
            tw, th = self.custom_size
        else:
            tw = int(self.w * self.scale)
            th = int(self.h * self.scale)
        n = tw * th
        if self.target_format == "PNG":
            est = n * 3 // 2
        else:
            est = n * 3 * self.target_quality // 300
        self.size_info.text = f"Результат: {tw}×{th} · ~{est // 1024} КБ"

    # ─── Загрузка ───

    def _open(self):
        def _done(path):
            if not path:
                return
            loaded = iu.load_image(path)
            if loaded is None:
                self.info.text = "Не удалось загрузить"
                return
            self.source_path = path
            self.rgb_bytes, self.w, self.h = loaded
            self.preview.texture = iu.to_texture(self.rgb_bytes, self.w, self.h)
            size_kb = os.path.getsize(path) // 1024
            self.info.text = f"{self.w}×{self.h} · {size_kb} КБ · {os.path.basename(path)}"
            self._update_size_info()
        pick_image(_done)

    # ─── Сохранение ───

    def _do_save(self, to_gallery=False):
        if self.source_path is None:
            self.info.text = "Сначала откройте фото"
            return
        ext_map = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}
        ext = ext_map[self.target_format]
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(self.storage.output_dir, f"conv_{ts}{ext}")

        if self.custom_size:
            tw, th = self.custom_size
        else:
            tw = int(self.w * self.scale)
            th = int(self.h * self.scale)

        self.info.text = "Обработка…"

        ok = iu.save_as_android(
            self.source_path, out_path,
            fmt=self.target_format,
            quality=self.target_quality,
            target_w=tw, target_h=th,
        )
        if not ok:
            self.info.text = "Ошибка сохранения"
            return

        size_kb = os.path.getsize(out_path) // 1024
        msg = f"Готово: {os.path.basename(out_path)} · {size_kb} КБ"

        if to_gallery:
            mime = {
                "PNG": "image/png",
                "JPEG": "image/jpeg",
                "WEBP": "image/webp",
            }[self.target_format]
            if save_to_gallery(out_path, mime=mime):
                msg += " · в галерее"

        self.info.text = msg

    def _back(self):
        self.manager.current = "home"