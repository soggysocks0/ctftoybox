# PyInstaller spec for CTFToyBox.
# Cross-platform: produces a single-file exe on Windows and a single-file
# binary on Linux. macOS isn't covered here but works the same way.
#
# Build with:    pyinstaller packaging/ctftoybox.spec --clean --noconfirm

# -*- mode: python ; coding: utf-8 -*-
import os
import sys

# Resolve the project root regardless of where pyinstaller is invoked from.
PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(SPEC)))


# --------------------------------------------------------------------------
# Files we ship alongside the Python code.
# Format: (source_path_on_disk, dest_path_inside_bundle)
# Inside the bundle, paths are relative to sys._MEIPASS at runtime.
# --------------------------------------------------------------------------
datas = [
    (os.path.join(PROJECT_ROOT, "ui", "themes"),     os.path.join("ui", "themes")),
    (os.path.join(PROJECT_ROOT, "ui", "resources"),  os.path.join("ui", "resources")),
    (os.path.join(PROJECT_ROOT, "addon_templates"),  "addon_templates"),
]


# --------------------------------------------------------------------------
# Hidden imports — modules PyInstaller's static analysis won't pick up
# because we route through dispatch tables / dynamic imports.
# --------------------------------------------------------------------------
hiddenimports = [
    # Generators are dispatched by category in dispatch.py; PyInstaller
    # may miss them.
    "generators.reverse_engineering",
    "generators.binary_exploitation",
    "generators.web_exploitation",
    "generators.forensics",
    "generators.custom",
    # System-template generators have the same dispatch-table pattern.
    "system_templates.generators.windows",
    "system_templates.generators.linux",
]


a = Analysis(
    [os.path.join(PROJECT_ROOT, "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Dropping these shaves a noticeable chunk off the bundle and we don't
    # use any of them.
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "PIL",
        "PySide6",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)


# Pick a friendly icon if we ever ship one. For now no --icon.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CTFToyBox",
    icon=os.path.join(PROJECT_ROOT, "packaging", "icon.ico"),  # NEW
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)