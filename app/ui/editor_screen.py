"""Модуль 1: Классический редактор (без NumPy)."""
import os
import time
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image as KivyImage
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle
from kivy.logger import Logger

from app.core import image_utils as iu
from app.core import operations as ops
from app.core.file_picker import pick_image
from app.core.storage import LocalStorage
from app.core.exporter import save_to_gallery
from app.ui.theme import theme
from app.ui.widgets import PillButton, SliderRow


def _app_dir():
    try:
        from android.storage import app_storage_path  # type: ignore
        return app_storage_path()
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".photoai")


TABS = ["Базовое", "Тепло", "Фильтры", "Геометрия"]


class EditorScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_dir = _app_dir()
        self.storage = LocalStorage(self.base_dir)

        # Храним как (bytes, w, h)
        self.original = None   # tuple или None
        self.current = None    # tuple или None
        self._undo = []
        self._redo = []
        self.MAX_HISTORY = 8

        self.active_tab = "Базовое"
        self._build()
        theme.bind(bg=self._upd_bg)

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        # Верхняя панель
        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        top.add_widget(PillButton(text="←", size_hint_x=None, width=dp(48),
                                   variant="secondary",
                                   on_release=lambda *_: self._back()))
        top.add_widget(Label(text="Редактор", font_size=dp(15), color=theme.text))
        top.add_widget(PillButton(text="↶", size_hint_x=None, width=dp(48),
                                   variant="ghost",
                                   on_release=lambda *_: self._undo_step()))
        top.add_widget(PillButton(text="↷", size_hint_x=None, width=dp(48),
                                   variant="ghost",
                                   on_release=lambda *_: self._redo_step()))
        top.add_widget(PillButton(text="💾", size_hint_x=None, width=dp(48),
                                   variant="primary",
                                   on_release=lambda *_: self._save_all()))
        root.add_widget(top)

        self.preview = KivyImage(size_hint=(1, 1), allow_stretch=True,
                                  keep_ratio=True)
        root.add_widget(self.preview)

        self.status_lbl = Label(text="Откройте фото", size_hint_y=None,
                                 height=dp(22), font_size=dp(11),
                                 color=theme.text_muted)
        root.add_widget(self.status_lbl)

        actions = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        actions.add_widget(PillButton(text="Открыть",
                                       on_release=lambda *_: self._open(),
                                       variant="primary"))
        actions.add_widget(PillButton(text="В галерею",
                                       on_release=lambda *_: self._export(),
                                       variant="secondary"))
        actions.add_widget(PillButton(text="Сброс",
                                       on_release=lambda *_: self._reset(),
                                       variant="ghost"))
        root.add_widget(actions)

        tabs_row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(4))
        self._tab_btns = {}
        for name in TABS:
            btn = PillButton(text=name, variant="secondary", font_size=dp(11))
            btn.bind(on_release=lambda inst, n=name: self._select_tab(n))
            self._tab_btns[name] = btn
            tabs_row.add_widget(btn)
        root.add_widget(tabs_row)

        self.tools_scroll = ScrollView(size_hint=(1, None), height=dp(170))
        self.tools_panel = BoxLayout(orientation="vertical", size_hint_y=None,
                                       spacing=dp(2), padding=(dp(4), dp(4)))
        self.tools_panel.bind(minimum_height=self.tools_panel.setter("height"))
        self.tools_scroll.add_widget(self.tools_panel)
        root.add_widget(self.tools_scroll)

        self.add_widget(root)
        self._select_tab("Базовое")

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
                self._set_status("Файл не выбран")
                return
            loaded = iu.load_image(path)
            if loaded is None:
                self._set_status("Не удалось загрузить")
                return
            self.original = loaded
            self.current = loaded
            self._undo.clear()
            self._redo.clear()
            self._refresh_preview()
            b, w, h = loaded
            self._set_status(f"Открыто: {w}x{h}")
        pick_image(_done)

    def _refresh_preview(self):
        if self.current is None:
            return
        b, w, h = self.current
        tex = iu.to_texture(b, w, h)
        if tex:
            self.preview.texture = tex
            self.preview.canvas.ask_update()

    def _push_undo(self):
        if self.current is None:
            return
        self._undo.append(self.current)
        if len(self._undo) > self.MAX_HISTORY:
            self._undo.pop(0)
        self._redo.clear()

    def _undo_step(self):
        if not self._undo:
            self._set_status("Нечего отменять")
            return
        self._redo.append(self.current)
        self.current = self._undo.pop()
        self._refresh_preview()
        self._set_status("Отменено")

    def _redo_step(self):
        if not self._redo:
            self._set_status("Нечего повторять")
            return
        self._undo.append(self.current)
        self.current = self._redo.pop()
        self._refresh_preview()
        self._set_status("Повторено")

    def _reset(self):
        if self.original is None:
            return
        self._push_undo()
        self.current = self.original
        self._refresh_preview()
        self._set_status("Сброшено")

    def _set_status(self, text):
        self.status_lbl.text = text

    def _select_tab(self, name):
        self.active_tab = name
        for tab_name, btn in self._tab_btns.items():
            btn.variant = "primary" if tab_name == name else "secondary"
            btn._upd_color()
        self.tools_panel.clear_widgets()
        if name == "Базовое":
            self._build_basic()
        elif name == "Тепло":
            self._build_warmth()
        elif name == "Фильтры":
            self._build_filters()
        elif name == "Геометрия":
            self._build_geom()

    def _build_basic(self):
        def _bright(v):
            if self.original is None: return
            b, w, h = self.original
            self.current = (ops.brightness(b, v / 100.0 + 0.5), w, h)
            self._refresh_preview()

        def _contrast(v):
            if self.original is None: return
            b, w, h = self.original
            self.current = (ops.contrast(b, v / 100.0 + 0.5), w, h)
            self._refresh_preview()

        self.tools_panel.add_widget(SliderRow("Яркость", 0, 100, 50, on_change=_bright))
        self.tools_panel.add_widget(SliderRow("Контраст", 0, 100, 50, on_change=_contrast))
        self.tools_panel.add_widget(PillButton(
            text="Зафиксировать как шаг",
            on_release=lambda *_: self._push_undo(),
            size_hint_y=None, height=dp(40)))

    def _build_warmth(self):
        def _warm(v):
            if self.original is None: return
            b, w, h = self.original
            self.current = (ops.warmth(b, (v - 50) / 50.0), w, h)
            self._refresh_preview()
        self.tools_panel.add_widget(SliderRow("Тепло/Холод", 0, 100, 50, on_change=_warm))

    def _build_filters(self):
        display = {
            "none": "Без фильтра", "vivid": "Яркий", "film": "Плёночный",
            "noir": "Ч/Б", "vintage": "Винтаж",
            "cinematic": "Кино", "cold": "Холодный", "warm": "Тёплый",
        }
        for name in display:
            btn = PillButton(text=display[name], variant="secondary",
                             size_hint_y=None, height=dp(40))
            btn.bind(on_release=lambda inst, n=name: self._apply_filter(n))
            self.tools_panel.add_widget(btn)

    def _apply_filter(self, name):
        if self.original is None:
            self._set_status("Сначала откройте фото")
            return
        self._push_undo()
        fn = ops.FILTERS[name]
        b, w, h = self.original
        self.current = (fn(b, w, h), w, h)
        self._refresh_preview()
        self._set_status(f"Фильтр: {name}")

    def _build_geom(self):
        self.tools_panel.add_widget(PillButton(
            text="↻ Повернуть вправо", variant="secondary",
            size_hint_y=None, height=dp(40),
            on_release=lambda *_: self._rotate(True)))
        self.tools_panel.add_widget(PillButton(
            text="↺ Повернуть влево", variant="secondary",
            size_hint_y=None, height=dp(40),
            on_release=lambda *_: self._rotate(False)))
        self.tools_panel.add_widget(PillButton(
            text="↔ Отразить Г", variant="secondary",
            size_hint_y=None, height=dp(40),
            on_release=lambda *_: self._flip("h")))
        self.tools_panel.add_widget(PillButton(
            text="↕ Отразить В", variant="secondary",
            size_hint_y=None, height=dp(40),
            on_release=lambda *_: self._flip("v")))

    def _rotate(self, cw):
        if self.current is None:
            return
        self._push_undo()
        b, w, h = self.current
        new_b, new_w, new_h = ops.rotate_90(b, w, h, cw)
        self.current = (new_b, new_w, new_h)
        self.original = self.current
        self._refresh_preview()
        self._set_status("Повёрнуто")

    def _flip(self, direction):
        if self.current is None:
            return
        self._push_undo()
        b, w, h = self.current
        if direction == "h":
            new_b = ops.flip_h(b, w, h)
        else:
            new_b = ops.flip_v(b, w, h)
        self.current = (new_b, w, h)
        self.original = self.current
        self._refresh_preview()
        self._set_status("Отражено")

    def _save_all(self):
        if self.current is None:
            self._set_status("Нечего сохранять")
            return
        b, w, h = self.current
        ts = time.strftime("%Y%m%d_%H%M%S")
        out = os.path.join(self.storage.output_dir, f"edit_{ts}.png")
        if iu.save_image(b, w, h, out):
            self._set_status(f"Сохранено: {os.path.basename(out)}")
        else:
            self._set_status("Ошибка сохранения")

    def _export(self):
        if self.current is None:
            self._set_status("Нечего экспортировать")
            return
        b, w, h = self.current
        ts = time.strftime("%Y%m%d_%H%M%S")
        tmp = os.path.join(self.storage.output_dir, f"export_{ts}.png")
        if not iu.save_image(b, w, h, tmp):
            self._set_status("Ошибка сохранения")
            return
        if save_to_gallery(tmp, mime="image/png"):
            self._set_status("✅ Сохранено в галерею")
        else:
            self._set_status("Не удалось экспортировать")

    def _back(self):
        self.manager.current = "home"