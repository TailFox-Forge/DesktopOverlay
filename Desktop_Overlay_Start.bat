@echo off
rem 소스에서 바로 실행할 때 쓰는 launcher.
rem 파이썬이 없으면 설치 페이지로 안내한다.
rem 파이썬 없이 쓰려면 배포된 Desktop_Overlay_Start.exe 를 사용하면 된다.
setlocal
cd /d "%~dp0"

where pythonw >nul 2>&1
if errorlevel 1 goto NOPYTHON

pythonw -c "import PyQt5, PIL, numpy" >nul 2>&1
if errorlevel 1 goto NOLIBS

if "%~1"=="" (
  start "" pythonw "%~dp0desktop_overlay.py"
) else (
  start "" pythonw "%~dp0desktop_overlay.py" "%~1"
)
exit /b 0

:NOPYTHON
echo.
echo   파이썬이 설치되어 있지 않습니다.
echo.
echo   1) 방금 열린 페이지에서 Windows 용 파이썬을 내려받아 설치하세요.
echo   2) 설치 화면 맨 아래 "Add python.exe to PATH" 를 반드시 체크하세요.
echo   3) 설치가 끝나면 이 파일을 다시 실행하세요.
echo.
echo   설치 없이 쓰려면 Desktop_Overlay_Start.exe 를 사용하세요.
echo.
start "" https://www.python.org/downloads/
pause
exit /b 1

:NOLIBS
echo.
echo   필요한 라이브러리가 없습니다. 지금 설치합니다.
echo.
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo   설치에 실패했습니다. 아래 명령을 직접 실행해 보세요.
  echo     python -m pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)
echo.
echo   설치가 끝났습니다. 프로그램을 시작합니다.
if "%~1"=="" (
  start "" pythonw "%~dp0desktop_overlay.py"
) else (
  start "" pythonw "%~dp0desktop_overlay.py" "%~1"
)
exit /b 0
