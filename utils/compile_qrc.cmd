@echo off
cd /d "%~dp0"
pyside6-rcc app\qfluentplus\resource\resource.qrc -o app\qfluentplus\resource\resource.py
echo Compiled resource.qrc to resource.py
pause
