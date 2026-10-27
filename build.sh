#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py seed_bazaar

# Free Render services do not provide a shell. These optional environment variables
# allow the first admin account to be created during the initial build only.
if [[ -n "${DJANGO_SUPERUSER_USERNAME:-}" && -n "${DJANGO_SUPERUSER_EMAIL:-}" && -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]]; then
  python manage.py shell -c 'import os; from django.contrib.auth import get_user_model; User = get_user_model(); username = os.environ["DJANGO_SUPERUSER_USERNAME"]; email = os.environ["DJANGO_SUPERUSER_EMAIL"]; password = os.environ["DJANGO_SUPERUSER_PASSWORD"]; User.objects.filter(username=username).exists() or User.objects.create_superuser(username, email, password)'
fi
