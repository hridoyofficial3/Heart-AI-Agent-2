[app]
title = Dipanwita Bot
package.name = dipanwita
package.domain = org.heart
source.dir = .
source.include_exts = py,json,html
version = 1.0
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,requests,urllib3,chardet,idna,certifi,pypdf,charset-normalizer
orientation = portrait
fullscreen = 0
services = Bot:service.py:foreground:sticky
android.permissions = INTERNET,FOREGROUND_SERVICE,WAKE_LOCK,POST_NOTIFICATIONS,REQUEST_IGNORE_BATTERY_OPTIMIZATIONS
android.api = 33
android.ndk = 25b
android.ndk_api = 24
p4a.branch = v2024.01.21
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.extra_manifest_application_arguments = ./app_args.xml

[buildozer]
log_level = 2
warn_on_root = 1
