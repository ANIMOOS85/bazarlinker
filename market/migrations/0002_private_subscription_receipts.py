from pathlib import Path
import shutil

from django.conf import settings
from django.db import migrations, models
import market.storage


def move_existing_receipts_to_private_storage(apps, schema_editor):
    SubscriptionRequest = apps.get_model("market", "SubscriptionRequest")
    public_root = Path(settings.MEDIA_ROOT).resolve()
    private_root = (Path(settings.BASE_DIR) / "private_uploads").resolve()

    for subscription in SubscriptionRequest.objects.exclude(receipt="").iterator():
        raw_name = str(subscription.receipt)
        relative_name = Path(raw_name)
        if relative_name.is_absolute() or ".." in relative_name.parts:
            continue
        source = (public_root / relative_name).resolve()
        destination = (private_root / relative_name).resolve()
        if public_root not in source.parents or private_root not in destination.parents:
            continue
        if not source.is_file():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.move(str(source), str(destination))
        else:
            # If a private copy already exists, remove the public duplicate.
            source.unlink(missing_ok=True)


def noop_reverse(apps, schema_editor):
    # Private payment evidence must not be copied back into a publicly served folder.
    pass


class Migration(migrations.Migration):
    dependencies = [("market", "0001_initial")]

    operations = [
        migrations.RunPython(move_existing_receipts_to_private_storage, noop_reverse),
        migrations.AlterField(
            model_name="subscriptionrequest",
            name="receipt",
            field=models.ImageField(storage=market.storage.PrivateReceiptStorage(), upload_to="receipts/"),
        ),
    ]
