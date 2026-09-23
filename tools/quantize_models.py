"""Квантизация ONNX-моделей в INT8. Запускать в WSL, не на Android.

Использование:
    python tools/quantize_models.py
Результат:
    assets/models/*_int8.onnx
"""
import os
import sys
from pathlib import Path

try:
    from onnxruntime.quantization import quantize_dynamic, QuantType
except ImportError:
    print("Установите: pip install onnx onnxruntime")
    sys.exit(1)


MODELS_DIR = Path("assets/models")

# Модели для квантизации: (входной файл, выходной файл)
TARGETS = [
    ("realesrgan_x4.onnx", "realesrgan_x4_int8.onnx"),
    ("modnet.onnx",        "modnet_int8.onnx"),
    ("yunet.onnx",         "yunet_int8.onnx"),
    # Добавим позже, когда скачаем:
    # ("gfpgan.onnx",       "gfpgan_int8.onnx"),
    # ("ddcolor.onnx",      "ddcolor_int8.onnx"),
]


def main():
    for src_name, dst_name in TARGETS:
        src = MODELS_DIR / src_name
        dst = MODELS_DIR / dst_name
        if not src.exists():
            print(f"⚠  Пропуск: {src} не найден")
            continue
        if dst.exists():
            print(f"✓ Уже есть: {dst}")
            continue

        size_mb = src.stat().st_size / 1024 / 1024
        print(f"\n▶ Квантизуем {src_name} ({size_mb:.1f} МБ) → {dst_name}")
        try:
            quantize_dynamic(
                model_input=str(src),
                model_output=str(dst),
                weight_type=QuantType.QUInt8,
            )
            out_mb = dst.stat().st_size / 1024 / 1024
            ratio = size_mb / out_mb if out_mb > 0 else 0
            print(f"✓ Готово: {out_mb:.1f} МБ (сжатие в {ratio:.1f}x)")
        except Exception as e:
            print(f"✗ Ошибка: {e}")


if __name__ == "__main__":
    main()