[app]
title = PhotoAI
package.name = photoai
package.domain = org.local

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,onnx
source.exclude_dirs = .git,.github,venv,venv-photoai,__pycache__,.buildozer,bin,tools

version = 0.4.0

# NumPy 1.26.4 — первая версия с официальной поддержкой Python 3.11
requirements = python3,kivy,numpy==1.26.4

# Указываем на предварительно собранный wheel для Android arm64-v8a + Python 3.11
requirements.source.numpy = https://anaconda.org/channels/buildozer/packages/numpy/files/numpy-1.26.4-0-cp311-cp311-android_24_arm64_v8a.whl

p4a.branch = master

orientation = all
icon.filename = %(source.dir)s/assets/icons/icon.png

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
