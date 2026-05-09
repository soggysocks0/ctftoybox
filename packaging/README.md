# Packaging CTFToyBox

This folder contains everything needed to turn the source tree into
distributable executables and installers.

## What gets built

| Platform         | Output                                        | How users install |
|------------------|-----------------------------------------------|-------------------|
| Windows 10 / 11  | `dist\CTFToyBox.exe`                          | Just double-click. |
| Debian / Ubuntu  | `dist/ctftoybox_<version>_amd64.deb`          | `sudo apt install ./ctftoybox_*.deb` |
| Other Linux      | `dist/CTFToyBox` (standalone binary)          | `chmod +x CTFToyBox && ./CTFToyBox` |

You **must build on the same OS as the target**. A Windows `.exe` has to
be built on Windows; a Linux binary has to be built on Linux. PyInstaller
does not cross-compile.

---

## Windows build

### 1. Prerequisites

- Python 3.10 or newer (3.11 / 3.12 / 3.14 all work)
- The project's runtime dependencies installed (build script does this)

### 2. Build

From the project root in PowerShell:

packaging\build-windows.bat

### 3. Distribute

Single file: `dist\CTFToyBox.exe`. Share it however you like (GitHub
Releases, a download link, USB stick).

Users double-click `CTFToyBox.exe` to run. No Python install required.

**Smart Screen warning:** On first launch, Windows may show a "Windows
protected your PC" dialog because the binary isn't code-signed. Users
click "More info" → "Run anyway". This is normal for unsigned indie
software; getting rid of it requires buying a code-signing certificate.

---

## Linux build

### 1. Prerequisites

- Python 3.10 or newer
- The project's runtime deps (build script handles this)
- `dpkg-deb` if you want the `.deb` package (skippable):
  ```
  sudo apt-get install dpkg
  ```

### 2. Build

From the project root:

```bash
./packaging/build-linux.sh
```

Override the version baked into the `.deb` if you want:

```bash
VERSION=0.1.1 ./packaging/build-linux.sh
```

### 3. Distribute

Two artifacts get produced in `dist/`:

- **`CTFToyBox`** — standalone binary. Works on most modern Linux distros
  out of the box (Ubuntu, Fedora, Arch, etc.) as long as the user's
  glibc isn't older than the build host's. Users `chmod +x` and run.
- **`ctftoybox_0.1.0_amd64.deb`** — Debian package for Ubuntu/Debian/
  Mint/Pop!_OS/etc. Installs `/opt/ctftoybox/CTFToyBox`, a `ctftoybox`
  command on `PATH`, and an entry in the app launcher.

### 4. How users install

**Debian-based distros (the easy path):**

```bash
sudo apt install ./ctftoybox_0.1.0_amd64.deb
```

Then launch from the app menu, or run `ctftoybox` from a terminal.

To uninstall:

```bash
sudo apt remove ctftoybox
```

**Other Linux distros (Fedora, Arch, openSUSE, etc.):**

```bash
chmod +x CTFToyBox
./CTFToyBox
```

That's it — the binary is fully self-contained.

### 5. Notes for users

- **Docker required for challenge deployment.** Without Docker the app
  starts fine, but Run/Stop on the Instances page will pop a "Docker
  not available" dialog. The `.deb` postinst hints at this.
- Generated artifacts live in `~/.ctf_manager/`, just like in the
  source-run version. (See the project rename note in the main README
  if/when this path changes.)

---

## Tweaks you might want

- **Add an icon.** Drop a `.ico` (Windows) or `.png` (Linux) into
  `packaging/`, then in `ctftoybox.spec` change the `EXE(...)` block to
  pass `icon='packaging/icon.ico'`. Rebuild.
- **Code-sign the Windows exe.** Requires a code-signing certificate.
  Add `signtool sign /f cert.pfx /p PASSWORD dist\CTFToyBox.exe` to
  `build-windows.ps1` after the PyInstaller step.
- **Bump version.** Edit the `VERSION` default in `build-linux.sh`.
  Also update the version string shown in `ui/sidebar.py` (`v0.1.0`
  label at the bottom of the sidebar).

---

## Troubleshooting

**"Permission denied" running `./packaging/build-linux.sh`** — Run
`chmod +x packaging/build-linux.sh` once. Some download tools strip the
exec bit.

**Build succeeds but the app crashes immediately on launch** — Run from
a terminal so you can see the traceback. On Windows, change `console=False`
to `console=True` in `ctftoybox.spec` and rebuild; you'll get a console
window with the error. Switch back to `False` once you've fixed it.

**"ModuleNotFoundError: No module named 'generators.X'"** — The dispatch
tables in `generators/dispatch.py` and
`system_templates/dispatch.py` import generators dynamically; if you add
a new one, also add it to the `hiddenimports` list in `ctftoybox.spec`
so PyInstaller bundles it.

**The `.exe` is huge (~150 MB).** That's PyQt6 — Qt's libraries are big.
You can shave 20-30 MB by adding `--exclude-module` for things you
don't need (already in the spec for tkinter / matplotlib / numpy).
Don't try to exclude any `PyQt6.*` submodule unless you're sure — Qt is
finicky about which pieces are loaded together.