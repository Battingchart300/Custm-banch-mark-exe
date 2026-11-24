@echo off
chcp 65001 >nul
echo PTS Benchmark v0.4 - build .exe (Windows 10/11)
echo.
python --version
python -m pip install --upgrade pyinstaller psutil
python -m PyInstaller --onefile --noconsole --name "PTS-Benchmark" --version-file version_info.txt main.py
echo.
echo Hotovo: dist\PTS-Benchmark.exe
pause
