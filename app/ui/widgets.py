"""Кастомные стилизованные виджеты: карточки, слайдеры, кнопки."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.properties import StringProperty, NumericProperty, ListProperty

from app.ui.theme import theme


class ThemedBox(BoxLayout):
    """BoxLayout, автоматически подстраивающий фон под тему."""
    bg_role = StringProperty("bg")  # bg | surface | surface_2

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


class PillButton(Button):
    """Скруглённая кнопка в стиле темы."""

    def __init__(self, variant="primary", **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = theme.text
        self.font_size = dp(14)
        self.variant = variant
        # Явно задаём шрифт без эмодзи
        self.font_name = "Roboto"
        with self.canvas.before:
            self._color = Color(0, 0, 0, 0)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(20)])
        self.bind(pos=self._upd, size=self._upd)
        theme.bind(accent=self._upd_color, surface_2=self._upd_color, text=self._upd_color)
        self._upd_color()

    def _upd(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def _upd_color(self, *_):
        if self.variant == "primary":
            self._color.rgba = theme.accent
            self.color = (1, 1, 1, 1)
        elif self.variant == "ghost":
            self._color.rgba = (0, 0, 0, 0)
            self.color = theme.text
        else:  # secondary
            self._color.rgba = theme.surface_2
            self.color = theme.text


class SliderRow(BoxLayout):
    """Строка: подпись, значение, слайдер. Значение 0..100, вызывается on_change."""
    label = StringProperty("")
    value = NumericProperty(50)
    value_text = StringProperty("50")

    def __init__(self, label="", min_value=0, max_value=100, initial=50, on_change=None, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(48),
                         spacing=dp(6), **kwargs)
        self._min = min_value
        self._max = max_value
        self._on_change = on_change

        lbl = Label(text=label, size_hint_x=0.28, color=theme.text, font_size=dp(13),
                    halign="left", valign="middle")
        lbl.bind(size=lambda *_: setattr(lbl, "text_size", lbl.size))
        self.add_widget(lbl)

        self.slider = Slider(min=min_value, max=max_value, value=initial,
                             size_hint_x=0.55, cursor_size=(dp(20), dp(20)))
        self.slider.bind(value=self._on_slider)
        self.add_widget(self.slider)

        self.value_label = Label(text=str(int(initial)), size_hint_x=0.17,
                                 color=theme.text_muted, font_size=dp(12))
        self.add_widget(self.value_label)

        theme.bind(text=self._upd_colors, text_muted=self._upd_colors)

    def _upd_colors(self, *_):
        self.value_label.color = theme.text_muted

    def _on_slider(self, _slider, value):
        self.value_label.text = str(int(value))
        if self._on_change:
            self._on_change(value)

    def set_value(self, v):
        self.slider.value = v