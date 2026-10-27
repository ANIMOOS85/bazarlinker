from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from .models import (
    Ad,
    ContactMessage,
    Referral,
    SellerProfile,
    SiteSettings,
    Store,
    SubscriptionPlan,
    SubscriptionRequest,
)

admin.site.site_header = "مدیریت بازار لینکَر"
admin.site.site_title = "مدیریت بازار لینکَر"
admin.site.index_title = "مدیریت فروشگاه‌ها، آگهی‌ها و اشتراک‌ها"


@admin.register(SubscriptionRequest)
class SubscriptionRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "requested_at", "expires_at", "receipt_link")
    list_filter = ("status", "requested_at")
    search_fields = ("user__username", "user__email", "plan__title")
    readonly_fields = ("receipt_link", "status", "requested_at", "reviewed_at", "expires_at")
    exclude = ("receipt",)

    def has_add_permission(self, request):
        # Requests must originate from the seller's payment form.
        return False

    @admin.display(description="رسید پرداخت")
    def receipt_link(self, obj):
        if not obj or not obj.pk or not obj.receipt:
            return "—"
        url = reverse("admin_receipt", args=[obj.pk])
        return format_html('<a href="{}" target="_blank" rel="noopener noreferrer">مشاهده رسید خصوصی</a>', url)


for model in [SellerProfile, Store, Ad, SubscriptionPlan, ContactMessage, SiteSettings, Referral]:
    admin.site.register(model)
