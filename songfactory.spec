# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Song Factory — Yakima Finds.

Build with:  pyinstaller songfactory.spec --clean
"""

import sys

# Platform-specific icon
icon_file = {
    'win32': 'songfactory/icon.ico',
    'darwin': 'songfactory/icon.icns',
}.get(sys.platform, 'songfactory/icon.svg')

a = Analysis(
    ['songfactory/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('songfactory/icon.svg', '.'),
        ('songfactory/icon.ico', '.'),
    ],
    hiddenimports=[
        'PyQt6.sip',
        'keyring.backends',
        'sqlite3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'playwright',   # Installed on first launch by user
        'tkinter',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SongFactory',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=[icon_file],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SongFactory',
)

# macOS .app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='SongFactory.app',
        icon='songfactory/icon.icns',
        bundle_identifier='com.yakimafinds.songfactory',
        info_plist={
            'CFBundleShortVersionString': '2.2.0',
            'NSHighResolutionCapable': True,
        },
    )
