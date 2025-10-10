# -*- mode: python ; coding: utf-8 -*-
agent_analysis = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('config_agente.json', '.'), ('scan', 'scan'), ('agent.ico', '.')],
    hiddenimports=['win32api', 'win32com', 'win32con', 'win32gui', 'win32process', 'keyring.backends.Windows', 'requests', 'psutil'],
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=['runtime_hook.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
agent_pyz = PYZ(agent_analysis.pure)
agent_exe = EXE(
    agent_pyz,
    agent_analysis.scripts,
    [],
    exclude_binaries=True,
    name='ScanAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon='agent.ico'
)
agent_coll = COLLECT(
    agent_exe,
    agent_analysis.binaries,
    agent_analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ScanAgent'
)
uninstaller_analysis = Analysis(
    ['uninstaller.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['psutil', 'winreg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
uninstaller_pyz = PYZ(uninstaller_analysis.pure)
uninstaller_exe = EXE(
    uninstaller_pyz,
    uninstaller_analysis.scripts,
    [],
    exclude_binaries=True,
    name='Uninstall',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon='agent.ico'
)
uninstaller_coll = COLLECT(
    uninstaller_exe,
    uninstaller_analysis.binaries,
    uninstaller_analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Uninstall'
)