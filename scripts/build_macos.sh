#!/bin/bash
# Build Song Factory for macOS
# Produces: dist/SongFactory.app and dist/SongFactory.dmg
set -e

cd "$(dirname "$0")/.."

echo "=== Song Factory macOS Build ==="

# Install build dependencies
pip install pyinstaller

# Generate icons
python3 scripts/convert_icons.py

# Build with PyInstaller
pyinstaller songfactory.spec --clean

echo ""
echo "Build complete: dist/SongFactory.app"

# Create DMG
echo "Creating DMG..."
hdiutil create \
    -volname "Song Factory" \
    -srcfolder dist/SongFactory.app \
    -ov -format UDZO \
    dist/SongFactory.dmg

echo "DMG created: dist/SongFactory.dmg"
echo ""
echo "Note: Users may need to run the following to bypass Gatekeeper:"
echo "  xattr -d com.apple.quarantine /path/to/SongFactory.app"
