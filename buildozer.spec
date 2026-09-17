[app]
title = PhotoAI
package.name = photoai
package.domain = org.local

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,onnx
source.exclude_dirs = .git,.github,venv,venv-photoai,__pycache__,.buildozer,bin,tools

version = 0.3.0

requirements = python3,kivy,numpy,pillow,plyer,pyjnius

p4a.branch = develop

orientation = all

icon.filename = %(source.dir)s/assets/icons/icon.png

android.api = 36
android.minapi = 24
android.ndk = 29
android.ndk_api = 24
android.accept_sdk_license = True

android.archs = arm64-v8a

# Для экспорта в галерею на Android ≤ 12
android.permissions = READ_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,WRITE_EXTERNAL_STORAGE
android.private_storage = True
android.allow_backup = False

[buildozer]
log_level = 2
