"""Главный экран — хаб с выбором модуля."""
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle

from app.ui.theme import theme
from app.ui.widgets import PillButton


class ModuleCard(BoxLayout):
    """Кликабельная карточка с иконкой, названием и описанием модуля."""
    def __init__(self, icon="★", title="", subtitle="", on_press=None, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(110),
                         padding=dp(14), spacing=dp(12), **kwargs)
        with self.canvas.before:
            self._color = Color(*theme.surface)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(18)])
        self.bind(pos=self._upd, size=self._upd)
        theme.bind(surface=self._upd_color)

        ic = Label(text=icon, font_size=dp(34), size_hint_x=0.18,
                   color=theme.accent)
        self.add_widget(ic)

        text_box = BoxLayout(orientation="vertical")
        t = Label(text=title, bold=True, font_size=dp(17), color=theme.text,
                  halign="left", valign="bottom")
        t.bind(size=lambda *_: setattr(t, "text_size", t.size))
        text_box.add_widget(t)
        s = Label(text=subtitle, font_size=dp(12), color=theme.text_muted,
                  halign="left", valign="top")
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


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()
        theme.bind(bg=self._upd_bg)

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(14))

        # Шапка
        header = BoxLayout(size_hint_y=None, height=dp(60))
        title = Label(text="[b]PhotoAI[/b]", markup=True, font_size=dp(26),
                      color=theme.text, halign="left", valign="middle")
        title.bind(size=lambda *_: setattr(title, "text_size", title.size))
        header.add_widget(title)
        theme_btn = PillButton(text="☀", size_hint_x=None, width=dp(48),
                               variant="secondary")
        theme_btn.bind(on_release=lambda *_: theme.toggle())
        header.add_widget(theme_btn)
        root.add_widget(header)

        # Карточки модулей
        root.add_widget(ModuleCard(
            icon="✎", title="Редактор",
            subtitle="Базовые правки, фильтры, геометрия",
            on_press=lambda: self._go("editor")))
        root.add_widget(ModuleCard(
            icon="◆", title="Инструменты",
            subtitle="Размер, формат, сжатие, пакетно",
            on_press=lambda: self._go("tools")))
        root.add_widget(ModuleCard(
            icon="★", title="ИИ-Редактор",
            subtitle="Апскейл, лица, фон, колоризация",
            on_press=lambda: self._go("ai")))

        root.add_widget(BoxLayout())  # spacer

        version = Label(text="v0.3.0 · offline · 0 сетевых запросов",
                        font_size=dp(11), color=theme.text_muted,
                        size_hint_y=None, height=dp(24))
        root.add_widget(version)

        self.add_widget(root)
        theme.bind(text=self._upd_text)

    def _upd_bg(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*theme.bg)
            from kivy.graphics import Rectangle
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd_bg_rect, size=self._upd_bg_rect)

    def _upd_bg_rect(self, *_):
        if hasattr(self, "_bg"):
            self._bg.pos = self.pos
            self._bg.size = self.size

    def _upd_text(self, *_):
        pass

    def _go(self, name):
        self.manager.current = name