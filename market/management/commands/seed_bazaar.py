import sys
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from market.models import SiteSettings, SubscriptionPlan


class Command(BaseCommand):
    help = "Create initial subscription plans and site settings; never create a predictable administrator password."

    def handle(self, *args, **options):
        SiteSettings.current()
        for title, months, price in [
            ("یک‌ماهه", 1, 100000),
            ("سه‌ماهه", 3, 270000),
            ("شش‌ماهه", 6, 500000),
            ("یک‌ساله", 12, 900000),
        ]:
            SubscriptionPlan.objects.get_or_create(
                months=months,
                defaults={"title": title, "price": price, "active": True},
            )

        if not User.objects.filter(is_superuser=True).exists():
            if sys.stdin.isatty():
                self.stdout.write(self.style.WARNING("برای امنیت، مدیر با رمز پیش‌فرض ساخته نمی‌شود. حساب مدیر را بسازید:"))
                call_command("createsuperuser")
            else:
                self.stdout.write(self.style.WARNING("هیچ مدیر ارشدی ثبت نشده است؛ بعداً دستور python manage.py createsuperuser را اجرا کنید."))
        else:
            self.stdout.write("Superuser already exists; no default credentials were changed.")
        self.stdout.write(self.style.SUCCESS("Initial plans and settings checked."))
