"""Модуль 3: ИИ-редактор (временно недоступен без NumPy)."""
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle

from app.ui.theme import theme
from app.ui.widgets import PillButton


class AIScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        top.add_widget(PillButton(text="<", size_hint_x=None, width=dp(48),
                                   variant="secondary",
                                   on_release=lambda *_: self._back()))
        top.add_widget(Label(text="ИИ-Редактор", font_size=dp(16),
                              color=theme.text))
        root.add_widget(top)

        root.add_widget(BoxLayout())  # spacer

        msg = Label(
            text="[b]ИИ-модуль в разработке[/b]\n\n"
                 "Функции апскейла, восстановления лиц, замены фона и др. "
                 "появятся в следующих версиях.\n\n"
                 "Они требуют нейросетевых моделей и будут полностью "
                 "локальными — никакой отправки данных в облако.",
            markup=True, font_size=dp(13), color=theme.text_muted,
            halign="center")
        msg.bind(size=lambda *_: setattr(msg, "text_size", msg.size))
        root.add_widget(msg)

        root.add_widget(BoxLayout())  # spacer

        self.add_widget(root)
        theme.bind(bg=self._upd_bg)

    def _upd_bg(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*theme.bg)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd_bg, size=self._upd_bg)
        if hasattr(self, "_bg"):
            self._bg.pos = self.pos
            self._bg.size = self.size

    def _back(self):
        self.manager.current = "home"