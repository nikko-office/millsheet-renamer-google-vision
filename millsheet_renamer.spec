# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Millsheet Renamer
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect tkinterdnd2 data files
tkdnd_datas = collect_data_files('tkinterdnd2')

# Collect customtkinter data files
ctk_datas = collect_data_files('customtkinter')

# Collect google cloud vision dependencies
google_datas = collect_data_files('google.cloud.vision')
grpc_datas = collect_data_files('grpc')

# Hidden imports for google cloud
hidden_imports = [
    'google.cloud.vision',
    'google.cloud.vision_v1',
    'google.api_core',
    'google.auth',
    'google.auth.transport.requests',
    'google.protobuf',
    'grpc',
    'grpc._cython',
    'tkinterdnd2',
    'customtkinter',
]

# Add all google submodules
hidden_imports += collect_submodules('google')
hidden_imports += collect_submodules('grpc')

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=tkdnd_datas + ctk_datas + google_datas + grpc_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MillsheetRenamer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MillsheetRenamer',
)
