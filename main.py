from kivy.app import App
from kivy.uix.label import Label

class PhotoAIApp(App):
    def build(self):
        return Label(text="PhotoAI — стартовая заглушка")

if __name__ == "__main__":
    PhotoAIApp().run()
