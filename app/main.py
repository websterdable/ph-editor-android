from kivy.app import App
from kivy.core.window import Window
from app.ui.main_screen import MainScreen


class PhotoAIApp(App):
    title = "PhotoAI"

    def build(self):
        Window.clearcolor = (0.08, 0.08, 0.10, 1)
        return MainScreen()


if __name__ == "__main__":
    PhotoAIApp().run()