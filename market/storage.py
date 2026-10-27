from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateReceiptStorage(FileSystemStorage):
    """Store payment receipts outside MEDIA_ROOT and never expose a public URL."""

    def __init__(self):
        super().__init__(location=settings.BASE_DIR / "private_uploads", base_url=None)

    def url(self, name):
        raise ValueError("Payment receipts are private; use the authenticated admin receipt view.")
