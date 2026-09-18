from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, NoTransition

from app.ui.theme import theme
from app.ui.splash_screen import SplashScreen
from app.ui.home_screen import HomeScreen
from app.ui.editor_screen import EditorScreen
from app.ui.tools_screen import ToolsScreen
from app.ui.ai_screen import AIScreen


class PhotoAIApp(App):
    title = "PhotoAI"

    def build(self):
        Window.clearcolor = theme.bg

        sm = ScreenManager(transition=NoTransition())

        # Splash первым
        splash = SplashScreen(name="splash", on_done=lambda: self._goto_home(sm))
        sm.add_widget(splash)

        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(EditorScreen(name="editor"))
        sm.add_widget(ToolsScreen(name="tools"))
        sm.add_widget(AIScreen(name="ai"))

        sm.current = "splash"

        # Форсируем первую отрисовку — убирает чёрный экран
        Clock.schedule_once(lambda dt: Window.canvas.ask_update(), 0.05)
        Clock.schedule_once(lambda dt: Window.canvas.ask_update(), 0.3)

        return sm

    def _goto_home(self, sm):
        sm.current = "home"
        # Ещё раз просим перерисовку после перехода
        Clock.schedule_once(lambda dt: Window.canvas.ask_update(), 0.1)


if __name__ == "__main__":
    PhotoAIApp().run()