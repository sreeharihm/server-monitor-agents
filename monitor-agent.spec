# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['dashboard.server', 'agents.cloudwatch_agent.server', 'agents.prometheus_agent.server']
hiddenimports += collect_submodules('dashboard')
hiddenimports += collect_submodules('agents')


a = Analysis(
    ['run_all.py'],
    pathex=[],
    binaries=[],
    datas=[('dashboard/static', 'dashboard/static'), ('config.yaml', '.')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='monitor-agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
