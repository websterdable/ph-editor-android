[app]
title = PhotoAI
package.name = photoai
package.domain = org.local

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,onnx,ttf,java,data
source.exclude_dirs = .git,.github,venv,venv-photoai,__pycache__,.buildozer,bin,tools,p4a-recipes

version = 0.5.0

requirements = python3==3.10.11,kivy==2.2.1,pyjnius

p4a.branch = v2023.09.16

orientation = all
fullscreen = 1
icon.filename = %(source.dir)s/assets/icons/icon.png

android.api = 33
android.minapi = 24
android.ndk = 25b
android.ndk_api = 24
android.accept_sdk_license = True
android.archs = arm64-v8a

# ONNX Runtime для Android
android.gradle_dependencies = com.microsoft.onnxruntime:onnxruntime-android:1.22.0
# Увеличенный heap для сборки (заменяем gradle_max_heap_size)
android.gradle_properties = org.gradle.jvmargs=-Xmx6g -XX:MaxMetaspaceSize=1g

# Java-исходники
android.add_src = java

android.permissions = READ_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,WRITE_EXTERNAL_STORAGE
android.private_storage = True
android.allow_backup = False

[buildozer]
log_level = 2
