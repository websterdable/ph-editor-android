[app]
title = PhotoAI
package.name = photoai
package.domain = org.local

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,onnx
source.exclude_dirs = .git,.github,venv,venv-photoai,__pycache__,.buildozer,bin

version = 0.1.0

# Требования: пока без KivyMD, чтобы изолировать ошибку
requirements = python3,kivy,numpy,pillow

# Используем develop-ветку python-for-android (там свежие фиксы)
p4a.branch = develop

# ONNX Runtime для Android подключается как Gradle-зависимость
android.gradle_dependencies = com.microsoft.onnxruntime:onnxruntime-android:1.22.0

# Android SDK/API
android.api = 33
android.minapi = 26
android.build_tools_version = 33.0.0
android.accept_sdk_license = True

# Архитектура
android.archs = arm64-v8a

# Разрешения и приватность
android.permissions = READ_MEDIA_IMAGES
android.private_storage = True
android.allow_backup = False

[buildozer]
log_level = 2
