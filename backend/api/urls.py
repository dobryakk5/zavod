from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ArticleViewSet,
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
    ProjectChannelAnalysisRunView,
    ProjectChannelAnalysisRunViewSet,
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
    ClientProductViewSet,
    ProductTypeViewSet,
    MindMapViewSet,
    MindNodePositionView,
    MindNodePropertyViewSet,
    WeeklySourceReportViewSet,
    WeeklySourceRunView,
    WeeklySourceBatchViewSet,
    WordstatQueryViewSet,
    WordstatClusterViewSet,
    WordstatResultViewSet,
    WebsiteScanViewSet,
    GoogleCSESearchView,
    GoogleCompetitorsAnalyzeView,
    GoogleCompetitorsStoreView,
    GoogleCompetitorsSitesView,
    GoogleCompetitorsResolveView,
    GoogleCompetitorsMarkView,
    GoogleCompetitorsCachedView,
)

app_name = 'api'

# DRF Router for ViewSets
router = DefaultRouter()
router.register(r'posts', PostViewSet, basename='post')
router.register(r'topics', TopicViewSet, basename='topic')
router.register(r'trends', TrendItemViewSet, basename='trend')
router.register(r'stories', StoryViewSet, basename='story')
router.register(r'articles', ArticleViewSet, basename='article')
router.register(r'templates', ContentTemplateViewSet, basename='template')
router.register(r'schedules-manage', ScheduleViewSet, basename='schedule-manage')
router.register(r'social-accounts', SocialAccountViewSet, basename='social-account')
router.register(r'post-types', PostTypeViewSet, basename='post-type')
router.register(r'post-tones', PostToneViewSet, basename='post-tone')
router.register(r'seo-keywords', SEOKeywordSetViewSet, basename='seo-keyword')
router.register(r'wordstat', WordstatQueryViewSet, basename='wordstat')
router.register(r'wordstat-clusters', WordstatClusterViewSet, basename='wordstat-cluster')
router.register(r'wordstat-results', WordstatResultViewSet, basename='wordstat-result')
router.register(r'channel-analyses', ChannelAnalysisViewSet, basename='channel-analysis')
router.register(r'project-analyses', ProjectChannelAnalysisRunViewSet, basename='project-analysis')
router.register(r'vk/integrations', VkIntegrationViewSet, basename='vk-integration')
router.register(r'weekly-sources', WeeklySourceReportViewSet, basename='weekly-sources')
router.register(r'weekly-batches', WeeklySourceBatchViewSet, basename='weekly-batches')
router.register(r'website-scans', WebsiteScanViewSet, basename='website-scan')
router.register(r'map/node-properties', MindNodePropertyViewSet, basename='mind-node-property')
router.register(r'map/mind-maps', MindMapViewSet, basename='mind-map')
router.register(r'products/list', ClientProductViewSet, basename='client-product')
router.register(r'products/types', ProductTypeViewSet, basename='product-type')

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
    path('project-analyses/run/', ProjectChannelAnalysisRunView.as_view(), name='project-analyses-run'),

    # Google
    path('google/cse-search/', GoogleCSESearchView.as_view(), name='google-cse-search'),
    path('google/competitors/analyze/', GoogleCompetitorsAnalyzeView.as_view(), name='google-competitors-analyze'),
    path('google/competitors/store/', GoogleCompetitorsStoreView.as_view(), name='google-competitors-store'),
    path('google/competitors/sites/', GoogleCompetitorsSitesView.as_view(), name='google-competitors-sites'),
    path('google/competitors/resolve/', GoogleCompetitorsResolveView.as_view(), name='google-competitors-resolve'),
    path('google/competitors/cached/', GoogleCompetitorsCachedView.as_view(), name='google-competitors-cached'),
    path('google/competitors/mark/', GoogleCompetitorsMarkView.as_view(), name='google-competitors-mark'),

    # Legacy list views (kept for backward compatibility)
    path('posts-list/', PostsListView.as_view(), name='posts-list'),
    path('schedules/', ScheduleListView.as_view(), name='schedules'),

    # Public RSS feed for Yandex Zen
    path('rss/<slug:client_slug>.xml', DzenRSSFeedView.as_view(), name='api-rss-feed'),

    # VK integration endpoints
    path('vk/connect/', VkConnectView.as_view(), name='vk-connect'),
    path('vk/callback/', VkCallbackView.as_view(), name='vk-callback'),
    path('vk/post_with_photos/', VkPublishView.as_view(), name='vk-post-with-photos'),

    # Mind map endpoints
    path('map/nodes/<uuid:node_id>/position/', MindNodePositionView.as_view(), name='mind-node-position'),

    # Include router URLs
    path('', include(router.urls)),
]
