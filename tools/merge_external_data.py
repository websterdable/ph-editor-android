"""Сливает .onnx + .data в один .onnx файл (external data -> embedded).

Использование:
    python tools/merge_external_data.py <in.onnx> <out.onnx>
"""
import sys
from pathlib import Path

try:
    import onnx
    from onnx.external_data_helper import load_external_data_for_model
except ImportError:
    print("Установите: pip install onnx")
    sys.exit(1)


def merge(src_path, dst_path):
    src = Path(src_path)
    dst = Path(dst_path)
    if not src.exists():
        print(f"✗ Файл не найден: {src}")
        sys.exit(1)

    print(f"▶ Читаю {src}")
    model = onnx.load(str(src), load_external_data=False)

    # Загружаем внешние веса из .data
    print(f"▶ Загружаю external data из {src.parent}")
    load_external_data_for_model(model, src.parent.as_posix())

    # Проверяем модель
    print("▶ Проверяю модель…")
    onnx.checker.check_model(model)

    # Сохраняем со встроенными весами
    print(f"▶ Сохраняю {dst}")
    onnx.save(model, str(dst), save_as_external_data=False)

    size_mb = dst.stat().st_size / 1024 / 1024
    print(f"✓ Готово: {size_mb:.1f} МБ")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Использование: python tools/merge_external_data.py <in.onnx> <out.onnx>")
        sys.exit(1)
    merge(sys.argv[1], sys.argv[2])