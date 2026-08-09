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
  echo   빌드용 가상환경을 만듭니다.
  echo.
  "%PYTHON_EXE%" -m venv "%VENV_DIR%"
  if errorlevel 1 goto FAIL
)

set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
call :ENSURE_VENV
if errorlevel 1 goto FAIL

"%VENV_PY%" -m pip install --require-hashes -r "%~dp0requirements-release.txt"
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
for /f "usebackq delims=" %%P in (`py -3 -c "import sys; print(sys.executable) if sys.version_info >= (3, 10) else sys.exit(1)" 2^>nul`) do set "PYTHON_EXE=%%P"
if defined PYTHON_EXE exit /b 0
for /f "usebackq delims=" %%P in (`python -c "import sys; print(sys.executable) if sys.version_info >= (3, 10) else sys.exit(1)" 2^>nul`) do set "PYTHON_EXE=%%P"
if defined PYTHON_EXE exit /b 0
exit /b 1

:ENSURE_VENV
"%VENV_PY%" -c "import sys" >nul 2>&1
if not errorlevel 1 exit /b 0
echo.
echo   기존 빌드용 가상환경이 손상되어 다시 만듭니다.
echo.
rmdir /s /q "%VENV_DIR%" >nul 2>&1
"%PYTHON_EXE%" -m venv "%VENV_DIR%"
if errorlevel 1 exit /b 1
exit /b 0

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
