[app]
title = Heart AI
package.name = heartai
package.domain = org.heart
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,html,xml,txt
version = 1.0.0
requirements = python3,kivy==2.2.1,requests,urllib3,pypdf,certifi,openssl
orientation = portrait
fullscreen = 0
android.presplash_color = #121214
android.permissions = INTERNET,POST_NOTIFICATIONS,READ_EXTERNAL_STORAGE,READ_MEDIA_IMAGES
android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.extra_manifest_xml = ./app_args.xml
android.archs = arm64-v8a, armeabi-v7a
services = Bot:service.py

[buildozer]
log_level = 2
warn_on_root = 1
