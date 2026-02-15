#!/bin/bash
# Build Song Factory for Linux
# Produces: dist/SongFactory/ (directory) and optionally an AppImage
set -e

cd "$(dirname "$0")/.."

echo "=== Song Factory Linux Build ==="

# Install build dependencies
pip install pyinstaller

# Generate icons
python3 scripts/convert_icons.py

# Build with PyInstaller
pyinstaller songfactory.spec --clean

echo ""
echo "Build complete: dist/SongFactory/"
echo "Run with: ./dist/SongFactory/SongFactory"

# Optional: Create AppImage if appimagetool is available
if command -v appimagetool &> /dev/null; then
    echo ""
    echo "Creating AppImage..."
    APPDIR="SongFactory.AppDir"
    rm -rf "$APPDIR"
    mkdir -p "$APPDIR/usr/bin"
    cp -r dist/SongFactory/* "$APPDIR/usr/bin/"

    # Desktop entry
    cat > "$APPDIR/songfactory.desktop" << 'DESKTOP'
[Desktop Entry]
Name=Song Factory
Exec=SongFactory
Icon=songfactory
Type=Application
Categories=Audio;Music;
DESKTOP

    # AppRun
    ln -sf usr/bin/SongFactory "$APPDIR/AppRun"

    # Icon
    cp songfactory/icon.svg "$APPDIR/songfactory.svg"

    ARCH=$(uname -m) appimagetool "$APPDIR" "dist/SongFactory-$(uname -m).AppImage"
    rm -rf "$APPDIR"
    echo "AppImage created: dist/SongFactory-$(uname -m).AppImage"
else
    echo ""
    echo "Note: Install appimagetool to create an AppImage."
    echo "  https://github.com/AppImage/AppImageKit/releases"
fi
