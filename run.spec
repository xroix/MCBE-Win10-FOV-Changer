# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['run.py'],
    pathex=['.'],
    binaries=[],
    datas=[('res\\logo.ico', '.'),
           ('res\\logo-title.png', '.'),
           ('res\\logo-full.png', '.')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(
    a.pure, a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FOV-Changer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False, # Note that upx must be installed or else it will be ignored
    upx_exclude=[],
    runtime_tmpdir=None,
    uac_admin=True,
    console=False,
    icon="res\\logo.ico",
    version="file_version_info.txt"
)
