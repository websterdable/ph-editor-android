[app]
title = PhotoAI
package.name = photoai
package.domain = org.local

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,onnx
source.exclude_dirs = .git,.github,venv,venv-photoai,__pycache__,.buildozer,bin,tools

version = 0.4.0

# NumPy 1.24.4 совместим с Python 3.11 и стабильно собирается
requirements = python3,kivy,numpy==1.24.4

# Стабильная ветка p4a, проверенная на совместимость с NumPy
p4a.branch = master

orientation = all
icon.filename = %(source.dir)s/assets/icons/icon.png

# Проверенная связка NDK/API для сборки NumPy
android.api = 33
android.minapi = 24
android.ndk = 25c
android.ndk_api = 24
android.accept_sdk_license = True
android.archs = arm64-v8a

android.permissions = READ_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,WRITE_EXTERNAL_STORAGE
android.private_storage = True
android.allow_backup = False

[buildozer]
log_level = 2
