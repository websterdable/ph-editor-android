"""Модуль 1: Классический редактор."""
import os
import time
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image as KivyImage
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle, RoundedRectangle
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


TABS = ["Базовое", "Свет", "Фильтры", "Геометрия"]


class EditorScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_dir = _app_dir()
        self.storage = LocalStorage(self.base_dir)

        # Оригинал (никогда не меняется) и текущее состояние
        self.original = None
        self.current = None
        # Undo/Redo — стеки numpy-массивов (ограничим 15)
        self._undo = []
        self._redo = []
        self.MAX_HISTORY = 15

        # Активный таб
        self.active_tab = "Базовое"

        self._build()
        theme.bind(bg=self._upd_bg)

    # ---------- UI ----------

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        # Верхняя панель
        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        top.add_widget(PillButton(text="←", size_hint_x=None, width=dp(48),
                                   variant="secondary",
                                   on_release=lambda *_: self._back()))
        self.title_lbl = Label(text="Редактор", font_size=dp(15), color=theme.text)
        top.add_widget(self.title_lbl)
        top.add_widget(PillButton(text="↶", size_hint_x=None, width=dp(48),
                                   variant="ghost",
                                   on_release=lambda *_: self._undo_step()))
        top.add_widget(PillButton(text="↷", size_hint_x=None, width=dp(48),
                                   variant="ghost",
                                   on_release=lambda *_: self._redo_step()))
        top.add_widget(PillButton(text="Сохранить", size_hint_x=None, width=dp(110),
                                   variant="primary",
                                   on_release=lambda *_: self._save_all()))
        root.add_widget(top)

        # Превью
        self.preview = KivyImage(size_hint=(1, 1), allow_stretch=True,
                                  keep_ratio=True)
        root.add_widget(self.preview)

        # Строка статуса
        self.status_lbl = Label(text="Откройте фото для начала",
                                 size_hint_y=None, height=dp(22),
                                 font_size=dp(11), color=theme.text_muted)
        root.add_widget(self.status_lbl)

        # Кнопки главных действий
        actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        actions.add_widget(PillButton(text="Открыть",
                                       on_release=lambda *_: self._open(),
                                       variant="primary"))
        actions.add_widget(PillButton(text="В галерею",
                                       on_release=lambda *_: self._export(),
                                       variant="secondary"))
        actions.add_widget(PillButton(text="Сбросить",
                                       on_release=lambda *_: self._reset(),
                                       variant="ghost"))
        root.add_widget(actions)

        # Табы
        tabs_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(4))
        self._tab_btns = {}
        for name in TABS:
            btn = PillButton(text=name, variant="secondary", font_size=dp(12))
            btn.bind(on_release=lambda inst, n=name: self._select_tab(n))
            self._tab_btns[name] = btn
            tabs_row.add_widget(btn)
        root.add_widget(tabs_row)

        # Панель инструментов (скроллится по вертикали)
        self.tools_scroll = ScrollView(size_hint=(1, None), height=dp(180))
        self.tools_panel = BoxLayout(orientation="vertical", size_hint_y=None,
                                       spacing=dp(2), padding=(dp(4), dp(4)))
        self.tools_panel.bind(minimum_height=self.tools_panel.setter("height"))
        self.tools_scroll.add_widget(self.tools_panel)
        root.add_widget(self.tools_scroll)

        self.add_widget(root)
        self._select_tab("Базовое")

    # ---------- Тема ----------

    def _upd_bg(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*theme.bg)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd_bg, size=self._upd_bg)
        if hasattr(self, "_bg"):
            self._bg.pos = self.pos
            self._bg.size = self.size

    # ---------- Работа с фото ----------

    def _open(self):
        def _done(path):
            if not path:
                self._set_status("Файл не выбран")
                return
            arr = iu.load_image(path)
            if arr is None:
                self._set_status("Не удалось загрузить")
                return
            # Уменьшим для скорости превью
            arr = iu.resize_max_side(arr, 1600)
            self.original = arr.copy()
            self.current = arr.copy()
            self._undo.clear()
            self._redo.clear()
            self._refresh_preview()
            self._set_status(f"Открыто: {arr.shape[1]}x{arr.shape[0]}")
        pick_image(_done)

    def _refresh_preview(self):
        if self.current is None:
            return
        tex = iu.to_texture(self.current)
        if tex:
            self.preview.texture = tex
            self.preview.canvas.ask_update()

    def _push_undo(self):
        """Перед изменением — сохранить текущее состояние в undo-стек."""
        if self.current is None:
            return
        self._undo.append(self.current.copy())
        if len(self._undo) > self.MAX_HISTORY:
            self._undo.pop(0)
        self._redo.clear()

    def _undo_step(self):
        if not self._undo:
            self._set_status("Нечего отменять")
            return
        self._redo.append(self.current.copy())
        self.current = self._undo.pop()
        self._refresh_preview()
        self._set_status("Отменено")

    def _redo_step(self):
        if not self._redo:
            self._set_status("Нечего повторять")
            return
        self._undo.append(self.current.copy())
        self.current = self._redo.pop()
        self._refresh_preview()
        self._set_status("Повторено")

    def _reset(self):
        if self.original is None:
            return
        self._push_undo()
        self.current = self.original.copy()
        self._refresh_preview()
        self._set_status("Сброшено к оригиналу")

    def _set_status(self, text):
        self.status_lbl.text = text

    # ---------- Панель инструментов ----------

    def _select_tab(self, name):
        self.active_tab = name
        # Подсветка активной кнопки
        for tab_name, btn in self._tab_btns.items():
            btn.variant = "primary" if tab_name == name else "secondary"
            btn._upd_color()
        # Наполняем панель
        self.tools_panel.clear_widgets()
        if name == "Базовое":
            self._build_basic_tools()
        elif name == "Свет":
            self._build_light_tools()
        elif name == "Фильтры":
            self._build_filters_tools()
        elif name == "Геометрия":
            self._build_geom_tools()

    def _apply_slider(self, func, value):
        """Общий обработчик — применяет операцию из оригинала."""
        if self.original is None:
            self._set_status("Сначала откройте фото")
            return
        self._push_undo()
        self.current = func(value)
        self._refresh_preview()

    def _build_basic_tools(self):
        def _bright(v):
            if self.original is None: return
            self.current = ops.brightness(self.original, v / 100.0 + 0.5)
            self._refresh_preview()

        def _contrast(v):
            if self.original is None: return
            self.current = ops.contrast(self.original, v / 100.0 + 0.5)
            self._refresh_preview()

        def _satur(v):
            if self.original is None: return
            self.current = ops.saturation(self.original, v / 50.0)
            self._refresh_preview()

        def _sharp(v):
            if self.original is None: return
            self.current = ops.sharpness(self.original, v / 50.0)
            self._refresh_preview()

        self.tools_panel.add_widget(SliderRow("Яркость", 0, 100, 50, on_change=_bright))
        self.tools_panel.add_widget(SliderRow("Контраст", 0, 100, 50, on_change=_contrast))
        self.tools_panel.add_widget(SliderRow("Насыщен.", 0, 100, 50, on_change=_satur))
        self.tools_panel.add_widget(SliderRow("Резкость", 0, 100, 0, on_change=_sharp))
        self.tools_panel.add_widget(PillButton(text="Зафиксировать как шаг",
                                                on_release=lambda *_: self._push_undo(),
                                                size_hint_y=None, height=dp(40)))

    def _build_light_tools(self):
        def _warm(v):
            if self.original is None: return
            self.current = ops.warmth(self.original, (v - 50) / 50.0)
            self._refresh_preview()
        self.tools_panel.add_widget(SliderRow("Тепло", 0, 100, 50, on_change=_warm))
        self.tools_panel.add_widget(Label(text="Больше опций — в будущих версиях",
                                            size_hint_y=None, height=dp(40),
                                            color=theme.text_muted))

    def _build_filters_tools(self):
        for name, fn in ops.FILTERS.items():
            display = {
                "none": "Без фильтра", "vivid": "Яркий", "film": "Плёночный",
                "noir": "Чёрно-белый", "vintage": "Винтаж",
                "cinematic": "Кино", "cyan": "Циан", "sepia": "Сепия",
            }.get(name, name)
            btn = PillButton(text=display, variant="secondary",
                             size_hint_y=None, height=dp(40))
            btn.bind(on_release=lambda inst, f=fn: self._apply_filter(f))
            self.tools_panel.add_widget(btn)

    def _apply_filter(self, fn):
        if self.original is None:
            self._set_status("Сначала откройте фото")
            return
        self._push_undo()
        self.current = fn(self.original)
        self._refresh_preview()
        self._set_status("Фильтр применён")

    def _build_geom_tools(self):
        self.tools_panel.add_widget(PillButton(
            text="↻ Повернуть вправо", variant="secondary",
            size_hint_y=None, height=dp(40),
            on_release=lambda *_: self._apply_op(ops.rotate_90, True)))
        self.tools_panel.add_widget(PillButton(
            text="↺ Повернуть влево", variant="secondary",
            size_hint_y=None, height=dp(40),
            on_release=lambda *_: self._apply_op(ops.rotate_90, False)))
        self.tools_panel.add_widget(PillButton(
            text="↔ Отразить по горизонтали", variant="secondary",
            size_hint_y=None, height=dp(40),
            on_release=lambda *_: self._apply_op(ops.flip_h)))
        self.tools_panel.add_widget(PillButton(
            text="↕ Отразить по вертикали", variant="secondary",
            size_hint_y=None, height=dp(40),
            on_release=lambda *_: self._apply_op(ops.flip_v)))

    def _apply_op(self, fn, *args):
        if self.current is None:
            self._set_status("Сначала откройте фото")
            return
        self._push_undo()
        self.current = fn(self.current, *args)
        # Обновим "оригинал" тоже, т.к. геометрия фундаментальна
        self.original = self.current.copy()
        self._refresh_preview()
        self._set_status("Готово")

    # ---------- Сохранение ----------

    def _save_all(self):
        if self.current is None:
            self._set_status("Нечего сохранять")
            return
        ts = time.strftime("%Y%m%d_%H%M%S")
        out = os.path.join(self.storage.output_dir, f"edit_{ts}.png")
        if iu.save_image(self.current, out):
            self.storage.save_result("edit", "editor", self.current, iu.save_image)
            self._set_status(f"Сохранено: {os.path.basename(out)}")
        else:
            self._set_status("Ошибка сохранения")

    def _export(self):
        if self.current is None:
            self._set_status("Нечего экспортировать")
            return
        ts = time.strftime("%Y%m%d_%H%M%S")
        tmp = os.path.join(self.storage.output_dir, f"export_{ts}.png")
        if not iu.save_image(self.current, tmp):
            self._set_status("Ошибка сохранения")
            return
        if save_to_gallery(tmp, mime="image/png"):
            self._set_status("✅ Сохранено в галерею (Pictures/PhotoAI)")
        else:
            self._set_status("Не удалось экспортировать (нет доступа)")

    def _back(self):
        self.manager.current = "home"