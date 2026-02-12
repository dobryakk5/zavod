# core/urls.py — добавлены referral endpoints

from django.urls import path
from . import views
from . import views_referral   # ← новый импорт

app_name = 'core'

urlpatterns = [
    # --- существующие маршруты (не трогаем) ---
    path('admin/post/<int:post_id>/generate-image/', views.generate_post_image, name='generate_post_image'),
    path('admin/post/<int:post_id>/generate-video/', views.generate_post_video, name='generate_post_video'),
    path('admin/post/<int:post_id>/quick-publish/', views.quick_publish_post, name='quick_publish_post'),
    path('admin/post/<int:post_id>/regenerate-text/', views.regenerate_text, name='regenerate_post_text'),
    path('admin/schedule/<int:schedule_id>/publish-now/', views.publish_schedule_now, name='publish_schedule_now'),
    path('admin/client/<int:client_id>/analyze-channel/', views.analyze_telegram_channel, name='analyze_telegram_channel'),

    # --- referral API ---
    path('api/referral/create_code/', views_referral.create_code, name='referral_create_code'),
    path('api/referral/my_code/', views_referral.my_code, name='referral_my_code'),
    path('api/referral/delete_code/', views_referral.delete_code, name='referral_delete_code'),
    path('api/referral/stats/', views_referral.stats, name='referral_stats'),
]
