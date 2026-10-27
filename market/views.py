import calendar
import math
import mimetypes
import re
from pathlib import PurePosixPath, Path
from urllib.parse import urlsplit

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Max, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from PIL import Image, UnidentifiedImageError

from .models import (
    Ad,
    CATEGORIES,
    CITIES,
    ContactMessage,
    Referral,
    SellerProfile,
    SiteSettings,
    Store,
    SubscriptionPlan,
    SubscriptionRequest,
)

MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 30_000_000
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image_upload(upload, *, required=False):
    """Validate the actual image bytes, not the browser-supplied MIME type."""
    if not upload:
        return "یک تصویر انتخاب کنید." if required else None
    if upload.size > MAX_IMAGE_SIZE:
        return "حجم هر تصویر باید حداکثر ۵ مگابایت باشد."

    suffix = Path(upload.name or "").suffix.lower()
    allowed_suffixes = {".jpg", ".jpeg", ".png", ".webp"}
    if suffix not in allowed_suffixes:
        return "پسوند تصویر باید JPG، PNG یا WEBP باشد."

    try:
        upload.seek(0)
        with Image.open(upload) as image:
            expected_formats = {
                ".jpg": {"JPEG"},
                ".jpeg": {"JPEG"},
                ".png": {"PNG"},
                ".webp": {"WEBP"},
            }
            if image.format not in ALLOWED_IMAGE_FORMATS or image.format not in expected_formats[suffix]:
                return "فرمت واقعی تصویر با پسوند فایل سازگار نیست."
            if image.width < 1 or image.height < 1 or image.width * image.height > MAX_IMAGE_PIXELS:
                return "ابعاد تصویر معتبر نیست یا بیش از حد بزرگ است."
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return "فایل انتخاب‌شده یک تصویر معتبر نیست."
    finally:
        try:
            upload.seek(0)
        except (AttributeError, OSError):
            pass
    return None


def parse_coordinates(lat_value, lng_value):
    """Return a valid coordinate pair, or (None, None) when both are blank."""
    lat_value = (lat_value or "").strip()
    lng_value = (lng_value or "").strip()
    if not lat_value and not lng_value:
        return None, None
    if not lat_value or not lng_value:
        raise ValueError("هر دو مختصات عرض و طول باید وارد شوند.")
    try:
        latitude = float(lat_value)
        longitude = float(lng_value)
    except (TypeError, ValueError):
        raise ValueError("مختصات نقشه معتبر نیست.")
    if (
        not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        raise ValueError("مختصات خارج از محدوده معتبر جغرافیایی است.")
    return latitude, longitude


def safe_external_url(value):
    """Return an already-safe HTTPS URL or an empty string for legacy unsafe data."""
    value = (value or "").strip()
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() == "https" and parsed.hostname and parsed.username is None and parsed.password is None and len(value) <= 180:
            return value
    except ValueError:
        pass
    return ""


def validate_external_url(value, field_label):
    """Allow only absolute HTTPS links for user-provided external contact URLs."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme.lower() == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and len(value) <= 180
        )
    except ValueError:
        valid = False
    if not valid:
        return f"لینک {field_label} باید یک نشانی کامل و امن با https:// باشد."
    return None


def validate_phone(value):
    value = (value or "").strip()
    digits = re.sub(r"\D", "", value)
    return bool(value and len(value) <= 30 and re.fullmatch(r"[0-9+()\-\s]+", value) and len(digits) >= 5)


def add_calendar_months(value, months):
    """Add real calendar months rather than approximating each month as 30 days."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def home(request):
    ads = Ad.objects.filter(status="published", store__active=True).select_related("store").order_by("-created_at")
    q = request.GET.get("q", "").strip()[:180]
    category = request.GET.get("category", "")
    city = request.GET.get("city", "").strip()[:80]
    low = request.GET.get("min_price", "").strip()
    high = request.GET.get("max_price", "").strip()

    if q:
        ads = ads.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(store__name__icontains=q))
    if category and category != "همه دسته‌ها" and category in CATEGORIES:
        ads = ads.filter(category=category)
    if city:
        ads = ads.filter(city__icontains=city)
    if low.isdigit() and len(low) <= 18:
        ads = ads.filter(price__gte=int(low))
    else:
        low = ""
    if high.isdigit() and len(high) <= 18:
        ads = ads.filter(price__lte=int(high))
    else:
        high = ""

    matching_store_ids = set(ads.values_list("store_id", flat=True).distinct())
    stores = Store.objects.filter(active=True, latitude__isnull=False, longitude__isnull=False)
    store_points = list(stores.values("id", "name", "city", "phone", "latitude", "longitude"))
    for point in store_points:
        point["has_matching_ads"] = point["id"] in matching_store_ids

    return render(request, "market/home.html", {
        "ads": ads,
        "stores": store_points,
        "categories": CATEGORIES,
        "cities": CITIES,
        "q": q,
        "selected_category": category,
        "city": city,
        "min_price": low if low.isdigit() else "",
        "max_price": high if high.isdigit() else "",
        "matching_store_count": len(matching_store_ids),
        "settings": SiteSettings.current(),
    })


def register(request):
    ref_code = request.POST.get("ref_code", "").strip().upper() if request.method == "POST" else request.GET.get("ref", "").strip().upper()
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        confirm = request.POST.get("confirm", "")
        error = None

        if not username or not email or not password:
            error = "همه فیلدهای ضروری را تکمیل کنید."
        elif len(username) > 150:
            error = "نام کاربری حداکثر باید ۱۵۰ نویسه باشد."
        else:
            try:
                validate_email(email)
            except ValidationError:
                error = "نشانی ایمیل معتبر نیست."

        if not error and password != confirm:
            error = "تکرار رمز عبور یکسان نیست."
        if not error:
            try:
                validate_password(password, user=User(username=username, email=email))
            except ValidationError as exc:
                error = " ".join(exc.messages)
        if not error and (User.objects.filter(username__iexact=username).exists() or User.objects.filter(email__iexact=email).exists()):
            error = "این نام کاربری یا ایمیل قبلاً ثبت شده است."

        referrer = None
        if not error and ref_code:
            referrer = SellerProfile.objects.select_related("user").filter(referral_code=ref_code).first()
            if not referrer:
                error = "کد معرف معتبر نیست."
            elif referrer.user.email.lower() == email:
                error = "نمی‌توانید خودتان را معرفی کنید."

        if error:
            messages.error(request, error)
        else:
            with transaction.atomic():
                user = User.objects.create_user(username=username, email=email, password=password)
                profile = SellerProfile.objects.create(user=user, referred_by=referrer)
                if referrer:
                    Referral.objects.create(referrer=referrer, referred=profile, code_used=ref_code)
            login(request, user)
            messages.success(request, "حساب شما ساخته شد. برای شروع اطلاعات فروشگاه را ثبت کنید.")
            return redirect("dashboard")
    return render(request, "market/auth.html", {"mode": "register", "ref_code": ref_code, "settings": SiteSettings.current()})


def login_view(request):
    if request.method == "POST":
        username_or_email = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username_or_email, password=password)
        if user is None:
            user_obj = User.objects.filter(email__iexact=username_or_email).first()
            if user_obj:
                user = authenticate(request, username=user_obj.username, password=password)
        if user:
            login(request, user)
            return redirect("manage" if user.is_staff else "dashboard")
        messages.error(request, "نام کاربری/ایمیل یا رمز عبور نادرست است.")
    return render(request, "market/auth.html", {"mode": "login", "settings": SiteSettings.current()})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("home")


def dashboard(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if request.user.is_staff:
        return redirect("manage")

    profile, _ = SellerProfile.objects.get_or_create(user=request.user)
    stores = Store.objects.filter(owner=request.user)
    ads = Ad.objects.filter(store__owner=request.user).select_related("store").order_by("-created_at")
    referrals = Referral.objects.filter(referrer=profile).select_related("referred__user").order_by("-created_at")
    received = getattr(profile, "referral_source", None)
    active_sub = SubscriptionRequest.objects.filter(
        user=request.user, status="approved", expires_at__gt=timezone.now()
    ).order_by("-expires_at").first()
    plans = SubscriptionPlan.objects.filter(active=True)
    pending_subscription = SubscriptionRequest.objects.filter(user=request.user, status="pending").exists()

    return render(request, "market/dashboard.html", {
        "profile": profile,
        "stores": stores,
        "store": stores.first(),
        "ads": ads,
        "referrals": referrals,
        "successful_referrals": referrals.filter(status="successful").count(),
        "pending_referrals": referrals.filter(status="pending").count(),
        "active_sub": active_sub,
        "pending_subscription": pending_subscription,
        "plans": plans,
        "categories": CATEGORIES,
        "cities": CITIES,
        "received_referral": received,
        "settings": SiteSettings.current(),
    })


@login_required
@require_POST
def save_store(request):
    store = Store.objects.filter(owner=request.user).first() or Store(owner=request.user)
    values = {
        "name": request.POST.get("name", "").strip(),
        "category": request.POST.get("category", "سایر").strip(),
        "city": request.POST.get("city", "").strip(),
        "province": request.POST.get("province", "").strip(),
        "address": request.POST.get("address", "").strip(),
        "phone": request.POST.get("phone", "").strip(),
        "whatsapp": request.POST.get("whatsapp", "").strip(),
        "bale": request.POST.get("bale", "").strip(),
        "contact_link": request.POST.get("contact_link", "").strip(),
        "about": request.POST.get("about", "").strip(),
    }
    if not values["name"] or not values["city"] or not values["phone"]:
        messages.error(request, "نام فروشگاه، شهر و شماره تماس ضروری است.")
        return redirect("dashboard")
    if len(values["name"]) > 160 or len(values["city"]) > 80 or len(values["province"]) > 80 or len(values["address"]) > 250 or len(values["about"]) > 5000:
        messages.error(request, "یکی از فیلدها بیش از حد مجاز طولانی است.")
        return redirect("dashboard")
    if values["category"] not in CATEGORIES:
        messages.error(request, "دسته‌بندی فروشگاه معتبر نیست.")
        return redirect("dashboard")
    if not validate_phone(values["phone"]):
        messages.error(request, "شماره تماس معتبر نیست.")
        return redirect("dashboard")
    for key, label in (("whatsapp", "واتساپ"), ("bale", "بله"), ("contact_link", "ارتباط با فروشنده")):
        problem = validate_external_url(values[key], label)
        if problem:
            messages.error(request, problem)
            return redirect("dashboard")

    try:
        latitude, longitude = parse_coordinates(request.POST.get("latitude"), request.POST.get("longitude"))
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("dashboard")

    for field, value in values.items():
        setattr(store, field, value)
    store.latitude, store.longitude = latitude, longitude
    store.save()
    messages.success(request, "اطلاعات فروشگاه ذخیره شد.")
    return redirect("dashboard")


def validate_ad_form(request, store, ad=None):
    title = request.POST.get("title", "").strip()
    price_raw = request.POST.get("price", "0").strip()
    category = request.POST.get("category", "سایر").strip()
    city = request.POST.get("city", store.city).strip()
    description = request.POST.get("description", "").strip()

    try:
        price = int(price_raw)
    except (ValueError, TypeError):
        price = -1

    if not title or len(title) > 180 or price < 0 or price > 9_000_000_000_000_000 or category not in CATEGORIES or not city or len(city) > 80 or len(description) > 5000:
        return None, "عنوان، قیمت، دسته‌بندی، شهر یا توضیحات را بررسی کنید."

    try:
        latitude, longitude = parse_coordinates(request.POST.get("latitude"), request.POST.get("longitude"))
    except ValueError as exc:
        return None, str(exc)
    if latitude is None and longitude is None:
        latitude, longitude = store.latitude, store.longitude

    uploaded = {}
    for field in ("image1", "image2", "image3"):
        file = request.FILES.get(field)
        if file:
            problem = validate_image_upload(file)
            if problem:
                return None, problem
            uploaded[field] = file

    if ad is None:
        ad = Ad(store=store)
    ad.title = title
    ad.price = price
    ad.category = category
    ad.city = city
    ad.description = description
    ad.latitude, ad.longitude = latitude, longitude
    for field, file in uploaded.items():
        setattr(ad, field, file)
    return ad, None


@login_required
@require_POST
def create_ad(request):
    store = Store.objects.filter(owner=request.user, active=True).first()
    if not store:
        messages.error(request, "ابتدا اطلاعات فروشگاه را ثبت کنید.")
        return redirect("dashboard")

    profile, _ = SellerProfile.objects.get_or_create(user=request.user)
    active = SubscriptionRequest.objects.filter(user=request.user, status="approved", expires_at__gt=timezone.now()).exists()
    if not active and Ad.objects.filter(store__owner=request.user).count() >= profile.initial_free_quota + profile.bonus_credits:
        messages.error(request, "سهمیه رایگان شما تمام شده است. اشتراک بخرید یا دوستان خود را معرفی کنید.")
        return redirect("dashboard")

    ad, error = validate_ad_form(request, store)
    if error:
        messages.error(request, error)
        return redirect("dashboard")
    ad.save()

    referral = Referral.objects.filter(referred__user=request.user, status="pending").first()
    if referral and referral.try_complete():
        messages.success(request, "آگهی ثبت شد؛ معرفی دوستت تکمیل شد و ۳ سهمیه رایگان به معرف تعلق گرفت.")
    else:
        messages.success(request, "آگهی با موفقیت ثبت شد.")
    return redirect("dashboard")


@login_required
def edit_ad(request, pk):
    ad = get_object_or_404(Ad, pk=pk, store__owner=request.user)
    if request.method == "POST":
        updated_ad, error = validate_ad_form(request, ad.store, ad=ad)
        if error:
            messages.error(request, error)
        else:
            updated_ad.save()
            messages.success(request, "تغییرات آگهی ذخیره شد.")
            return redirect("dashboard")
    return render(request, "market/ad_edit.html", {
        "ad": ad,
        "categories": CATEGORIES,
        "cities": CITIES,
        "settings": SiteSettings.current(),
    })


@login_required
@require_POST
def delete_ad(request, pk):
    ad = get_object_or_404(Ad, pk=pk, store__owner=request.user)
    ad.delete()
    messages.success(request, "آگهی حذف شد.")
    return redirect("dashboard")


def ad_detail(request, pk):
    ad = get_object_or_404(Ad, pk=pk, status="published", store__active=True)
    return render(request, "market/ad_detail.html", {
        "ad": ad,
        "whatsapp_url": safe_external_url(ad.store.whatsapp),
        "bale_url": safe_external_url(ad.store.bale),
        "contact_url": safe_external_url(ad.store.contact_link),
        "settings": SiteSettings.current(),
    })


@login_required
@require_POST
def subscriptions(request):
    if SubscriptionRequest.objects.filter(user=request.user, status="pending").exists():
        messages.error(request, "یک درخواست اشتراک شما در انتظار بررسی است؛ پس از تعیین وضعیت، درخواست تازه ثبت کنید.")
        return redirect("dashboard")

    plan_id = request.POST.get("plan", "")
    if not plan_id.isdigit():
        messages.error(request, "طرح اشتراک انتخاب‌شده معتبر نیست.")
        return redirect("dashboard")
    plan = SubscriptionPlan.objects.filter(pk=int(plan_id), active=True).first()
    if not plan:
        messages.error(request, "طرح اشتراک انتخاب‌شده در دسترس نیست.")
        return redirect("dashboard")

    receipt = request.FILES.get("receipt")
    problem = validate_image_upload(receipt, required=True)
    if problem:
        messages.error(request, problem)
        return redirect("dashboard")

    SubscriptionRequest.objects.create(user=request.user, plan=plan, receipt=receipt)
    messages.success(request, "درخواست اشتراک برای بررسی مدیر ارسال شد.")
    return redirect("dashboard")


@require_POST
def contact(request):
    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip()
    message = request.POST.get("message", "").strip()
    try:
        validate_email(email)
        email_valid = True
    except ValidationError:
        email_valid = False
    if name and len(name) <= 100 and email_valid and message and len(message) <= 3000:
        ContactMessage.objects.create(name=name, email=email, message=message)
        messages.success(request, "پیام شما ارسال شد.")
    else:
        messages.error(request, "اطلاعات پیام را بررسی کنید.")
    return redirect("home")


def is_admin(user):
    return user.is_authenticated and user.is_staff


@user_passes_test(is_admin, login_url="login")
def manage(request):
    ctx = {
        "users": User.objects.all().order_by("-date_joined"),
        "stores": Store.objects.all().order_by("-created_at"),
        "ads": Ad.objects.all().select_related("store", "store__owner").order_by("-created_at"),
        "subs": SubscriptionRequest.objects.select_related("user", "plan").order_by("-requested_at"),
        "messages_list": ContactMessage.objects.all().order_by("-created_at"),
        "referrals": Referral.objects.select_related("referrer__user", "referred__user").order_by("-created_at"),
        "plans": SubscriptionPlan.objects.all(),
        "settings_obj": SiteSettings.current(),
        "settings": SiteSettings.current(),
    }
    return render(request, "market/manage.html", ctx)


@user_passes_test(is_admin, login_url="login")
def admin_receipt(request, pk):
    subscription = get_object_or_404(SubscriptionRequest, pk=pk)
    if not subscription.receipt:
        raise Http404
    try:
        file_obj = subscription.receipt.open("rb")
    except (FileNotFoundError, OSError, ValueError):
        raise Http404
    filename = PurePosixPath(subscription.receipt.name).name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    response = FileResponse(file_obj, content_type=content_type, as_attachment=False, filename=filename)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@user_passes_test(is_admin, login_url="login")
@require_POST
def review_subscription(request, pk, decision):
    if decision not in {"approved", "rejected"}:
        raise Http404

    now = timezone.now()
    with transaction.atomic():
        sub = get_object_or_404(SubscriptionRequest.objects.select_for_update().select_related("plan"), pk=pk)
        if sub.status != "pending":
            messages.warning(request, "این درخواست قبلاً بررسی شده است و قابل بررسی مجدد نیست.")
            return redirect("manage")

        sub.status = decision
        sub.reviewed_at = now
        if decision == "approved":
            latest_expiry = SubscriptionRequest.objects.filter(
                user=sub.user, status="approved", expires_at__gt=now
            ).aggregate(latest=Max("expires_at"))["latest"]
            start_from = max(now, latest_expiry) if latest_expiry else now
            sub.expires_at = add_calendar_months(start_from, sub.plan.months)
        else:
            sub.expires_at = None
        sub.save(update_fields=["status", "reviewed_at", "expires_at"])

    messages.success(request, "وضعیت درخواست اشتراک به‌روزرسانی شد.")
    return redirect("/manage/#subscriptions")


@user_passes_test(is_admin, login_url="login")
@require_POST
def review_referral(request, pk, decision):
    if decision not in {"successful", "rejected"}:
        raise Http404

    with transaction.atomic():
        row = get_object_or_404(Referral.objects.select_for_update().select_related("referrer__user", "referred__user"), pk=pk)
        if row.status != "pending":
            messages.warning(request, "این معرفی قبلاً بررسی شده است.")
            return redirect("/manage/#referrals")
        if decision == "successful":
            has_active_store = Store.objects.filter(owner=row.referred.user, active=True).exists()
            has_published_ad = Ad.objects.filter(store__owner=row.referred.user, status="published").exists()
            if not has_active_store or not has_published_ad:
                messages.error(request, "این معرفی هنوز شرایط دریافت جایزه را ندارد؛ فروشگاه فعال و حداقل یک آگهی منتشرشده لازم است.")
                return redirect("/manage/#referrals")
            referrer = SellerProfile.objects.select_for_update().get(pk=row.referrer_id)
            referrer.bonus_credits += 3
            referrer.reward_notice = True
            referrer.save(update_fields=["bonus_credits", "reward_notice"])
            row.reward_ads = 3
            row.reward_at = timezone.now()
        row.status = decision
        row.save(update_fields=["status", "reward_ads", "reward_at"])

    messages.success(request, "وضعیت معرفی به‌روزرسانی شد.")
    return redirect("/manage/#referrals")


@user_passes_test(is_admin, login_url="login")
@require_POST
def review_ad(request, pk):
    status = request.POST.get("status", "")
    if status not in {"published", "pending", "rejected"}:
        messages.error(request, "وضعیت انتخاب‌شده معتبر نیست.")
        return redirect("/manage/#ads")
    ad = get_object_or_404(Ad, pk=pk)
    ad.status = status
    ad.save(update_fields=["status"])
    messages.success(request, "وضعیت آگهی به‌روزرسانی شد.")
    return redirect("/manage/#ads")


@user_passes_test(is_admin, login_url="login")
@require_POST
def save_settings(request):
    site_name = request.POST.get("site_name", "").strip()
    if not site_name or len(site_name) > 120:
        messages.error(request, "نام سایت الزامی است و باید حداکثر ۱۲۰ نویسه باشد.")
        return redirect("/manage/#settings")

    s = SiteSettings.current()
    s.site_name = site_name
    s.bank_name = request.POST.get("bank_name", "").strip()[:120]
    s.bank_holder = request.POST.get("bank_holder", "").strip()[:120]
    s.bank_card = request.POST.get("bank_card", "").strip()[:30]
    s.site_description = request.POST.get("site_description", "").strip()
    s.save()

    for plan in SubscriptionPlan.objects.all():
        val = request.POST.get(f"price_{plan.pk}", "").strip()
        if val.isdigit():
            plan.price = int(val)
            plan.save(update_fields=["price"])
    messages.success(request, "تنظیمات و قیمت اشتراک‌ها ذخیره شد.")
    return redirect("/manage/#settings")


@login_required
@require_POST
def dismiss_reward_notice(request):
    profile, _ = SellerProfile.objects.get_or_create(user=request.user)
    profile.reward_notice = False
    profile.save(update_fields=["reward_notice"])
    return redirect("dashboard")


def custom_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def custom_500(request):
    return render(request, "errors/500.html", status=500)
