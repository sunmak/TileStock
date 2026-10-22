@echo off
setlocal
cd /d "%~dp0"
echo TileStock Pro - first time setup
py -3.12 --version >nul 2>&1
if errorlevel 1 (
 echo Install Python 3.12 from python.org with the Python launcher, then try again.
 pause
 exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
 py -3.12 -m venv .venv
 if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install -r requirements-lock.txt
if errorlevel 1 goto failed
if not exist ".env" copy ".env.example" ".env" >nul
echo.
echo Setup complete. Follow README.md to create the database and edit .env.
echo First run Setup-Owner.bat if no owner exists, then Start-TileStock.bat.
pause
exit /b 0
:failed
echo Setup failed. Check the error above and your internet connection.
pause
exit /b 1
