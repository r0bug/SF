# Building Song Factory

Song Factory can be built as a standalone executable for Linux, macOS, and Windows using PyInstaller.

## Prerequisites

- Python 3.10+
- pip
- All runtime dependencies: `pip install -r requirements.txt`
- Build tools: `pip install pyinstaller cairosvg` (cairosvg is needed for icon conversion)

## Quick Build

### Linux

```bash
./scripts/build_linux.sh
```

Output: `dist/SongFactory/SongFactory` (executable directory)

If `appimagetool` is installed, also creates `dist/SongFactory-x86_64.AppImage`.

### macOS

```bash
./scripts/build_macos.sh
```

Output: `dist/SongFactory.app` and `dist/SongFactory.dmg`

**Code signing note:** Unsigned apps will be blocked by Gatekeeper. Users can bypass with:
```bash
xattr -d com.apple.quarantine /path/to/SongFactory.app
```

### Windows

```batch
scripts\build_windows.bat
```

Output: `dist\SongFactory\SongFactory.exe`

For a proper installer, use [NSIS](https://nsis.sourceforge.io/) or [Inno Setup](https://jrsoftware.org/isinfo.php) to package the `dist\SongFactory\` directory.

## Manual Build

```bash
# 1. Generate platform icons
python3 scripts/convert_icons.py

# 2. Run PyInstaller
pyinstaller songfactory.spec --clean
```

## Development Install

For development without packaging:

```bash
pip install -e .
songfactory  # runs via entry point
```

Or directly:
```bash
python songfactory/main.py
```

## Playwright Browsers

Playwright browsers (Chromium) are **not** bundled in the executable — they are too large (~400 MB). On first launch, if browser automation is used, the app will prompt the user to install them:

```bash
python -m playwright install chromium
```

## Output Structure

```
dist/SongFactory/
├── SongFactory          # Main executable
├── icon.svg             # App icon
├── icon.ico             # Windows icon
├── _internal/           # PyInstaller runtime files
│   ├── PyQt6/
│   ├── ...
```

## CI/CD

Example GitHub Actions workflow for multi-platform builds:

```yaml
name: Build
on: [push, workflow_dispatch]

jobs:
  build:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt pyinstaller cairosvg
      - run: python scripts/convert_icons.py
      - run: pyinstaller songfactory.spec --clean
      - uses: actions/upload-artifact@v4
        with:
          name: SongFactory-${{ matrix.os }}
          path: dist/SongFactory/
```
