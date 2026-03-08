from __future__ import annotations

"""
API views public surface.

This module re-exports view classes from smaller `views_*.py` modules to keep
`api/urls.py` stable while the monolithic legacy module is being split.
"""

# Non-extracted views (still live in the legacy module).
from .views_misc import (  # noqa: F401
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
    RefreshTokenView,
    ScheduleListView,
    ScheduleViewSet,
    ProjectSemanticSetViewSet,
    SemanticClusterViewSet,
    SemanticGroupViewSet,
    SEOKeywordSetViewSet,
    SocialAccountViewSet,
    ProjectChannelAnalysisRunView,
    ProjectChannelAnalysisRunViewSet,
    StoryViewSet,
    TelegramTaskListView,
    CRMTaskListCreateView,
    CRMTaskDetailView,
    CRMTaskHistoryListCreateView,
    TelegramAuthView,
    TopicViewSet,
    TrendItemViewSet,
    VkCallbackView,
    VkConnectView,
    VkIntegrationViewSet,
    VkPublishView,
    WeeklySourceBatchViewSet,
    WeeklySourceReportViewSet,
    WeeklySourceRunView,
    WordstatClusterViewSet,
    WordstatQueryViewSet,
    WordstatResultViewSet,
)

# Extracted modules (overrides legacy implementations).
from .views_posts import PostsListView, PostToneViewSet, PostTypeViewSet, PostViewSet, WeeklyContentStrategyViewSet  # noqa: F401
from .views_products import (  # noqa: F401
    ClientProductViewSet,
    MindMapViewSet,
    MindNodePositionView,
    MindNodePropertyViewSet,
    ProductTypeViewSet,
    WeeklySalesPlanViewSet,
)
from .views_social import DzenRSSFeedView, TgChannelView  # noqa: F401
from .views_tgstat import (  # noqa: F401
    TgstatCategoryListView,
    TgstatChannelListView,
    TgstatFavoritesView,
    TgstatRecommendationsView,
    TgstatTagListView,
)
from .views_websites import WebsiteScanViewSet  # noqa: F401
from .views_kb import (  # noqa: F401
    KbFolderViewSet,
    KbDocumentViewSet,
    KbCommentViewSet,
    KbDocumentShareViewSet,
    KbTagViewSet,
    KbSearchViewSet,
    KbLinkPreviewView,
)
from .views_google import (  # noqa: F401
    GoogleCSESearchView,
    GoogleCompetitorsAnalyzeView,
    GoogleCompetitorsStoreView,
    GoogleCompetitorsSitesView,
    GoogleCompetitorsResolveView,
    GoogleCompetitorsMarkView,
    GoogleCompetitorsCachedView,
)
from .views_payments import (  # noqa: F401
    YooKassaCreatePaymentView,
    YooKassaCreatePaymentLinkView,
    YooKassaPaymentStatusView,
    PaymentPlanListView,
    PaymentPromoCodeApplyView,
    PaymentSubscriptionView,
    PaymentProvidersView,
    YooKassaWebhookView,
    YooKassaOAuthRedirectView,
    YooKassaOAuthCallbackView,
    YooKassaOAuthDisconnectView,
    YooKassaSaveCredentialsView,
    TBankSaveCredentialsView,
)
from .views_vk_auth import VkAuthUrlView, VkAuthView  # noqa: F401
from .views_vk_messages import VkMessageCallbackView  # noqa: F401
from .views_social_accounts import SocialAccountsView, LinkVkView, LinkTelegramView, UnlinkView, ResolveConflictView  # noqa: F401
from .views_messaging import ClientChannelView  # noqa: F401
from .views_unified_inbox import (  # noqa: F401
    EmailInboxWebhookView,
    UnifiedInboxCourseAcceptView,
    UnifiedInboxReplyView,
    UnifiedInboxThreadsView,
)
