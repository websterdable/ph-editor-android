[app]
title = PhotoAI
package.name = photoai
package.domain = org.local

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,onnx
source.exclude_dirs = .git,.github,venv,venv-photoai,__pycache__,.buildozer,bin

version = 0.2.0
android.numeric_version = 2

requirements = python3,kivy,numpy,plyer

p4a.branch = develop

orientation = all

android.api = 36
android.minapi = 24
android.ndk = 29
android.ndk_api = 24
android.accept_sdk_license = True

android.archs = arm64-v8a

android.permissions = READ_EXTERNAL_STORAGE,READ_MEDIA_IMAGES
android.private_storage = True
android.allow_backup = False

[buildozer]
log_level = 2
