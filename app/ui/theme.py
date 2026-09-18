"""Менеджер тем: dark/light + следование системе."""
from kivy.utils import platform
from kivy.event import EventDispatcher
from kivy.properties import StringProperty, ListProperty


DARK = {
    "bg":         [0.055, 0.055, 0.078, 1],   # #0E0E14
    "surface":    [0.102, 0.102, 0.141, 1],   # #1A1A24
    "surface_2":  [0.145, 0.145, 0.188, 1],   # #252530
    "text":       [0.941, 0.941, 0.961, 1],   # #F0F0F5
    "text_muted": [0.565, 0.565, 0.627, 1],   # #9090A0
    "accent":     [0.486, 0.361, 1.000, 1],   # #7C5CFF
    "accent_2":   [0.133, 0.827, 0.933, 1],   # #22D3EE
    "divider":    [0.165, 0.165, 0.208, 1],   # #2A2A35
    "success":    [0.290, 0.871, 0.502, 1],
    "danger":     [0.973, 0.443, 0.443, 1],
}

LIGHT = {
    "bg":         [0.961, 0.961, 0.969, 1],   # #F5F5F7
    "surface":    [1.000, 1.000, 1.000, 1],   # #FFFFFF
    "surface_2":  [0.925, 0.925, 0.941, 1],   # #ECECF0
    "text":       [0.059, 0.090, 0.165, 1],   # #0F172A Slate Navy
    "text_muted": [0.392, 0.455, 0.545, 1],   # #64748B
    "accent":     [0.357, 0.247, 0.878, 1],   # #5B3FE0
    "accent_2":   [0.031, 0.569, 0.698, 1],   # #0891B2
    "divider":    [0.886, 0.886, 0.910, 1],   # #E2E2E8
    "success":    [0.086, 0.639, 0.290, 1],
    "danger":     [0.937, 0.267, 0.267, 1],
}


def _system_is_dark():
    if platform != "android":
        return True
    try:
        from jnius import autoclass  # type: ignore
        Configuration = autoclass("android.content.res.Configuration")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        cfg = PythonActivity.mActivity.getResources().getConfiguration()
        mode = cfg.uiMode & Configuration.UI_MODE_NIGHT_MASK
        return mode == Configuration.UI_MODE_NIGHT_YES
    except Exception:
        return True


class ThemeManager(EventDispatcher):
    mode = StringProperty("auto")     # auto | dark | light
    current = StringProperty("dark")  # фактически применённая
    font_regular = StringProperty("assets/fonts/Inter-Regular.ttf")
    font_medium = StringProperty("assets/fonts/Inter-Medium.ttf")
    font_bold = StringProperty("assets/fonts/Inter-Bold.ttf")
    font_icons = StringProperty("assets/fonts/MaterialSymbols.ttf")

    bg = ListProperty()
    surface = ListProperty()
    surface_2 = ListProperty()
    text = ListProperty()
    text_muted = ListProperty()
    accent = ListProperty()
    accent_2 = ListProperty()
    divider = ListProperty()
    success = ListProperty()
    danger = ListProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(mode=self._apply)
        self._apply()

    def _apply(self, *_):
        if self.mode == "auto":
            self.current = "dark" if _system_is_dark() else "light"
        else:
            self.current = self.mode
        palette = DARK if self.current == "dark" else LIGHT
        for k, v in palette.items():
            setattr(self, k, v)

    def toggle(self):
        self.mode = "light" if self.current == "dark" else "dark"


theme = ThemeManager()