@echo off
pyinstaller --onefile --windowed --name "SCS_File_Updater" ^
    --icon=icon.ico ^
    --add-data "README.md;." ^
    main.py
echo.
echo Build complete. Executable is in dist\SCS_File_Updater.exe
pause
