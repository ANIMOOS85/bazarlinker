@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv (
  echo Creating Python virtual environment...
  py -m venv .venv
)
call .venv\Scripts\activate.bat
if not exist .env (
  if not defined DJANGO_DEBUG set DJANGO_DEBUG=1
  if not defined DJANGO_SECRET_KEY set DJANGO_SECRET_KEY=django-insecure-local-development-only-change-before-deployment
  if not defined DJANGO_ALLOWED_HOSTS set DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
)
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_bazaar
if errorlevel 1 (
  echo.
  echo Initialization failed. Check the error above.
  pause
  exit /b 1
)
echo.
echo Bazaar Linker is starting at http://127.0.0.1:8000/
echo Admin panel: http://127.0.0.1:8000/manage/  (also /django-admin/)
python manage.py runserver 127.0.0.1:8000
pause
