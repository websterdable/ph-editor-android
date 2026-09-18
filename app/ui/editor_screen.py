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

from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup

from app.ui.widgets import (
    PillButton, SliderRow, IconButton,
    ICON_BACK, ICON_UNDO, ICON_REDO, ICON_SAVE,
    ICON_ROTATE_R, ICON_ROTATE_L, ICON_FLIP,
)
from app.ui.overlay import show_loading, hide_loading
from kivy.clock import Clock

def _app_dir():
    try:
        from android.storage import app_storage_path  # type: ignore
        return app_storage_path()
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".photoai")


TABS = ["Базовое", "Свет", "Фильтры", "Кроп", "Геометрия"]

CROP_PRESETS = [
    ("Оригинал", None),
    ("1 : 1",    (1, 1)),
    ("4 : 5",    (4, 5)),
    ("3 : 2",    (3, 2)),
    ("16 : 9",   (16, 9)),
    ("9 : 16",   (9, 16)),
]

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
        top = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(4))
        top.add_widget(IconButton(
            icon=ICON_BACK, variant="ghost",
            size_hint=(None, None), size=(dp(44), dp(44)),
            on_release=lambda *_: self._back()))
        self.title_lbl = Label(text="Редактор", font_name=theme.font_medium,
                                font_size=dp(16), color=theme.text)
        top.add_widget(self.title_lbl)
        top.add_widget(IconButton(
            icon=ICON_UNDO, variant="ghost",
            size_hint=(None, None), size=(dp(44), dp(44)),
            on_release=lambda *_: self._undo_step()))
        top.add_widget(IconButton(
            icon=ICON_REDO, variant="ghost",
            size_hint=(None, None), size=(dp(44), dp(44)),
            on_release=lambda *_: self._redo_step()))    
        
        # Кнопка «Текст»
        top.add_widget(IconButton(
            icon="\ue262",  # text_fields
            variant="ghost",
            size_hint=(None, None), size=(dp(44), dp(44)),
            on_release=lambda *_: self._show_text_dialog()))

        # Кнопка «Сравнить» — нажал: оригинал, отпустил: результат
        cmp_btn = IconButton(
            icon="\ue41d",  # compare
            variant="ghost",
            size_hint=(None, None), size=(dp(44), dp(44)))
        cmp_btn.bind(state=self._on_compare_state)
        top.add_widget(cmp_btn)

        top.add_widget(IconButton(
            icon=ICON_SAVE, variant="primary",
            size_hint=(None, None), size=(dp(44), dp(44)),
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

        self.tools_scroll = ScrollView(
            size_hint=(1, None), height=dp(170),
            scroll_type=["bars"],  # только через скроллбар, не через контент
            bar_width=dp(4),
        )
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
        elif name == "Свет":
            self._build_light()
        elif name == "Фильтры":
            self._build_filters()
        elif name == "Кроп":
            self._build_crop()
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

        def _expo(v):
            if self.original is None: return
            b, w, h = self.original
            self.current = (ops.exposure(b, v - 50), w, h)
            self._refresh_preview()

        def _satur(v):
            if self.original is None: return
            b, w, h = self.original
            self.current = (ops.saturation(b, v / 50.0), w, h)
            self._refresh_preview()

        def _sharp(v):
            if self.original is None: return
            b, w, h = self.original
            self.current = (ops.sharpness(b, w, h, v), w, h)
            self._refresh_preview()

        def _hue(v):
            if self.original is None: return
            b, w, h = self.original
            self.current = (ops.hue_shift(b, (v - 50) * 3.6), w, h)
            self._refresh_preview()

        self.tools_panel.add_widget(SliderRow("Яркость", 0, 100, 50, on_change=_bright))
        self.tools_panel.add_widget(SliderRow("Контраст", 0, 100, 50, on_change=_contrast))
        self.tools_panel.add_widget(SliderRow("Экспозиция", 0, 100, 50, on_change=_expo))
        self.tools_panel.add_widget(SliderRow("Насыщенность", 0, 200, 100, on_change=_satur))
        self.tools_panel.add_widget(SliderRow("Резкость", 0, 200, 0, on_change=_sharp))
        self.tools_panel.add_widget(SliderRow("Оттенок (Hue)", 0, 100, 50, on_change=_hue))
        self.tools_panel.add_widget(PillButton(
            text="Зафиксировать как шаг",
            on_release=lambda *_: self._push_undo(),
            size_hint_y=None, height=dp(40)))

    def _build_light(self):
        def _shadows(v):
            if self.original is None: return
            b, w, h = self.original
            self.current = (ops.shadows(b, v - 50), w, h)
            self._refresh_preview()

        def _highlights(v):
            if self.original is None: return
            b, w, h = self.original
            self.current = (ops.highlights(b, v - 50), w, h)
            self._refresh_preview()

        def _scurve(v):
            if self.original is None: return
            b, w, h = self.original
            self.current = (ops.s_curve(b, v - 50), w, h)
            self._refresh_preview()

        def _warm(v):
            if self.original is None: return
            b, w, h = self.original
            self.current = (ops.warmth(b, (v - 50) / 50.0), w, h)
            self._refresh_preview()

        self.tools_panel.add_widget(SliderRow("Тени", 0, 100, 50, on_change=_shadows))
        self.tools_panel.add_widget(SliderRow("Света", 0, 100, 50, on_change=_highlights))
        self.tools_panel.add_widget(SliderRow("S-кривая", 0, 100, 50, on_change=_scurve))
        self.tools_panel.add_widget(SliderRow("Тепло/Холод", 0, 100, 50, on_change=_warm))

    def _build_filters(self):
        display = {
            "none":       "Без фильтра",
            "vivid":      "Яркий",
            "vivid+":     "Яркий+",
            "film":       "Плёночный",
            "noir":       "Ч/Б контраст",
            "noir_soft":  "Ч/Б мягкий",
            "vintage":    "Винтаж",
            "cinematic":  "Кино",
            "cold":       "Холодный",
            "warm":       "Тёплый",
            "sepia":      "Сепия",
            "cyanotype":  "Циан",
            "fade":       "Fade",
            "dramatic":   "Драма",
            "retro":      "Ретро",
            "sunset":     "Закат",
            "mint":       "Мята",
            "pink":       "Розовый",
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
        show_loading(f"Фильтр: {name}…")
        Clock.schedule_once(lambda dt: self._do_apply_filter(name), 0.05)

    def _do_apply_filter(self, name):
        try:
            self._push_undo()
            fn = ops.FILTERS[name]
            b, w, h = self.original
            self.current = (fn(b, w, h), w, h)
            self._refresh_preview()
            self._set_status(f"Фильтр: {name}")
        except Exception as e:
            self._set_status(f"Ошибка: {e}")
        finally:
            hide_loading()

    def _build_geom(self):
        for txt, icon, cb in [
            ("Повернуть вправо", ICON_ROTATE_R, lambda *_: self._rotate(True)),
            ("Повернуть влево",  ICON_ROTATE_L, lambda *_: self._rotate(False)),
            ("Отразить гориз.",  ICON_FLIP,     lambda *_: self._flip("h")),
            ("Отразить верт.",   ICON_FLIP,     lambda *_: self._flip("v")),
        ]:
            row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
            b = IconButton(icon=icon, variant="secondary",
                            size_hint=(None, None), size=(dp(44), dp(44)))
            b.bind(on_release=cb)
            row.add_widget(b)
            lbl = Label(text=txt, color=theme.text, font_name=theme.font_regular,
                        font_size=dp(13), halign="left", valign="middle")
            lbl.bind(size=lambda *_: setattr(lbl, "text_size", lbl.size))
            row.add_widget(lbl)
            self.tools_panel.add_widget(row)

        # ─── Сравнение «до/после» ────────────────────────────────

    def _on_compare_state(self, btn, state):
        if self.original is None:
            return
        if state == "down":
            # Показываем оригинал
            b, w, h = self.original
            tex = iu.to_texture(b, w, h)
            if tex:
                self.preview.texture = tex
                self.preview.canvas.ask_update()
            self._set_status("Показан оригинал")
        else:
            # Возвращаем текущий результат
            self._refresh_preview()
            self._set_status("Показан результат")

    # ─── Кроп ────────────────────────────────────────────────

    def _build_crop(self):
        # Кнопки-пресеты
        for name, ratio in CROP_PRESETS:
            btn = PillButton(text=name, variant="secondary",
                             size_hint_y=None, height=dp(44))
            btn.bind(on_release=lambda inst, r=ratio: self._apply_crop_preset(r))
            self.tools_panel.add_widget(btn)

        # Разделитель
        sep = Label(text="Ручной кроп", size_hint_y=None, height=dp(28),
                    color=theme.text_muted, font_name=theme.font_regular,
                    font_size=dp(12))
        self.tools_panel.add_widget(sep)

        # Кнопка — открыть диалог с полями X/Y/W/H
        btn_manual = PillButton(text="Задать координаты", variant="primary",
                                 size_hint_y=None, height=dp(44))
        btn_manual.bind(on_release=lambda *_: self._show_crop_dialog())
        self.tools_panel.add_widget(btn_manual)

    def _apply_crop_preset(self, ratio):
        if self.current is None:
            self._set_status("Сначала откройте фото")
            return
        if ratio is None:
            # «Оригинал» — просто оставить как есть
            self._set_status("Кроп отменён")
            return
        show_loading("Кроп…")
        Clock.schedule_once(lambda dt: self._do_crop_preset(ratio), 0.05)

    def _do_crop_preset(self, ratio):
        try:
            self._push_undo()
            b, w, h = self.current
            new_b, new_w, new_h = ops.crop_centered(b, w, h, ratio[0], ratio[1])
            self.current = (new_b, new_w, new_h)
            self.original = self.current
            self._refresh_preview()
            self._set_status(f"Кроп {ratio[0]}:{ratio[1]} · {new_w}×{new_h}")
        except Exception as e:
            self._set_status(f"Ошибка: {e}")
        finally:
            hide_loading()


    def _show_crop_dialog(self):
        if self.current is None:
            self._set_status("Сначала откройте фото")
            return
        _, w, h = self.current

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))

        fields = {}
        for label, default in [("X", 0), ("Y", 0),
                                ("Ширина", w), ("Высота", h)]:
            row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
            lbl = Label(text=label, size_hint_x=0.3, color=theme.text,
                        font_name=theme.font_regular, font_size=dp(13))
            row.add_widget(lbl)
            ti = TextInput(text=str(default), multiline=False,
                           input_filter="int", font_size=dp(14))
            row.add_widget(ti)
            fields[label] = ti
            root.add_widget(row)

        hint = Label(text=f"Максимум: {w}×{h}",
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
                x = int(fields["X"].text or 0)
                y = int(fields["Y"].text or 0)
                cw = int(fields["Ширина"].text or w)
                ch = int(fields["Высота"].text or h)
                popup.dismiss()
                self._apply_manual_crop(x, y, cw, ch)
            except Exception as e:
                self._set_status(f"Ошибка: {e}")

        cancel.bind(on_release=_cancel)
        ok.bind(on_release=_apply)
        btns.add_widget(cancel)
        btns.add_widget(ok)
        root.add_widget(btns)

        popup = Popup(title="Ручной кроп", content=root,
                      size_hint=(0.9, 0.6), title_color=theme.text,
                      separator_color=theme.accent)
        popup.open()

    def _apply_manual_crop(self, x, y, cw, ch):
        if self.current is None:
            return
        show_loading("Кроп…")
        Clock.schedule_once(lambda dt: self._do_manual_crop(x, y, cw, ch), 0.05)

    def _do_manual_crop(self, x, y, cw, ch):
        try:
            self._push_undo()
            b, w, h = self.current
            new_b, new_w, new_h = ops.crop(b, w, h, x, y, cw, ch)
            self.current = (new_b, new_w, new_h)
            self.original = self.current
            self._refresh_preview()
            self._set_status(f"Кроп · {new_w}×{new_h}")
        except Exception as e:
            self._set_status(f"Ошибка: {e}")
        finally:
            hide_loading()

    # ─── Текст на фото ──────────────────────────────────────

    def _show_text_dialog(self):
        if self.current is None:
            self._set_status("Сначала откройте фото")
            return

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))

        ti = TextInput(text="", multiline=False, font_size=dp(15),
                       hint_text="Введите текст…")
        root.add_widget(ti)

        # Размер
        size_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        size_lbl = Label(text="Размер", size_hint_x=0.3, color=theme.text,
                         font_name=theme.font_regular, font_size=dp(13))
        size_row.add_widget(size_lbl)
        size_in = TextInput(text="48", multiline=False, input_filter="int",
                             font_size=dp(14))
        size_row.add_widget(size_in)
        root.add_widget(size_row)

        # Цвет
        color_lbl = Label(text="Цвет", size_hint_y=None, height=dp(24),
                          color=theme.text, font_name=theme.font_regular,
                          font_size=dp(13))
        root.add_widget(color_lbl)

        color_btns = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        color_map = {
            "Белый":    (255, 255, 255, 255),
            "Чёрный":   (0, 0, 0, 255),
            "Красный":  (255, 60, 60, 255),
            "Синий":    (60, 120, 255, 255),
            "Жёлтый":   (255, 220, 60, 255),
        }
        selected = {"color": (255, 255, 255, 255)}
        color_buttons = {}

        def _pick_color(name, rgba):
            selected["color"] = rgba
            for n, b in color_buttons.items():
                b.variant = "primary" if n == name else "secondary"
                b._upd_color()

        for name, rgba in color_map.items():
            b = PillButton(text=name, variant="secondary", font_size=dp(11))
            b.bind(on_release=lambda inst, n=name, c=rgba: _pick_color(n, c))
            color_buttons[name] = b
            color_btns.add_widget(b)
        root.add_widget(color_btns)

        # Кнопки
        btns = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        cancel = PillButton(text="Отмена", variant="ghost")
        ok = PillButton(text="Добавить", variant="primary")

        def _cancel(*_):
            popup.dismiss()

        def _apply(*_):
            text = ti.text.strip()
            if not text:
                popup.dismiss()
                return
            try:
                fs = int(size_in.text or 48)
            except Exception:
                fs = 48
            popup.dismiss()
            self._apply_text(text, fs, selected["color"])

        cancel.bind(on_release=_cancel)
        ok.bind(on_release=_apply)
        btns.add_widget(cancel)
        btns.add_widget(ok)
        root.add_widget(btns)

        popup = Popup(title="Текст на фото", content=root,
                      size_hint=(0.9, 0.7), title_color=theme.text,
                      separator_color=theme.accent)
        popup.open()

    def _apply_text(self, text, font_size, color):
        if self.current is None:
            return
        show_loading("Рендер текста…")
        Clock.schedule_once(
            lambda dt: self._do_apply_text(text, font_size, color), 0.05)

    def _do_apply_text(self, text, font_size, color):
        try:
            self._push_undo()
            b, w, h = self.current
            new_b = ops.text_overlay(b, w, h, text,
                                      font_size=font_size,
                                      color=color,
                                      x_ratio=0.5, y_ratio=0.85)
            self.current = (new_b, w, h)
            self._refresh_preview()
            self._set_status(f"Текст добавлен: «{text[:20]}…»")
        except Exception as e:
            self._set_status(f"Ошибка: {e}")
        finally:
            hide_loading()

    def _rotate(self, cw):
        if self.current is None:
            return
        show_loading("Поворот…")
        Clock.schedule_once(lambda dt: self._do_rotate(cw), 0.05)

    def _do_rotate(self, cw):
        try:
            self._push_undo()
            b, w, h = self.current
            new_b, new_w, new_h = ops.rotate_90(b, w, h, cw)
            self.current = (new_b, new_w, new_h)
            self.original = self.current
            self._refresh_preview()
            self._set_status("Повёрнуто")
        except Exception as e:
            self._set_status(f"Ошибка: {e}")
        finally:
            hide_loading()

    def _flip(self, direction):
        if self.current is None:
            return
        show_loading("Отражение…")
        Clock.schedule_once(lambda dt: self._do_flip(direction), 0.05)

    def _do_flip(self, direction):
        try:
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
        except Exception as e:
            self._set_status(f"Ошибка: {e}")
        finally:
            hide_loading()

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
            self._set_status("Сохранено в галерею")
        else:
            self._set_status("Не удалось экспортировать")

    def _back(self):
        self.manager.current = "home"