# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['run.py'],
             pathex=['C:\\Users\\xroix\\Desktop\\Coding\\Programming\\Python\\Other\\FOV-Changer'],
             binaries=[],
             datas=[('C:\\Users\\xroix\\Desktop\\Coding\\Programming\\Python\\Other\\FOV-Changer\\logo.ico', '.'),
                    ('C:\\Users\\xroix\\Desktop\\Coding\\Programming\\Python\\Other\\FOV-Changer\\res\\logo-title.png', '.'),
                    ('C:\\Users\\xroix\\Desktop\\Coding\\Programming\\Python\\Other\\FOV-Changer\\res\\logo-full.png', '.')],
             hiddenimports=['pkg_resources.py2_warn', 'pystray._win32'],
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
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
		  icon="logo.ico")
