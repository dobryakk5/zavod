from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ArticleViewSet,
    ChannelAnalysisViewSet,
    ClientBookSemanticsView,
    ClientExpertBooksView,
    GenerationEventSummaryView,
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
    ProjectSemanticSetViewSet,
    SemanticClusterViewSet,
    SemanticGroupViewSet,
    WeeklyContentStrategyViewSet,
    RefreshTokenView,
    ProjectChannelAnalysisRunView,
    ProjectChannelAnalysisRunViewSet,
    ScheduleListView,
    ScheduleViewSet,
    GoogleCSESearchView,
    GoogleCompetitorsAnalyzeView,
    GoogleCompetitorsStoreView,
    GoogleCompetitorsSitesView,
    GoogleCompetitorsResolveView,
    GoogleCompetitorsMarkView,
    GoogleCompetitorsCachedView,
    TelegramAuthView,
    TelegramTaskListView,
    YooKassaCreatePaymentView,
    YooKassaPaymentStatusView,
    PaymentPlanListView,
    PaymentPromoCodeApplyView,
    PaymentSubscriptionView,
    YooKassaWebhookView,
    YooKassaOAuthRedirectView,
    YooKassaOAuthCallbackView,
    YooKassaOAuthDisconnectView,
    YooKassaSaveCredentialsView,
    SocialAccountViewSet,
    SEOKeywordSetViewSet,
    StoryViewSet,
    TopicViewSet,
    TrendItemViewSet,
    WordstatQueryViewSet,
    WordstatClusterViewSet,
    WordstatResultViewSet,
    VkIntegrationViewSet,
    WeeklySourceReportViewSet,
    WeeklySourceBatchViewSet,
    WeeklySourceRunView,
    WeeklySalesPlanViewSet,
    WebsiteScanViewSet,
    MindNodePropertyViewSet,
    MindMapViewSet,
    MindNodePositionView,
    ClientProductViewSet,
    ProductTypeViewSet,
    VkCallbackView,
    VkConnectView,
    VkPublishView,
    KbFolderViewSet,
    KbDocumentViewSet,
    KbCommentViewSet,
    KbDocumentShareViewSet,
    KbTagViewSet,
    KbSearchViewSet,
    KbLinkPreviewView,
)

from .views_social import (
    DzenRSSFeedView,
    TgChannelView,
)
from .views_tgstat import (
    TgstatCategoryListView,
    TgstatChannelListView,
    TgstatFavoritesView,
    TgstatRecommendationsView,
    TgstatTagListView,
)

from .views_map_crm import (
    ContactsListView,
    ContactDetailView,
    ContactTelegramLinkView,
    TagsListView,
    TagDetailView,
    ContactTagsView,
    CategoriesListView,
    CategoryDetailView,
    EventTypesListView,
    EventTypeDetailView,
    EventsListView,
    EventDetailView,
    AvailabilityEventsListView,
    AvailabilityEventDetailView,
    PaymentsListView,
    PaymentDetailView,
    NotesListView,
    NoteDetailView,
)
from .views_chains import (
    CurrentChainView,
    CurrentChainGraphView,
    ChainNodesView,
    ChainNodeDetailView,
    ChainEdgesView,
    ChainEdgeDetailView,
    ChainEdgeConditionsView,
    ChainEdgeConditionDetailView,
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
router.register(r'content-strategy', WeeklyContentStrategyViewSet, basename='content-strategy')
router.register(r'semantic-groups', SemanticGroupViewSet, basename='semantic-group')
router.register(r'semantic-clusters', SemanticClusterViewSet, basename='semantic-cluster')
router.register(r'seo-keywords', SEOKeywordSetViewSet, basename='seo-keyword')
router.register(r'project-semantics', ProjectSemanticSetViewSet, basename='project-semantic-set')
router.register(r'wordstat', WordstatQueryViewSet, basename='wordstat')
router.register(r'wordstat-clusters', WordstatClusterViewSet, basename='wordstat-cluster')
router.register(r'wordstat-results', WordstatResultViewSet, basename='wordstat-result')
router.register(r'channel-analyses', ChannelAnalysisViewSet, basename='channel-analysis')
router.register(r'project-analyses', ProjectChannelAnalysisRunViewSet, basename='project-analysis')
router.register(r'vk/integrations', VkIntegrationViewSet, basename='vk-integration')
router.register(r'weekly-sources', WeeklySourceReportViewSet, basename='weekly-sources')
router.register(r'weekly-batches', WeeklySourceBatchViewSet, basename='weekly-batches')
router.register(r'weekly-sales', WeeklySalesPlanViewSet, basename='weekly-sales')
router.register(r'website-scans', WebsiteScanViewSet, basename='website-scan')
router.register(r'map/node-properties', MindNodePropertyViewSet, basename='mind-node-property')
router.register(r'map/mind-maps', MindMapViewSet, basename='mind-map')
router.register(r'products/list', ClientProductViewSet, basename='client-product')
router.register(r'products/types', ProductTypeViewSet, basename='product-type')
router.register(r'kb/folders', KbFolderViewSet, basename='kb-folder')
router.register(r'kb/documents', KbDocumentViewSet, basename='kb-document')
router.register(r'kb/comments', KbCommentViewSet, basename='kb-comment')
router.register(r'kb/shares', KbDocumentShareViewSet, basename='kb-share')
router.register(r'kb/tags', KbTagViewSet, basename='kb-tag')
router.register(r'kb/search', KbSearchViewSet, basename='kb-search')

urlpatterns = [
    # Analytics endpoint (must be before router to avoid conflicts)
    path('tg_channel/', TgChannelView.as_view(), name='tg_channel'),
    path('tgstat/categories/', TgstatCategoryListView.as_view(), name='tgstat-categories'),
    path('tgstat/tags/', TgstatTagListView.as_view(), name='tgstat-tags'),
    path('tgstat/channels/', TgstatChannelListView.as_view(), name='tgstat-channels'),
    path('tgstat/favorites/', TgstatFavoritesView.as_view(), name='tgstat-favorites'),
    path('tgstat/recommendations/', TgstatRecommendationsView.as_view(), name='tgstat-recommendations'),

    # Authentication endpoints
    path('auth/telegram', TelegramAuthView.as_view(), name='telegram-auth'),
    path('auth/token/', LoginView.as_view(), name='token'),
    path('auth/refresh/', RefreshTokenView.as_view(), name='refresh'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),

    # Client endpoints
    path('client/info/', ClientInfoView.as_view(), name='client-info'),
    path('client/summary/', ClientSummaryView.as_view(), name='client-summary'),
    path('client/generation-events/', GenerationEventSummaryView.as_view(), name='client-generation-events'),
    path('client/settings/', ClientSettingsView.as_view(), name='client-settings'),
    path('client/expert-books/', ClientExpertBooksView.as_view(), name='client-expert-books'),
    path('client/book-semantics/', ClientBookSemanticsView.as_view(), name='client-book-semantics'),

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

    # Payments
    path('payments/create/', YooKassaCreatePaymentView.as_view(), name='yookassa-create-payment'),
    path('payments/status/<str:payment_id>/', YooKassaPaymentStatusView.as_view(), name='yookassa-payment-status'),
    path('payments/plans/', PaymentPlanListView.as_view(), name='payment-plans'),
    path('payments/subscription/', PaymentSubscriptionView.as_view(), name='payment-subscription'),
    path('payments/promo/', PaymentPromoCodeApplyView.as_view(), name='payment-promo-apply'),
    path('payments/webhook/<uuid:client_uuid>/', YooKassaWebhookView.as_view(), name='yookassa-webhook-client'),
    path('payments/yookassa/connect/', YooKassaOAuthRedirectView.as_view(), name='yookassa-oauth-connect'),
    path('payments/yookassa/callback/', YooKassaOAuthCallbackView.as_view(), name='yookassa-oauth-callback'),
    path('payments/yookassa/disconnect/', YooKassaOAuthDisconnectView.as_view(), name='yookassa-oauth-disconnect'),
    path('payments/yookassa/credentials/', YooKassaSaveCredentialsView.as_view(), name='yookassa-credentials'),
    path('payments/webhook/', YooKassaWebhookView.as_view(), name='yookassa-webhook'),

    # Legacy list views (kept for backward compatibility)
    path('posts-list/', PostsListView.as_view(), name='posts-list'),
    path('schedules/', ScheduleListView.as_view(), name='schedules'),
    path('telegram-tasks/', TelegramTaskListView.as_view(), name='telegram-tasks'),

    # Public RSS feed for Yandex Zen
    path('rss/<slug:client_slug>.xml', DzenRSSFeedView.as_view(), name='api-rss-feed'),

    # VK integration endpoints
    path('vk/connect/', VkConnectView.as_view(), name='vk-connect'),
    path('vk/callback/', VkCallbackView.as_view(), name='vk-callback'),
    path('vk/post_with_photos/', VkPublishView.as_view(), name='vk-post-with-photos'),

    # Link preview endpoint for editor modal
    path('link-preview/', KbLinkPreviewView.as_view(), name='link-preview'),

    # Mind map endpoints
    path('map/nodes/<uuid:node_id>/position/', MindNodePositionView.as_view(), name='mind-node-position'),

    # CRM endpoints
    path('crm/contacts/', ContactsListView.as_view(), name='crm-contacts-list'),
    path('crm/contacts/<int:contact_id>/', ContactDetailView.as_view(), name='crm-contact-detail'),
    path('crm/contacts/<int:contact_id>/telegram-link/', ContactTelegramLinkView.as_view(), name='crm-contact-telegram-link'),
    path('crm/tags/', TagsListView.as_view(), name='crm-tags-list'),
    path('crm/tags/<int:tag_id>/', TagDetailView.as_view(), name='crm-tag-detail'),
    path('crm/contact-tags/', ContactTagsView.as_view(), name='crm-contact-tags'),
    path('crm/categories/', CategoriesListView.as_view(), name='crm-categories-list'),
    path('crm/categories/<int:category_id>/', CategoryDetailView.as_view(), name='crm-category-detail'),
    path('crm/event-types/', EventTypesListView.as_view(), name='crm-event-types-list'),
    path('crm/event-types/<int:event_type_id>/', EventTypeDetailView.as_view(), name='crm-event-type-detail'),
    path('crm/events/', EventsListView.as_view(), name='crm-events-list'),
    path('crm/events/<int:event_id>/', EventDetailView.as_view(), name='crm-event-detail'),
    path('crm/availability-events/', AvailabilityEventsListView.as_view(), name='crm-availability-events-list'),
    path('crm/availability-events/<int:event_id>/', AvailabilityEventDetailView.as_view(), name='crm-availability-event-detail'),
    path('crm/payments/', PaymentsListView.as_view(), name='crm-payments-list'),
    path('crm/payments/<int:payment_id>/', PaymentDetailView.as_view(), name='crm-payment-detail'),
    path('crm/notes/', NotesListView.as_view(), name='crm-notes-list'),
    path('crm/notes/<int:note_id>/', NoteDetailView.as_view(), name='crm-note-detail'),

    # Welcome chain endpoints (single chain per tenant)
    path('chains/current/', CurrentChainView.as_view(), name='chains-current'),
    path('chains/current/graph/', CurrentChainGraphView.as_view(), name='chains-current-graph'),
    path('chains/current/nodes/', ChainNodesView.as_view(), name='chains-current-nodes'),
    path('chains/current/nodes/<int:node_id>/', ChainNodeDetailView.as_view(), name='chains-current-node-detail'),
    path('chains/current/edges/', ChainEdgesView.as_view(), name='chains-current-edges'),
    path('chains/current/edges/<int:edge_id>/', ChainEdgeDetailView.as_view(), name='chains-current-edge-detail'),
    path('chains/current/edges/<int:edge_id>/conditions/', ChainEdgeConditionsView.as_view(), name='chains-current-edge-conditions'),
    path('chains/current/edges/<int:edge_id>/conditions/<int:condition_id>/', ChainEdgeConditionDetailView.as_view(), name='chains-current-edge-condition'),

    # Include router URLs
    path('', include(router.urls)),
]
