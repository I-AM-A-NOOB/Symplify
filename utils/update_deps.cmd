@echo off
echo =====================
echo = pip upgrade check =
echo =====================
echo [!] please check if you are in the correct python environment.
pip list --outdated
choice /C yn /N /M "Upgrade outdated packages automatically? (y/N) " /D n /T 10
if errorlevel 2 (
    echo Abort.
    goto :eof
) else if errorlevel 1 (
    echo Upgrading outdated packages...
    python -m pip install --upgrade pip
    pip install --upgrade -r requirements.txt
)
pause
