from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls
from wagtail import urls as wagtail_urls
from api.views import VkConnectView, VkCallbackView, VkPublishView, DzenRSSFeedView
from core import views as core_views
from core.admin_views import custom_generator_view

urlpatterns = [
    path('django-admin/custom/', admin.site.admin_view(custom_generator_view), name='admin-custom-generator'),
    path('django-admin/', admin.site.urls),
    path('admin/', include(wagtailadmin_urls)),
    path('documents/', include(wagtaildocs_urls)),
    path('api/v1/', include('core.api.v1.urls')),
    path('api/', include('api.urls')),
    path('core/', include('core.urls')),  # Core app URLs
    path('rss/<slug:client_slug>.xml', DzenRSSFeedView.as_view(), name='rss-feed'),
    path('posts/<slug:client_slug>/<int:post_id>/', core_views.public_post_detail, name='public-post'),
    # Direct VK routes (used by frontend popup redirects)
    path('vk/connect/', VkConnectView.as_view(), name='vk-connect'),
    path('vk/callback/', VkCallbackView.as_view(), name='vk-callback'),
    path('vk/post_with_photos/', VkPublishView.as_view(), name='vk-post-with-photos'),
    path('', include(wagtail_urls)),
]

# Раздача медиа-файлов в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
