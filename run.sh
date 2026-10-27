#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
# Development defaults only. For production, configure unique environment values at the host.
if [ ! -f .env ]; then
  export DJANGO_DEBUG="${DJANGO_DEBUG:-1}"
  export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-django-insecure-local-development-only-change-before-deployment}"
  export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-localhost,127.0.0.1}"
fi
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_bazaar
python manage.py runserver 127.0.0.1:8000
