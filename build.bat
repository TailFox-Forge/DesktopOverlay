@echo off
rem 파이썬 없이도 실행되는 배포 폴더를 만든다.
rem 결과물: dist\Desktop_Overlay_Start\Desktop_Overlay_Start.exe
setlocal
cd /d "%~dp0"
set "VENV_DIR=%~dp0.venv-build"

call :FIND_PYTHON
if errorlevel 1 goto NOPYTHON

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo.
  echo   빌드용 가상환경을 만듭니다: %VENV_DIR%
  echo.
  "%PYTHON_EXE%" -m venv "%VENV_DIR%"
  if errorlevel 1 goto FAIL
)

set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

"%VENV_PY%" -m pip install -r "%~dp0requirements-release.txt"
if errorlevel 1 goto FAIL

"%VENV_PY%" -m PyInstaller --noconfirm --onedir --windowed ^
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
echo   빌드 완료: dist\Desktop_Overlay_Start\Desktop_Overlay_Start.exe
echo.
pause
exit /b 0

:FIND_PYTHON
set "PYTHON_EXE="
for /f "usebackq delims=" %%P in (`py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1); print(sys.executable)" 2^>nul`) do set "PYTHON_EXE=%%P"
if defined PYTHON_EXE exit /b 0
for /f "usebackq delims=" %%P in (`python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1); print(sys.executable)" 2^>nul`) do set "PYTHON_EXE=%%P"
if defined PYTHON_EXE exit /b 0
exit /b 1

:NOPYTHON
echo.
echo   Python 3.10 이상을 찾지 못했습니다.
echo.
pause
exit /b 1

:FAIL
echo.
echo   빌드에 실패했습니다.
echo.
pause
exit /b 1
