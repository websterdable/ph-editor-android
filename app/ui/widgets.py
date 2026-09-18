"""Кастомные стилизованные виджеты: кнопки, иконки, слайдеры, карточки."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.graphics import Color, RoundedRectangle
from kivy.properties import StringProperty, NumericProperty, ListProperty

from app.ui.theme import theme


# ─── Иконки Material Symbols (юникод) ─────────────────────────

ICON_BACK = "\ue5c4"
ICON_UNDO = "\ue166"
ICON_REDO = "\ue15a"
ICON_SAVE = "\ue161"
ICON_UPLOAD = "\ue2c6"
ICON_EDITOR = "\ue43b"
ICON_TOOLS = "\ue869"
ICON_AI = "\ue65f"
ICON_THEME = "\ue3a8"
ICON_CROP = "\ue3be"
ICON_ROTATE_R = "\ue41a"
ICON_ROTATE_L = "\ue419"
ICON_FLIP = "\ue3e8"
ICON_SETTINGS = "\ue8b8"
ICON_HISTORY = "\ue889"
ICON_CHECK = "\ue86c"
ICON_ERROR = "\ue000"
ICON_CLOSE = "\ue5cd"
ICON_ADD = "\ue145"
ICON_REMOVE = "\ue15b"


# ─── Кнопки ───────────────────────────────────────────────────

class PillButton(Button):
    """Скруглённая кнопка с текстом, в стиле темы."""

    def __init__(self, variant="primary", **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = theme.text
        self.font_name = theme.font_medium
        self.font_size = dp(14)
        self.variant = variant
        with self.canvas.before:
            self._color = Color(0, 0, 0, 0)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
        self.bind(pos=self._upd, size=self._upd)
        theme.bind(accent=self._upd_color, surface_2=self._upd_color,
                   text=self._upd_color, font_medium=self._upd_font)
        self._upd_color()

    def _upd(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def _upd_font(self, *_):
        self.font_name = theme.font_medium

    def _upd_color(self, *_):
        if self.variant == "primary":
            self._color.rgba = theme.accent
            self.color = (1, 1, 1, 1)
        elif self.variant == "ghost":
            self._color.rgba = (0, 0, 0, 0)
            self.color = theme.text
        elif self.variant == "danger":
            self._color.rgba = theme.danger
            self.color = (1, 1, 1, 1)
        else:  # secondary
            self._color.rgba = theme.surface_2
            self.color = theme.text


class IconButton(Button):
    """Круглая иконочная кнопка с Material Symbol."""

    def __init__(self, icon="", variant="ghost", **kwargs):
        super().__init__(**kwargs)
        self.text = icon
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.font_name = theme.font_icons
        self.font_size = dp(24)
        self.color = theme.text
        self.variant = variant
        with self.canvas.before:
            self._color = Color(0, 0, 0, 0)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[dp(self.width / 2)])
        self.bind(pos=self._upd, size=self._upd_size)
        theme.bind(accent=self._upd_color, surface_2=self._upd_color,
                   text=self._upd_color, font_icons=self._upd_font)
        self._upd_color()

    def _upd(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._rect.radius = [dp(min(self.width, self.height) / 2)]

    def _upd_size(self, *_):
        self._upd()
        self._rect.radius = [dp(min(self.width, self.height) / 2)]

    def _upd_font(self, *_):
        self.font_name = theme.font_icons

    def _upd_color(self, *_):
        if self.variant == "primary":
            self._color.rgba = theme.accent
            self.color = (1, 1, 1, 1)
        elif self.variant == "secondary":
            self._color.rgba = theme.surface_2
            self.color = theme.text
        else:  # ghost
            self._color.rgba = (0, 0, 0, 0)
            self.color = theme.text


# ─── Slider row ───────────────────────────────────────────────

class SliderRow(BoxLayout):
    """Строка: подпись, слайдер, значение."""
    label = StringProperty("")
    value = NumericProperty(50)

    def __init__(self, label="", min_value=0, max_value=100, initial=50,
                 on_change=None, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(48), spacing=dp(6), **kwargs)
        self._on_change = on_change

        lbl = Label(text=label, size_hint_x=0.28, color=theme.text,
                    font_name=theme.font_regular, font_size=dp(13),
                    halign="left", valign="middle")
        lbl.bind(size=lambda *_: setattr(lbl, "text_size", lbl.size))
        self.add_widget(lbl)

        self.slider = Slider(min=min_value, max=max_value, value=initial,
                             size_hint_x=0.55, cursor_size=(dp(20), dp(20)))
        self.slider.bind(value=self._on_slider)
        self.add_widget(self.slider)

        self.value_label = Label(text=str(int(initial)), size_hint_x=0.17,
                                 color=theme.text_muted,
                                 font_name=theme.font_regular, font_size=dp(12))
        self.add_widget(self.value_label)

        theme.bind(text=self._upd_colors, text_muted=self._upd_colors,
                   font_regular=self._upd_font)

    def _upd_colors(self, *_):
        self.value_label.color = theme.text_muted

    def _upd_font(self, *_):
        self.value_label.font_name = theme.font_regular

    def _on_slider(self, _slider, value):
        self.value_label.text = str(int(value))
        if self._on_change:
            self._on_change(value)


# ─── ModuleCard ───────────────────────────────────────────────

class ModuleCard(BoxLayout):
    """Карточка-модуль на главном экране."""

    def __init__(self, icon="", title="", subtitle="", on_press=None, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(108), padding=dp(18), spacing=dp(14), **kwargs)
        with self.canvas.before:
            self._color = Color(*theme.surface)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(18)])
        self.bind(pos=self._upd, size=self._upd)
        theme.bind(surface=self._upd_color)

        # Иконка слева
        icon_box = BoxLayout(size_hint_x=None, width=dp(56))
        icon_lbl = Label(text=icon, font_size=dp(36), color=theme.accent,
                         font_name=theme.font_icons, halign="center", valign="middle")
        icon_lbl.bind(size=lambda *_: setattr(icon_lbl, "text_size", icon_lbl.size))
        icon_box.add_widget(icon_lbl)
        self.add_widget(icon_box)

        # Текст
        text_box = BoxLayout(orientation="vertical")
        t = Label(text=title, bold=True, font_size=dp(17), color=theme.text,
                  font_name=theme.font_bold, halign="left", valign="bottom")
        t.bind(size=lambda *_: setattr(t, "text_size", t.size))
        text_box.add_widget(t)
        s = Label(text=subtitle, font_size=dp(12), color=theme.text_muted,
                  font_name=theme.font_regular, halign="left", valign="top")
        s.bind(size=lambda *_: setattr(s, "text_size", s.size))
        text_box.add_widget(s)
        self.add_widget(text_box)

        self._on_press = on_press
        theme.bind(text=self._upd_color, text_muted=self._upd_color)

    def _upd(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def _upd_color(self, *_):
        self._color.rgba = theme.surface

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.opacity = 0.85
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        self.opacity = 1.0
        if self.collide_point(*touch.pos) and self._on_press:
            self._on_press()
            return True
        return super().on_touch_up(touch)


class ThemedBox(BoxLayout):
    bg_role = StringProperty("bg")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._color = Color(*getattr(theme, self.bg_role))
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[0])
        self.bind(pos=self._upd, size=self._upd)
        theme.bind(bg=self._upd, surface=self._upd, surface_2=self._upd)

    def _upd(self, *_):
        self._color.rgba = getattr(theme, self.bg_role)
        self._rect.pos = self.pos
        self._rect.size = self.size