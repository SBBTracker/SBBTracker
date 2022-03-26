# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
import glob

block_cipher = None

hidden_battlesim = collect_submodules('sbbbattlesim')
hidden_tracker = [ file[2:].replace("/", ".").replace("\\", ".").replace(".py", "") for file in glob.glob("./sbbtracker/lang/lang_*.py") ]

print(collect_submodules('./sbbtracker/lang/'))
a = Analysis(['sbbtracker/application.py'],
             pathex=[],
             binaries=[],
             datas=[],
             hiddenimports=hidden_battlesim+hidden_tracker,
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
a.datas += [('assets/sbbt.ico', 'assets/sbbt.ico', 'DATA')]
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts, 
          [],
          exclude_binaries=True,
          name='SBBTracker',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None , icon='assets/sbbt.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas, 
               strip=False,
               upx=True,
               upx_exclude=[],
               name='SBBTracker')
