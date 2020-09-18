# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['run.py'],
             pathex=['.'],
             binaries=[],
             datas=[('res\\logo.ico', '.'),
                    ('res\\logo-title.png', '.'),
                    ('res\\logo-full.png', '.')],
             hiddenimports=['pkg_resources.py2_warn', 'pystray._win32', "pillow._imaging"],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='FOV-Changer',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
		  icon="res\\logo.ico",
		  version="file_version_info.txt")
