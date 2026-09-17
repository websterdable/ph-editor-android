"""Модуль 3: ИИ-редактор."""
import os
import threading
import time
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image as KivyImage
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.logger import Logger

from app.core import image_utils as iu
from app.core.file_picker import pick_image
from app.core.storage import LocalStorage
from app.core.exporter import save_to_gallery
from app.core.ai_engine import AIEngine
from app.core import ai_operations as aio
from app.ui.theme import theme
from app.ui.widgets import PillButton


def _app_dir():
    try:
        from android.storage import app_storage_path  # type: ignore
        return app_storage_path()
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".photoai")


def _models_dir():
    """Папка моделей внутри app storage."""
    d = os.path.join(_app_dir(), "models")
    os.makedirs(d, exist_ok=True)
    return d


class AIScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.storage = LocalStorage(_app_dir())
        self.engine = AIEngine(_models_dir())
        self.original = None
        self.current = None
        self._busy = False
        self._build()
        theme.bind(bg=self._upd_bg)

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        # Шапка
        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        top.add_widget(PillButton(
            text="←", size_hint_x=None, width=dp(48), variant="secondary",
            on_release=lambda *_: self._back()))
        self.title = Label(text="✨ ИИ-Редактор", font_size=dp(16),
                            color=theme.text)
        top.add_widget(self.title)
        top.add_widget(PillButton(
            text="💾", size_hint_x=None, width=dp(48), variant="secondary",
            on_release=lambda *_: self._export()))
        root.add_widget(top)

        # Превью
        self.preview = KivyImage(size_hint=(1, 1), allow_stretch=True,
                                  keep_ratio=True)
        root.add_widget(self.preview)

        # Прогресс
        self.progress = Label(
            text="", size_hint_y=None, height=dp(24),
            font_size=dp(11), color=theme.accent_2)
        root.add_widget(self.progress)

        # Статус моделей
        self.models_status = Label(
            text="", size_hint_y=None, height=dp(22),
            font_size=dp(10), color=theme.text_muted)
        root.add_widget(self.models_status)
        self._refresh_models_status()

        # Кнопки
        actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        actions.add_widget(PillButton(
            text="Открыть фото", variant="primary",
            on_release=lambda *_: self._open()))
        actions.add_widget(PillButton(
            text="Сброс", variant="ghost",
            on_release=lambda *_: self._reset()))
        actions.add_widget(PillButton(
            text="Модели", variant="secondary",
            on_release=lambda *_: self._show_models()))
        root.add_widget(actions)

        # Сетка кнопок ИИ-функций (скроллится)
        sv = ScrollView(size_hint=(1, None), height=dp(220))
        grid = BoxLayout(orientation="vertical", size_hint_y=None,
                          spacing=dp(4), padding=(dp(4), dp(4)))
        grid.bind(minimum_height=grid.setter("height"))

        for label, key, enabled in [
            ("⬆ Апскейл x4",          "upscale",    True),
            ("👤 Улучшить лица",       "face",       True),
            ("🧹 Удалить шум",         "denoise",    True),
            ("🎨 Колоризация",          "colorize",   True),
            ("👴 Состарить",            "age_old",    True),
            ("👶 Омолодить",            "age_young",  True),
            ("✂ Удалить фон",          "remove_bg",  True),
            ("🖌 Удалить объект",       "inpaint",    False),
        ]:
            btn = PillButton(text=label, variant="secondary",
                              size_hint_y=None, height=dp(44))
            btn.bind(on_release=lambda inst, k=key: self._run(k))
            grid.add_widget(btn)
        sv.add_widget(grid)
        root.add_widget(sv)

        self.add_widget(root)

    # ---------- Тема ----------

    def _upd_bg(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*theme.bg)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd_bg, size=self._upd_bg)
        if hasattr(self, "_bg"):
            self._bg.pos = self.pos
            self._bg.size = self.size

    # ---------- Модели ----------

    def _refresh_models_status(self):
        if not self.engine.is_ready():
            self.models_status.text = "ONNX Runtime недоступен"
            self.models_status.color = theme.text_muted
            return
        found = self.engine.list_models()
        if not found:
            self.models_status.text = "Модели не найдены в папке models/"
            self.models_status.color = theme.text_muted
        else:
            self.models_status.text = f"Моделей: {len(found)} — {', '.join(found)}"
            self.models_status.color = theme.accent_2

    def _show_models(self):
        lines = [
            f"• {m}" for m in (self.engine.list_models() or ["(пусто)"])
        ]
        content = Label(
            text="Найдены модели:\n" + "\n".join(lines) +
                 "\n\nПоместите .onnx-файлы в:\n" +
                 os.path.join(_app_dir(), "models"),
            color=theme.text, font_size=dp(12),
        )
        Popup(title="Модели", content=content,
              size_hint=(0.9, 0.6)).open()

    # ---------- Работа с фото ----------

    def _open(self):
        def _done(path):
            if not path:
                return
            arr = iu.load_image(path)
            if arr is None:
                self.progress.text = "Не удалось загрузить"
                return
            arr = iu.resize_max_side(arr, 1600)
            self.original = arr.copy()
            self.current = arr.copy()
            self._refresh_preview()
            self.progress.text = f"Готово · {arr.shape[1]}×{arr.shape[0]}"
        pick_image(_done)

    def _refresh_preview(self):
        if self.current is None:
            return
        tex = iu.to_texture(self.current)
        if tex:
            self.preview.texture = tex
            self.preview.canvas.ask_update()

    def _reset(self):
        if self.original is None:
            return
        self.current = self.original.copy()
        self._refresh_preview()
        self.progress.text = "Сброшено"

    def _back(self):
        self.manager.current = "home"

    # ---------- Запуск ИИ-операций ----------

    def _run(self, key):
        if self._busy:
            return
        if self.current is None:
            self.progress.text = "Сначала откройте фото"
            return
        if not self.engine.is_ready():
            self.progress.text = "ONNX Runtime недоступен"
            return

        self._busy = True
        self.progress.text = f"Обработка: {key}…"
        threading.Thread(target=self._worker, args=(key,), daemon=True).start()

    def _worker(self, key):
        start = time.time()
        try:
            img = self.current
            result = None

            if key == "upscale":
                result = aio.upscale(self.engine, img)
            elif key == "face":
                result = aio.restore_face(self.engine, img)
            elif key == "denoise":
                result = aio.denoise(self.engine, img)
            elif key == "colorize":
                result = aio.colorize(self.engine, img)
            elif key == "age_old":
                result = aio.age_transform(self.engine, img, "old", 0.7)
            elif key == "age_young":
                result = aio.age_transform(self.engine, img, "young", 0.7)
            elif key == "remove_bg":
                result = aio.remove_background(self.engine, img)
            elif key == "inpaint":
                self._post_status("Функция пока не подключена")
                return

            elapsed = time.time() - start
            if result is None:
                self._post_status(f"{key}: модель недоступна")
            else:
                self._post_result(key, result, elapsed)
        except Exception as e:
            Logger.error(f"AIWorker({key}): {e}")
            self._post_status(f"Ошибка: {e}")
        finally:
            self._busy = False

    def _post_result(self, key, result, elapsed):
        Clock.schedule_once(lambda *_: self._apply_result(key, result, elapsed), 0)

    def _post_status(self, text):
        Clock.schedule_once(lambda *_: setattr(self.progress, "text", text), 0)

    def _apply_result(self, key, result, elapsed):
        # Для remove_bg результат — RGBA
        if key == "remove_bg" and result.ndim == 3 and result.shape[2] == 4:
            self.current = result[:, :, :3]  # для превью показываем RGB
            rgba = result
            ts = time.strftime("%Y%m%d_%H%M%S")
            out = os.path.join(self.storage.output_dir, f"nobg_{ts}.png")
            iu.save_image(rgba, out)
            self.progress.text = f"Фон удалён · {elapsed:.1f}с (RGBA сохранён)"
        else:
            self.current = result
            self._refresh_preview()
            self.progress.text = f"{key} готово · {elapsed:.1f}с"
        self._refresh_models_status()

    # ---------- Экспорт ----------

    def _export(self):
        if self.current is None:
            self.progress.text = "Нечего сохранять"
            return
        ts = time.strftime("%Y%m%d_%H%M%S")
        out = os.path.join(self.storage.output_dir, f"ai_{ts}.png")
        if iu.save_image(self.current, out):
            self.storage.save_result("ai", "editor", self.current, iu.save_image)
            ok = save_to_gallery(out, "image/png")
            self.progress.text = (
                "✅ Сохранено в галерею" if ok
                else "Сохранено в приложение"
            )
        else:
            self.progress.text = "Ошибка сохранения"