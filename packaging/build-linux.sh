#!/usr/bin/env bash
# Builds CTFToyBox for Linux.
#
# Two outputs:
#   1. dist/CTFToyBox                 — standalone binary, runs anywhere
#                                       with glibc >= the build host's
#   2. dist/ctftoybox_<version>_amd64.deb  — Debian package (Ubuntu, Debian,
#                                            Linux Mint, Pop!_OS, etc.)
#
# Usage (from project root):
#     ./packaging/build-linux.sh

set -euo pipefail

VERSION="${VERSION:-0.1.0}"

# Move to project root regardless of where script is invoked from
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "==> Project root: $PROJECT_DIR"
echo "==> Version:      $VERSION"

# ----------------------------------------------------------------------
# 1. Build the standalone binary with PyInstaller
# ----------------------------------------------------------------------
echo "==> Installing build dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m pip install pyinstaller

echo "==> Cleaning previous build artifacts..."
rm -rf build dist

echo "==> Running PyInstaller..."
pyinstaller packaging/ctftoybox.spec --clean --noconfirm

BIN="$PROJECT_DIR/dist/CTFToyBox"
if [[ ! -f "$BIN" ]]; then
    echo "==> Build did not produce dist/CTFToyBox — see PyInstaller output above." >&2
    exit 1
fi
chmod +x "$BIN"
SIZE=$(du -h "$BIN" | cut -f1)
echo "==> Binary built: $BIN  ($SIZE)"

# ----------------------------------------------------------------------
# 2. Wrap the binary in a .deb package
# ----------------------------------------------------------------------
if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo
    echo "==> Skipping .deb build (dpkg-deb not installed)."
    echo "    Install with:  sudo apt-get install dpkg"
    echo "    The standalone binary at dist/CTFToyBox is still ready to ship."
    exit 0
fi

echo
echo "==> Building .deb package..."

DEB_ROOT="$PROJECT_DIR/build/deb-root"
rm -rf "$DEB_ROOT"

# Standard FHS layout inside the .deb:
#   /usr/bin/CTFToyBox                 -> our binary (symlinked)
#   /opt/ctftoybox/CTFToyBox           -> the actual binary
#   /usr/share/applications/...        -> .desktop entry for app menu
mkdir -p "$DEB_ROOT/DEBIAN"
mkdir -p "$DEB_ROOT/opt/ctftoybox"
mkdir -p "$DEB_ROOT/usr/bin"
mkdir -p "$DEB_ROOT/usr/share/applications"
mkdir -p "$DEB_ROOT/usr/share/icons/hicolor/512x512/apps" 

cp "$BIN" "$DEB_ROOT/opt/ctftoybox/CTFToyBox"
chmod 0755 "$DEB_ROOT/opt/ctftoybox/CTFToyBox"

cp "$PROJECT_DIR/packaging/icon.png" \
   "$DEB_ROOT/usr/share/icons/hicolor/512x512/apps/ctftoybox.png"
chmod 0644 "$DEB_ROOT/usr/share/icons/hicolor/512x512/apps/ctftoybox.png"

# /usr/bin shim — keeps the package's payload under /opt and gives users a
# command on PATH.
ln -sf /opt/ctftoybox/CTFToyBox "$DEB_ROOT/usr/bin/ctftoybox"

# Desktop entry so it shows up in the app launcher
cat > "$DEB_ROOT/usr/share/applications/ctftoybox.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=CTFToyBox
Comment=Deploy and manage CTF challenge instances
Exec=/opt/ctftoybox/CTFToyBox
Icon=ctftoybox
Terminal=false
Categories=Development;Education;Security;
EOF
chmod 0644 "$DEB_ROOT/usr/share/applications/ctftoybox.desktop"

# Package metadata
cat > "$DEB_ROOT/DEBIAN/control" <<EOF
Package: ctftoybox
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Maintainer: soggysocks0 <soggysocks0@users.noreply.github.com>
Description: CTFToyBox — CTF challenge instance manager
 A desktop application for deploying and managing CTF-style
 challenge instances (Reverse Engineering, Binary Exploitation,
 Web Exploitation, Forensics, plus user-supplied custom challenges)
 via Docker, and for generating vulnerable system-template scripts
 for pentest practice.
 .
 Note: Docker must be installed and running for challenge deployment
 functionality to work. Without Docker, the application still runs
 and can generate scripts; only the Run/Stop actions need it.
Homepage: https://github.com/soggysocks0
EOF

# Optional: post-install hint about Docker
cat > "$DEB_ROOT/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if ! command -v docker >/dev/null 2>&1; then
    echo "Note: Docker is not installed. Install Docker to enable container-based challenge deployment."
    echo "      See https://docs.docker.com/engine/install/"
fi
exit 0
EOF
chmod 0755 "$DEB_ROOT/DEBIAN/postinst"

DEB_NAME="ctftoybox_${VERSION}_amd64.deb"
dpkg-deb --build --root-owner-group "$DEB_ROOT" "$PROJECT_DIR/dist/$DEB_NAME"

echo
echo "==> SUCCESS."
echo "    Binary:   dist/CTFToyBox"
echo "    Package:  dist/$DEB_NAME"
echo
echo "Users can install with:  sudo apt install ./dist/$DEB_NAME"
echo "Or run the binary directly without installing."