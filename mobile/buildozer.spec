[app]
title = Pensiero Magico
package.name = pensieromagico
package.domain = it.gmago2703
source.dir = .
source.include_exts = py,png,json
source.exclude_patterns = prova_grafica.py
source.exclude_dirs = bin, .buildozer, foto_android, __pycache__, firma
version.regex = __version__ = "(.*)"
version.filename = %(source.dir)s/pmse/__init__.py
requirements = python3,kivy==2.3.1,numpy,sqlite3,openssl,certifi,charset_normalizer==3.3.2
icon.filename = %(source.dir)s/pmse/icona.png
presplash.color = #00653B
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.api = 34
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True
android.release_artifact = apk
android.debug_artifact = apk

[buildozer]
log_level = 2
warn_on_root = 0
