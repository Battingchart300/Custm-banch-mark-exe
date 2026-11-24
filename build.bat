@echo off
chcp 65001 >nul
echo PTS Benchmark v0.3 - build .exe (Windows 10/11)
echo.
python --version
python -m pip install --upgrade pyinstaller psutil
python -m PyInstaller --onefile --noconsole --name "PTS-Benchmark" main.py
echo.
echo Hotovo: dist\PTS-Benchmark.exe
pause
