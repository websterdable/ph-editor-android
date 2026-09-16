[app]
title = PhotoAI
package.name = photoai
package.domain = org.local

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,onnx
source.exclude_dirs = .git,.github,venv,venv-photoai,__pycache__,.buildozer,bin

version = 0.1.0

# Без KivyMD, чтобы изолировать проблему сборки
requirements = python3,kivy

# Ветка python-for-android с фиксами для Python 3.11 и NumPy
p4a.branch = develop

# ONNX Runtime для Android (подключим позже, когда база соберётся)
# android.gradle_dependencies = com.microsoft.onnxruntime:onnxruntime-android:1.22.0

# Android SDK/API
android.api = 36
android.minapi = 24
android.ndk = 29
android.ndk_api = 24
android.accept_sdk_license = True

# Архитектура
android.archs = arm64-v8a

# Разрешения и приватность
android.permissions = READ_MEDIA_IMAGES
android.private_storage = True
android.allow_backup = False

[buildozer]
log_level = 2
