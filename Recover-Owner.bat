@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Run Setup-Windows.bat first.
 pause
 exit /b 1
)
echo Local owner recovery resets the owner's password and requires authenticator re-enrollment.
echo Only use this from your trusted Windows account when locked out.
".venv\Scripts\python.exe" owner_setup.py --recover-owner
pause
