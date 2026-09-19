"""Оверлей загрузки: полупрозрачный фон + спиннер + текст."""
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.animation import Animation

from app.ui.theme import theme


class LoadingOverlay(FloatLayout):
    """Оверлей поверх экрана с вращающимся спиннером."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.opacity = 0
        self.disabled = True

        with self.canvas.before:
            self._bg_color = Color(0, 0, 0, 0.55)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)

        # Карточка по центру
        card = FloatLayout(size_hint=(None, None), size=(dp(180), dp(140)),
                           pos_hint={"center_x": 0.5, "center_y": 0.5})
        with card.canvas.before:
            self._card_color = Color(*theme.surface)
            self._card_rect = RoundedRectangle(pos=card.pos, size=card.size,
                                                radius=[dp(20)])
        card.bind(pos=self._upd_card, size=self._upd_card)

        # Спиннер — простая точка с анимацией opacity
        self._dot = Label(text="●", font_name=theme.font_icons,
                          font_size=dp(44), color=theme.accent,
                          size_hint=(None, None),
                          size=(dp(48), dp(48)),
                          pos_hint={"center_x": 0.5, "center_y": 0.65})
        card.add_widget(self._dot)

        self._status = Label(text="Обработка…",
                              font_name=theme.font_medium,
                              font_size=dp(13), color=theme.text,
                              size_hint=(None, None),
                              size=(dp(160), dp(24)),
                              pos_hint={"center_x": 0.5, "center_y": 0.25})
        card.add_widget(self._status)

        self.add_widget(card)

        self.bind(pos=self._upd, size=self._upd)
        theme.bind(surface=self._upd_theme)

    def _upd(self, *_):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def _upd_card(self, card, *_):
        self._card_rect.pos = card.pos
        self._card_rect.size = card.size

    def _upd_theme(self, *_):
        self._card_color.rgba = theme.surface
        self._dot.color = theme.accent
        self._status.color = theme.text

    def show(self, text="Обработка…"):
        self.disabled = False
        # Раскрываем обратно на весь родитель
        self.size_hint = (1, 1)
        self.size = self.parent.size if self.parent else (0, 0)
        self.pos = self.parent.pos if self.parent else (0, 0)
        self._status.text = text
        Animation(opacity=1, duration=0.15).start(self)
        # Пульсация спиннера
        anim = (Animation(opacity=0.3, duration=0.6) +
                Animation(opacity=1, duration=0.6))
        anim.repeat = True
        anim.start(self._dot)

    def hide(self):
        Animation(opacity=0, duration=0.15).start(self)
        Clock.schedule_once(self._really_hide, 0.2)
        Animation.cancel_all(self._dot)
    
    def on_touch_down(self, touch):
        if self.opacity < 0.1:
            return False  # пропустить тап вниз, в ScreenManager
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.opacity < 0.1:
            return False
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self.opacity < 0.1:
            return False
        return super().on_touch_up(touch)


    def _really_hide(self, dt):
        self.disabled = True
        self.opacity = 0
        # Схлопываем, чтобы виджет не занимал место и не ловил тапы
        self.size_hint = (None, None)
        self.size = (0, 0)


# Глобальный синглтон (инжектируется в ScreenManager)
_overlay = None


def attach_overlay(parent):
    """Добавить оверлей поверх любого контейнера (FloatLayout)."""
    global _overlay
    _overlay = LoadingOverlay()
    parent.add_widget(_overlay)
    return _overlay


def show_loading(text="Обработка…"):
    if _overlay:
        _overlay.show(text)


def hide_loading():
    if _overlay:
        _overlay.hide()