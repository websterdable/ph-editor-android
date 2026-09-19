from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.screenmanager import ScreenManager, NoTransition

from app.ui.theme import theme
from app.ui.overlay import attach_overlay
from app.ui.splash_screen import SplashScreen
from app.ui.home_screen import HomeScreen
from app.ui.editor_screen import EditorScreen
from app.ui.tools_screen import ToolsScreen
from app.ui.ai_screen import AIScreen


class PhotoAIApp(App):
    title = "PhotoAI"

    def build(self):
        Window.clearcolor = theme.bg

        # ScreenManager со всеми экранами
        sm = ScreenManager(transition=NoTransition())

        splash = SplashScreen(name="splash", on_done=lambda: self._goto_home(sm))
        sm.add_widget(splash)
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(EditorScreen(name="editor"))
        sm.add_widget(ToolsScreen(name="tools"))
        sm.add_widget(AIScreen(name="ai"))

        sm.current = "splash"

        # Обёртка: FloatLayout содержит SM снизу и оверлей сверху
        root = FloatLayout()
        root.add_widget(sm)

        overlay = attach_overlay(root)
        # Синхронизируем размеры
        root.bind(size=lambda w, s: setattr(overlay, "size", s))
        root.bind(pos=lambda w, p: setattr(overlay, "pos", p))

        # Форсируем первую отрисовку — убирает чёрный экран
        Clock.schedule_once(lambda dt: Window.canvas.ask_update(), 0.05)
        Clock.schedule_once(lambda dt: Window.canvas.ask_update(), 0.3)

        return root

    def _goto_home(self, sm):
        sm.current = "home"
        Clock.schedule_once(lambda dt: Window.canvas.ask_update(), 0.1)


if __name__ == "__main__":
    PhotoAIApp().run()