@echo off
echo.
echo === SCS File Updater - Clean & Reliable Build Script ===
echo.

:: Ensure pip is up to date
python -m pip install --upgrade pip --quiet

:: Install exact working versions (prevents PyQt6 issues)
python -m pip install PyQt6==6.6.1 rarfile patool pyinstaller --quiet

:: Clean previous builds
rmdir /s /q build dist __pycache__ 2>nul
del SCS_File_Updater.spec 2>nul

:: Build with explicit hidden imports to force PyQt6 inclusion
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "SCS_File_Updater" ^
    --icon=icon.ico ^
    --add-data "README.md;." ^
    --hidden-import PyQt6 ^
    --hidden-import PyQt6.QtCore ^
    --hidden-import PyQt6.QtGui ^
    --hidden-import PyQt6.QtWidgets ^
    main.py

echo.
echo =================================================
echo Build completed successfully!
echo Your executable is ready: dist\SCS_File_Updater.exe
echo =================================================
pause
