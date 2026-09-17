from kivy.app import App
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, FadeTransition

from app.ui.theme import theme
from app.ui.home_screen import HomeScreen
from app.ui.editor_screen import EditorScreen
from app.ui.tools_screen import ToolsScreen


class PhotoAIApp(App):
    title = "PhotoAI"

    def build(self):
        Window.clearcolor = theme.bg
        sm = ScreenManager(transition=FadeTransition(duration=0.15))
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(EditorScreen(name="editor"))
        sm.add_widget(ToolsScreen(name="tools"))
        return sm


if __name__ == "__main__":
    PhotoAIApp().run()