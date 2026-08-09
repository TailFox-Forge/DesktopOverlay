@echo off
rem 소스에서 바로 실행할 때 쓰는 launcher.
rem 파이썬이 없으면 설치 페이지로 안내한다.
rem 파이썬 없이 쓰려면 배포된 Desktop_Overlay_Start.exe 를 사용하면 된다.
setlocal
cd /d "%~dp0"
set "VENV_DIR=%~dp0.venv-runtime"

call :FIND_PYTHON
if errorlevel 1 goto NOPYTHON

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo.
  echo   소스 실행용 가상환경을 만듭니다: %VENV_DIR%
  echo.
  "%PYTHON_EXE%" -m venv "%VENV_DIR%"
  if errorlevel 1 goto VENVFAIL
)

set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
call :ENSURE_VENV
if errorlevel 1 goto VENVFAIL
set "VENV_PYW=%VENV_DIR%\Scripts\pythonw.exe"
if not exist "%VENV_PYW%" set "VENV_PYW=%VENV_PY%"

"%VENV_PY%" -c "import PyQt5, PIL, numpy" >nul 2>&1
if errorlevel 1 goto NOLIBS

goto RUN

:RUN
if "%~1"=="" (
  start "" "%VENV_PYW%" "%~dp0desktop_overlay.py"
) else (
  start "" "%VENV_PYW%" "%~dp0desktop_overlay.py" "%~1"
)
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
echo   기존 소스 실행용 가상환경이 손상되어 다시 만듭니다.
echo.
rmdir /s /q "%VENV_DIR%" >nul 2>&1
"%PYTHON_EXE%" -m venv "%VENV_DIR%"
if errorlevel 1 exit /b 1
exit /b 0

:NOPYTHON
echo.
echo   Python 3.10 이상을 찾지 못했습니다.
echo.
echo   1) 방금 열린 페이지에서 Windows 용 파이썬을 내려받아 설치하세요.
echo   2) 설치 화면 맨 아래 "Add python.exe to PATH" 를 체크하거나 Python Launcher 를 설치하세요.
echo   3) 설치가 끝나면 이 파일을 다시 실행하세요.
echo.
echo   설치 없이 쓰려면 Desktop_Overlay_Start.exe 를 사용하세요.
echo.
start "" https://www.python.org/downloads/
pause
exit /b 1

:VENVFAIL
echo.
echo   가상환경 생성에 실패했습니다.
echo.
pause
exit /b 1

:NOLIBS
echo.
echo   필요한 라이브러리를 소스 실행용 가상환경에 설치합니다.
echo.
"%VENV_PY%" -m pip install --require-hashes -r "%~dp0requirements.txt"
if errorlevel 1 (
  echo.
  echo   설치에 실패했습니다. 아래 명령을 직접 실행해 보세요.
  echo     "%VENV_PY%" -m pip install --require-hashes -r "%~dp0requirements.txt"
  echo.
  pause
  exit /b 1
)
echo.
echo   설치가 끝났습니다. 프로그램을 시작합니다.
goto RUN
