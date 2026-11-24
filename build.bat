@echo off
chcp 65001 >nul
echo PTS Benchmark v0.5 - build .exe (Windows 10/11)
echo.
python --version
dotnet --version
python -m pip install --upgrade pyinstaller psutil
dotnet build csharp/PtsHardwareInfo.csproj -c Release
python -m PyInstaller --onefile --noconsole --name "PTS-Benchmark" --version-file version_info.txt --add-binary "csharp/bin/Release/net8.0-windows/PtsHardwareInfo.exe;." main.py
echo.
echo Hotovo: dist\PTS-Benchmark.exe
echo C# helper: csharp\bin\Release\net8.0-windows\PtsHardwareInfo.exe
pause
