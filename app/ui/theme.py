"""Менеджер тем: dark/light + следование системе."""
from kivy.utils import platform
from kivy.event import EventDispatcher
from kivy.properties import StringProperty, ListProperty


DARK = {
    "bg":         [0.055, 0.055, 0.078, 1],
    "surface":    [0.102, 0.102, 0.141, 1],
    "surface_2":  [0.145, 0.145, 0.196, 1],
    "text":       [0.910, 0.910, 0.941, 1],
    "text_muted": [0.600, 0.600, 0.680, 1],
    "accent":     [0.486, 0.361, 1.000, 1],
    "accent_2":   [0.133, 0.827, 0.933, 1],
    "divider":    [0.200, 0.200, 0.260, 1],
}

LIGHT = {
    "bg":         [0.965, 0.965, 0.980, 1],
    "surface":    [1.000, 1.000, 1.000, 1],
    "surface_2":  [0.930, 0.930, 0.950, 1],
    "text":       [0.100, 0.100, 0.150, 1],
    "text_muted": [0.450, 0.450, 0.520, 1],
    "accent":     [0.420, 0.290, 0.950, 1],
    "accent_2":   [0.030, 0.640, 0.760, 1],
    "divider":    [0.850, 0.850, 0.880, 1],
}


def _system_is_dark():
    """Определить тему системы на Android. Иначе True (dark)."""
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
    """Единая точка правды о цветах. Слушается через bind(mode=...)."""
    mode = StringProperty("auto")  # auto | dark | light
    current = StringProperty("dark")  # фактически применённая

    bg = ListProperty()
    surface = ListProperty()
    surface_2 = ListProperty()
    text = ListProperty()
    text_muted = ListProperty()
    accent = ListProperty()
    accent_2 = ListProperty()
    divider = ListProperty()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(mode=self._apply, current=self._apply)
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


# Синглтон
theme = ThemeManager()