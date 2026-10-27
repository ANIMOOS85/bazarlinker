from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .views import validate_external_url, validate_image_upload


class BrandedErrorPageTests(TestCase):
    def test_unknown_path_uses_custom_404(self):
        response = self.client.get('/this-page-does-not-exist/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'اوه! این صفحه پیدا نشد', status_code=404)
        self.assertContains(response, 'بازگشت به صفحه اصلی', status_code=404)

    def test_missing_ad_uses_custom_404(self):
        response = self.client.get('/ads/987654321/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'اوه! این صفحه پیدا نشد', status_code=404)


class InputValidationTests(TestCase):
    def test_javascript_url_is_rejected(self):
        self.assertIsNotNone(validate_external_url('javascript:alert(1)', 'واتساپ'))

    def test_https_url_is_accepted(self):
        self.assertIsNone(validate_external_url('https://wa.me/989120000000', 'واتساپ'))

    def test_text_file_is_rejected_as_image(self):
        upload = SimpleUploadedFile('receipt.png', b'this is not an image', content_type='image/png')
        self.assertIsNotNone(validate_image_upload(upload, required=True))
