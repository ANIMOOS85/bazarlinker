import secrets, string
from django.db import models, transaction, IntegrityError
from django.contrib.auth.models import User
from django.utils import timezone
from .storage import PrivateReceiptStorage

CATEGORIES = ['پوشاک','خوراکی و مواد غذایی','لوازم خانه و آشپزخانه','زیبایی و بهداشت','موبایل و دیجیتال','کامپیوتر و لوازم جانبی','خدمات','خودرو و قطعات','کتاب و آموزش','ورزش و سرگرمی','صنایع دستی','سایر']
CITIES = ['تهران','اهواز','ایذه','کرج','اصفهان','شیراز','مشهد','تبریز','قم','خرم‌آباد','دزفول','اندیمشک','آبادان','رشت','یزد','بندرعباس','اراک','قزوین','سنندج','کرمانشاه','زنجان','ساری','گرگان','بوشهر','یاسوج','ایلام','بیرجند','زاهدان','اردبیل','ارومیه','کاشان']
def make_referral_code():
    alphabet = string.ascii_uppercase + string.digits
    return 'BL-' + ''.join(secrets.choice(alphabet) for _ in range(6))
class SellerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='seller_profile')
    referral_code = models.CharField(max_length=12, unique=True, blank=True)
    referred_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='referrals')
    bonus_credits = models.PositiveIntegerField(default=0)
    initial_free_quota = models.PositiveIntegerField(default=3)
    reward_notice = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    def save(self, *args, **kwargs):
        if not self.referral_code and self._state.adding:
            for _ in range(20):
                code = make_referral_code()
                if SellerProfile.objects.filter(referral_code=code).exists():
                    continue
                self.referral_code = code
                try:
                    return super().save(*args, **kwargs)
                except IntegrityError:
                    # A concurrent request may have generated the same code; retry.
                    self.referral_code = ''
            raise RuntimeError('Could not allocate a unique referral code after several attempts.')
        super().save(*args, **kwargs)
    @property
    def free_quota_left(self):
        used = Ad.objects.filter(store__owner=self.user).count()
        return max(0, self.initial_free_quota + self.bonus_credits - used)
class Store(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stores')
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=80, default='سایر')
    city = models.CharField(max_length=80)
    province = models.CharField(max_length=80, blank=True)
    address = models.CharField(max_length=250, blank=True)
    phone = models.CharField(max_length=30)
    whatsapp = models.CharField(max_length=180, blank=True)
    bale = models.CharField(max_length=180, blank=True)
    contact_link = models.URLField(blank=True)
    about = models.TextField(blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name
class Ad(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='ads')
    title = models.CharField(max_length=180)
    price = models.PositiveBigIntegerField(default=0)
    category = models.CharField(max_length=80, default='سایر')
    city = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    image1 = models.ImageField(upload_to='ads/', blank=True)
    image2 = models.ImageField(upload_to='ads/', blank=True)
    image3 = models.ImageField(upload_to='ads/', blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[('published','منتشرشده'),('pending','در انتظار بررسی'),('rejected','ردشده')], default='published')
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.title
class SubscriptionPlan(models.Model):
    title = models.CharField(max_length=80)
    months = models.PositiveSmallIntegerField(default=1)
    price = models.PositiveBigIntegerField(default=0)
    active = models.BooleanField(default=True)
    def __str__(self): return self.title
class SubscriptionRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscription_requests')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    receipt = models.ImageField(upload_to='receipts/', storage=PrivateReceiptStorage())
    status = models.CharField(max_length=20, choices=[('pending','در انتظار'),('approved','تأیید شده'),('rejected','رد شده')], default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField(max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
class SiteSettings(models.Model):
    site_name = models.CharField(max_length=120, default='بازار لینکَر')
    bank_name = models.CharField(max_length=120, blank=True)
    bank_holder = models.CharField(max_length=120, blank=True)
    bank_card = models.CharField(max_length=30, blank=True)
    site_description = models.TextField(blank=True)
    @classmethod
    def current(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
class Referral(models.Model):
    referrer = models.ForeignKey(SellerProfile, on_delete=models.PROTECT, related_name='referral_rows')
    referred = models.OneToOneField(SellerProfile, on_delete=models.PROTECT, related_name='referral_source')
    code_used = models.CharField(max_length=12)
    status = models.CharField(max_length=20, choices=[('pending','در انتظار تکمیل شرایط'),('successful','موفق'),('rejected','ردشده')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    reward_at = models.DateTimeField(null=True, blank=True)
    reward_ads = models.PositiveSmallIntegerField(default=0)
    def try_complete(self):
        if self.status != 'pending':
            return False
        with transaction.atomic():
            row = Referral.objects.select_for_update().select_related('referred__user').get(pk=self.pk)
            if row.status != 'pending':
                return False
            # Recheck eligibility after locking the referral to avoid awarding twice
            # or relying only on stale checks made before entering the transaction.
            has_active_store = Store.objects.filter(owner=row.referred.user, active=True).exists()
            has_published_ad = Ad.objects.filter(store__owner=row.referred.user, status='published').exists()
            if not has_active_store or not has_published_ad:
                return False
            referrer = SellerProfile.objects.select_for_update().get(pk=row.referrer_id)
            referrer.bonus_credits += 3
            referrer.reward_notice = True
            referrer.save(update_fields=['bonus_credits', 'reward_notice'])
            row.status = 'successful'
            row.reward_ads = 3
            row.reward_at = timezone.now()
            row.save(update_fields=['status', 'reward_ads', 'reward_at'])
        return True
