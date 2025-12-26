from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ChannelAnalysisViewSet,
    ClientExpertBooksView,
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
    DzenRSSFeedView,
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
    VkIntegrationViewSet,
    VkConnectView,
    VkCallbackView,
    VkPublishView,
    WeeklySourceReportViewSet,
    WeeklySourceRunView,
    WeeklySourceBatchViewSet,
    WordstatQueryViewSet,
    WordstatResultViewSet,
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
router.register(r'wordstat', WordstatQueryViewSet, basename='wordstat')
router.register(r'wordstat-results', WordstatResultViewSet, basename='wordstat-result')
router.register(r'channel-analyses', ChannelAnalysisViewSet, basename='channel-analysis')
router.register(r'vk/integrations', VkIntegrationViewSet, basename='vk-integration')
router.register(r'weekly-sources', WeeklySourceReportViewSet, basename='weekly-sources')
router.register(r'weekly-batches', WeeklySourceBatchViewSet, basename='weekly-batches')

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
    path('client/expert-books/', ClientExpertBooksView.as_view(), name='client-expert-books'),
    path('weekly-sources/run/', WeeklySourceRunView.as_view(), name='weekly-sources-run'),

    # Legacy list views (kept for backward compatibility)
    path('posts-list/', PostsListView.as_view(), name='posts-list'),
    path('schedules/', ScheduleListView.as_view(), name='schedules'),

    # Public RSS feed for Yandex Zen
    path('rss/<slug:client_slug>.xml', DzenRSSFeedView.as_view(), name='api-rss-feed'),

    # VK integration endpoints
    path('vk/connect/', VkConnectView.as_view(), name='vk-connect'),
    path('vk/callback/', VkCallbackView.as_view(), name='vk-callback'),
    path('vk/post_with_photos/', VkPublishView.as_view(), name='vk-post-with-photos'),

    # Include router URLs
    path('', include(router.urls)),
]
