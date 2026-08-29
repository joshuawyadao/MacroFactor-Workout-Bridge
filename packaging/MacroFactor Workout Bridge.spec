from pathlib import Path


project_root = Path(SPECPATH).parent
icon_path = project_root / "build" / "MacroFactor Workout Bridge.icns"

analysis = Analysis(
    [str(project_root / "packaging" / "app_entry.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[(str(project_root / "config" / "exercises.example.json"), "config")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="MacroFactor Workout Bridge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
)
collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MacroFactor Workout Bridge",
)
app = BUNDLE(
    collection,
    name="MacroFactor Workout Bridge.app",
    icon=str(icon_path),
    bundle_identifier="com.joshuawyadao.macrofactor-workout-bridge",
    info_plist={
        "CFBundleDisplayName": "MacroFactor Workout Bridge",
        "CFBundleShortVersionString": "0.2.1",
        "CFBundleVersion": "3",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "Copyright © 2026 Joshua Wyadao",
    },
)
