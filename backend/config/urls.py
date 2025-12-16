from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls
from wagtail import urls as wagtail_urls
from api.views import VkConnectView, VkCallbackView, VkPublishView

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('admin/', include(wagtailadmin_urls)),
    path('documents/', include(wagtaildocs_urls)),
    path('api/', include('api.urls')),
    path('core/', include('core.urls')),  # Core app URLs
    # Direct VK routes (used by frontend popup redirects)
    path('vk/connect/', VkConnectView.as_view(), name='vk-connect'),
    path('vk/callback/', VkCallbackView.as_view(), name='vk-callback'),
    path('vk/post_with_photos/', VkPublishView.as_view(), name='vk-post-with-photos'),
    path('', include(wagtail_urls)),
]

# Раздача медиа-файлов в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
