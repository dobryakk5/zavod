from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ClientInfoView,
    ClientSettingsView,
    ClientSummaryView,
    ContentTemplateViewSet,
    LoginView,
    LogoutView,
    PostsListView,
    PostToneViewSet,
    PostTypeViewSet,
    PostViewSet,
    RefreshTokenView,
    ScheduleListView,
    ScheduleViewSet,
    SocialAccountViewSet,
    SEOKeywordSetViewSet,
    StoryViewSet,
    TelegramAuthView,
    TopicViewSet,
    TrendItemViewSet,
    TgChannelView,
)

app_name = 'api'

# DRF Router for ViewSets
router = DefaultRouter()
router.register(r'posts', PostViewSet, basename='post')
router.register(r'topics', TopicViewSet, basename='topic')
router.register(r'trends', TrendItemViewSet, basename='trend')
router.register(r'stories', StoryViewSet, basename='story')
router.register(r'templates', ContentTemplateViewSet, basename='template')
router.register(r'schedules-manage', ScheduleViewSet, basename='schedule-manage')
router.register(r'social-accounts', SocialAccountViewSet, basename='social-account')
router.register(r'post-types', PostTypeViewSet, basename='post-type')
router.register(r'post-tones', PostToneViewSet, basename='post-tone')
router.register(r'seo-keywords', SEOKeywordSetViewSet, basename='seo-keyword')

urlpatterns = [
    # Analytics endpoint (must be before router to avoid conflicts)
    path('tg_channel/', TgChannelView.as_view(), name='tg_channel'),

    # Authentication endpoints
    path('auth/telegram', TelegramAuthView.as_view(), name='telegram-auth'),
    path('auth/token/', LoginView.as_view(), name='token'),
    path('auth/refresh/', RefreshTokenView.as_view(), name='refresh'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),

    # Client endpoints
    path('client/info/', ClientInfoView.as_view(), name='client-info'),
    path('client/summary/', ClientSummaryView.as_view(), name='client-summary'),
    path('client/settings/', ClientSettingsView.as_view(), name='client-settings'),

    # Legacy list views (kept for backward compatibility)
    path('posts-list/', PostsListView.as_view(), name='posts-list'),
    path('schedules/', ScheduleListView.as_view(), name='schedules'),

    # Include router URLs
    path('', include(router.urls)),
]
