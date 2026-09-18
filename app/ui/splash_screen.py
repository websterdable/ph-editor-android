"""Splash-экран с логотипом и слоганом."""
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle, RoundedRectangle

from app.ui.theme import theme


class SplashScreen(Screen):
    def __init__(self, on_done=None, **kwargs):
        super().__init__(**kwargs)
        self._on_done = on_done

        root = BoxLayout(orientation="vertical", padding=dp(32))

        root.add_widget(BoxLayout())  # spacer

        # Логотип — стилизованная иконка
        icon = Label(
            text="\ue43b",  # photo_filter
            font_name=theme.font_icons,
            font_size=dp(80),
            color=theme.accent,
            size_hint_y=None, height=dp(100),
        )
        root.add_widget(icon)

        name = Label(
            text="PhotoAI",
            font_name=theme.font_bold,
            font_size=dp(34),
            color=theme.text,
            size_hint_y=None, height=dp(50),
        )
        root.add_widget(name)

        tagline = Label(
            text="Private by design",
            font_name=theme.font_regular,
            font_size=dp(14),
            color=theme.text_muted,
            size_hint_y=None, height=dp(30),
        )
        root.add_widget(tagline)

        root.add_widget(BoxLayout())  # spacer
        root.add_widget(BoxLayout())  # spacer

        self.add_widget(root)

        with self.canvas.before:
            Color(*theme.bg)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)
        theme.bind(bg=self._upd_color)

        # Через 1 секунду — переход на главный
        Clock.schedule_once(self._finish, 1.0)

    def _upd(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def _upd_color(self, *_):
        self._bg.texture = None  # форс перерисовки
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*theme.bg)
            self._bg = Rectangle(pos=self.pos, size=self.size)

    def _finish(self, dt):
        if self._on_done:
            self._on_done()