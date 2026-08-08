@echo off
rem 파이썬 없이도 실행되는 단일 exe 를 만든다.
rem 결과물: dist\Desktop_Overlay_Start.exe
cd /d "%~dp0"

python -m pip install --upgrade pyinstaller
if errorlevel 1 goto FAIL

python -m PyInstaller --noconfirm --onefile --windowed ^
  --name Desktop_Overlay_Start ^
  --exclude-module tkinter ^
  --exclude-module PyQt5.QtWebEngineWidgets ^
  --exclude-module PyQt5.QtNetwork ^
  --exclude-module PyQt5.QtQml ^
  --exclude-module PyQt5.QtSql ^
  --exclude-module matplotlib ^
  --exclude-module scipy ^
  --exclude-module pandas ^
  desktop_overlay.py
if errorlevel 1 goto FAIL

echo.
echo   빌드 완료: dist\Desktop_Overlay_Start.exe
echo.
pause
exit /b 0

:FAIL
echo.
echo   빌드에 실패했습니다.
echo.
pause
exit /b 1
