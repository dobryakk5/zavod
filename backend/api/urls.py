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
    VkAuthUrlView,
    VkAuthView,
    VkMessageCallbackView,
    SocialAccountsView,
    LinkVkView,
    LinkTelegramView,
    UnlinkView,
    ResolveConflictView,
    TelegramTaskListView,
    CRMTaskListCreateView,
    CRMTaskDetailView,
    CRMTaskHistoryListCreateView,
    YooKassaCreatePaymentView,
    YooKassaCreatePaymentLinkView,
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
    ClientChannelView,
    EmailInboxWebhookView,
    UnifiedInboxReplyView,
    UnifiedInboxThreadsView,
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

from .views_crm_orm import (
    ContactTelegramLinkView,
    MapContactViewSet,
    MapCRMDealViewSet,
    MapCRMPaymentViewSet,
    MapCRMTagViewSet,
    MapCRMCategoryViewSet,
    MapContactTagsViewSet,
    MapCRMEventTypeViewSet,
    MapCRMEventViewSet,
    MapAvailabilityEventViewSet,
    MapCRMNoteViewSet,
)
from .views_chains import (
    ChainsListView,
    CurrentChainView,
    CurrentChainGraphView,
    ChainNodesView,
    ChainNodeDetailView,
    ChainEdgesView,
    ChainEdgeDetailView,
    ChainEdgeConditionsView,
    ChainEdgeConditionDetailView,
)
from .views_public_client_page import (
    PublicClientPageBuyProductView,
    PublicClientPagePurchasesView,
    PublicClientPagePaymentStatusView,
    PublicClientPageView,
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

# CRM router (ORM для CRM сущностей map.*)
crm_router = DefaultRouter()
crm_router.register(r'contacts', MapContactViewSet, basename='crm-contact')
crm_router.register(r'deals', MapCRMDealViewSet, basename='crm-deal')
crm_router.register(r'payments', MapCRMPaymentViewSet, basename='crm-payment')
crm_router.register(r'tags', MapCRMTagViewSet, basename='crm-tag')
crm_router.register(r'categories', MapCRMCategoryViewSet, basename='crm-category')
crm_router.register(r'contact-tags', MapContactTagsViewSet, basename='crm-contact-tag')
crm_router.register(r'event-types', MapCRMEventTypeViewSet, basename='crm-event-type')
crm_router.register(r'events', MapCRMEventViewSet, basename='crm-event')
crm_router.register(r'availability-events', MapAvailabilityEventViewSet, basename='crm-availability-event')
crm_router.register(r'notes', MapCRMNoteViewSet, basename='crm-note')

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
    path('auth/vk', VkAuthView.as_view(), name='vk-auth'),
    path('auth/vk/url', VkAuthUrlView.as_view(), name='vk-auth-url'),
    path('auth/vk/messages/callback', VkMessageCallbackView.as_view(), name='vk-messages-callback'),
    path('auth/social/accounts', SocialAccountsView.as_view(), name='social-accounts'),
    path('auth/social/link/vk', LinkVkView.as_view(), name='social-link-vk'),
    path('auth/social/link/telegram', LinkTelegramView.as_view(), name='social-link-telegram'),
    path('auth/social/conflict/resolve', ResolveConflictView.as_view(), name='social-conflict-resolve'),
    path('auth/social/unlink/<str:provider>', UnlinkView.as_view(), name='social-unlink'),
    path('auth/token/', LoginView.as_view(), name='token'),
    path('auth/refresh/', RefreshTokenView.as_view(), name='refresh'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),

    # Client endpoints
    path('public/client-page/<int:client_id>/', PublicClientPageView.as_view(), name='public-client-page'),
    path('public/client-page/<int:client_id>/buy/', PublicClientPageBuyProductView.as_view(), name='public-client-page-buy'),
    path('public/client-page/<int:client_id>/payment-status/', PublicClientPagePaymentStatusView.as_view(), name='public-client-page-payment-status'),
    path('public/client-page/<int:client_id>/purchases/', PublicClientPagePurchasesView.as_view(), name='public-client-page-purchases'),
    path('client/info/', ClientInfoView.as_view(), name='client-info'),
    path('client/summary/', ClientSummaryView.as_view(), name='client-summary'),
    path('client/generation-events/', GenerationEventSummaryView.as_view(), name='client-generation-events'),
    path('client/settings/', ClientSettingsView.as_view(), name='client-settings'),
    path('client/channel', ClientChannelView.as_view(), name='client-channel'),
    path('client/unified-inbox/', UnifiedInboxThreadsView.as_view(), name='client-unified-inbox'),
    path('client/unified-inbox/reply/', UnifiedInboxReplyView.as_view(), name='client-unified-inbox-reply'),
    path('inbox/email/webhook/<uuid:client_uuid>/', EmailInboxWebhookView.as_view(), name='inbox-email-webhook'),
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
    path('payments/link/', YooKassaCreatePaymentLinkView.as_view(), name='yookassa-create-payment-link'),
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
    path('telegram-tasks/crm-tasks/', CRMTaskListCreateView.as_view(), name='telegram-crm-tasks'),
    path('telegram-tasks/crm-tasks/<int:task_id>/', CRMTaskDetailView.as_view(), name='telegram-crm-task-detail'),
    path('telegram-tasks/crm-tasks/<int:task_id>/history/', CRMTaskHistoryListCreateView.as_view(), name='telegram-crm-task-history'),

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

    # CRM endpoints: ORM для CRM сущностей
    path('crm/contacts/<int:contact_id>/telegram-link/', ContactTelegramLinkView.as_view(), name='crm-contact-telegram-link'),
    path('crm/', include(crm_router.urls)),

    # Chains / chatbot endpoints
    path('chains/', ChainsListView.as_view(), name='chains-list'),
    path('chains/current/', CurrentChainView.as_view(), name='chains-current'),
    path('chains/current/graph/', CurrentChainGraphView.as_view(), name='chains-current-graph'),
    path('chains/current/nodes/', ChainNodesView.as_view(), name='chains-current-nodes'),
    path('chains/current/nodes/<int:node_id>/', ChainNodeDetailView.as_view(), name='chains-current-node-detail'),
    path('chains/current/edges/', ChainEdgesView.as_view(), name='chains-current-edges'),
    path('chains/current/edges/<int:edge_id>/', ChainEdgeDetailView.as_view(), name='chains-current-edge-detail'),
    path('chains/current/edges/<int:edge_id>/conditions/', ChainEdgeConditionsView.as_view(), name='chains-current-edge-conditions'),
    path('chains/current/edges/<int:edge_id>/conditions/<int:condition_id>/', ChainEdgeConditionDetailView.as_view(), name='chains-current-edge-condition'),
    path('chains/<int:chain_id>/', CurrentChainView.as_view(), name='chains-detail'),
    path('chains/<int:chain_id>/graph/', CurrentChainGraphView.as_view(), name='chains-graph'),
    path('chains/<int:chain_id>/nodes/', ChainNodesView.as_view(), name='chains-nodes'),
    path('chains/<int:chain_id>/nodes/<int:node_id>/', ChainNodeDetailView.as_view(), name='chains-node-detail'),
    path('chains/<int:chain_id>/edges/', ChainEdgesView.as_view(), name='chains-edges'),
    path('chains/<int:chain_id>/edges/<int:edge_id>/', ChainEdgeDetailView.as_view(), name='chains-edge-detail'),
    path('chains/<int:chain_id>/edges/<int:edge_id>/conditions/', ChainEdgeConditionsView.as_view(), name='chains-edge-conditions'),
    path('chains/<int:chain_id>/edges/<int:edge_id>/conditions/<int:condition_id>/', ChainEdgeConditionDetailView.as_view(), name='chains-edge-condition'),

    # Include router URLs
    path('', include(router.urls)),
]
