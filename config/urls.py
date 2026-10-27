from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path
from market import views

handler404 = "market.views.custom_404"
handler500 = "market.views.custom_500"

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/reward-notice/dismiss/", views.dismiss_reward_notice, name="dismiss_reward_notice"),
    path("store/save/", views.save_store, name="save_store"),
    path("ads/create/", views.create_ad, name="create_ad"),
    path("ads/<int:pk>/edit/", views.edit_ad, name="edit_ad"),
    path("ads/<int:pk>/delete/", views.delete_ad, name="delete_ad"),
    path("ads/<int:pk>/", views.ad_detail, name="ad_detail"),
    path("subscriptions/", views.subscriptions, name="subscriptions"),
    path("contact/", views.contact, name="contact"),
    path("manage/", views.manage, name="manage"),
    path("manage/subscriptions/<int:pk>/receipt/", views.admin_receipt, name="admin_receipt"),
    path("manage/subscriptions/<int:pk>/<str:decision>/", views.review_subscription, name="review_subscription"),
    path("manage/ads/<int:pk>/review/", views.review_ad, name="review_ad"),
    path("manage/settings/", views.save_settings, name="save_settings"),
    path("manage/referrals/<int:pk>/<str:decision>/", views.review_referral, name="review_referral"),
    # Media routes must appear before the catch-all in local development.
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Unknown paths render our branded 404 instead of a generic server page.
urlpatterns += [re_path(r"^.*$", views.custom_404)]
