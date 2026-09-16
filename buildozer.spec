[app]
title = PhotoAI
package.name = photoai
package.domain = org.local
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,onnx
source.exclude_dirs = .git,.github,venv,__pycache__
version = 0.1.0

requirements = python3,kivy,kivymd,numpy,pillow
android.gradle_dependencies = com.microsoft.onnxruntime:onnxruntime-android:1.22.0
android.api = 33
android.minapi = 26
android.archs = arm64-v8a
android.permissions = READ_MEDIA_IMAGES
android.private_storage = True
android.allow_backup = False
android.accept_sdk_license = True
android.build_tools_version = 33.0.0

[buildozer]
log_level = 2
