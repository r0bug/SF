@echo off
REM Build Song Factory for Windows
REM Produces: dist\SongFactory\SongFactory.exe

cd /d "%~dp0\.."

echo === Song Factory Windows Build ===

REM Install build dependencies
pip install pyinstaller

REM Generate icons
python scripts\convert_icons.py

REM Build with PyInstaller
pyinstaller songfactory.spec --clean

echo.
echo Build complete: dist\SongFactory\SongFactory.exe
echo.
echo Optional: Use NSIS or Inno Setup to create an installer.
