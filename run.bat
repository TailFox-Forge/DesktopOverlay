@echo off
rem 창 없이 실행. 인자로 이미지 파일을 주거나, 이 파일 위로 이미지를 끌어다 놓아도 된다.
cd /d "%~dp0"
start "" pythonw "%~dp0desktop_overlay.py" %1
