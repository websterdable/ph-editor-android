"""Главный экран — хаб с выбором модуля."""
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle

from app.ui.theme import theme
from app.ui.widgets import (
    ModuleCard, IconButton,
    ICON_EDITOR, ICON_TOOLS, ICON_AI, ICON_THEME,
)


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()
        theme.bind(bg=self._upd_bg)

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(14))

        # Шапка
        header = BoxLayout(size_hint_y=None, height=dp(60), spacing=dp(6))
        title = Label(text="PhotoAI", font_name=theme.font_bold,
                      font_size=dp(28), color=theme.text,
                      halign="left", valign="middle")
        title.bind(size=lambda *_: setattr(title, "text_size", title.size))
        header.add_widget(title)

        theme_btn = IconButton(icon=ICON_THEME, variant="secondary",
                                size_hint=(None, None), size=(dp(48), dp(48)))
        theme_btn.bind(on_release=lambda *_: theme.toggle())
        header.add_widget(theme_btn)
        root.add_widget(header)

        root.add_widget(ModuleCard(
            icon=ICON_EDITOR, title="Редактор",
            subtitle="Коррекция, фильтры, кроп, текст",
            on_press=lambda: self._go("editor")))
        root.add_widget(ModuleCard(
            icon=ICON_TOOLS, title="Инструменты",
            subtitle="Формат, размер, качество, EXIF",
            on_press=lambda: self._go("tools")))
        root.add_widget(ModuleCard(
            icon=ICON_AI, title="ИИ-Редактор",
            subtitle="Апскейл, лица, фон",
            on_press=lambda: self._go("ai")))

        root.add_widget(BoxLayout())

        version = Label(text="v0.5.0 · offline · Private by design",
                        font_name=theme.font_regular,
                        font_size=dp(11), color=theme.text_muted,
                        size_hint_y=None, height=dp(24))
        root.add_widget(version)

        self.add_widget(root)

    def _upd_bg(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*theme.bg)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd_bg, size=self._upd_bg)
        if hasattr(self, "_bg"):
            self._bg.pos = self.pos
            self._bg.size = self.size

    def _go(self, name):
        self.manager.current = name