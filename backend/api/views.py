from __future__ import annotations

"""
API views public surface.

This module re-exports view classes from smaller `views_*.py` modules to keep
`api/urls.py` stable while the monolithic legacy module is being split.
"""

# Non-extracted views (still live in the legacy module).
from .views_misc import (  # noqa: F401
    ChannelAnalysisViewSet,
    ClientExpertBooksView,
    ClientInfoView,
    ClientSettingsView,
    ClientSummaryView,
    ContentTemplateViewSet,
    LoginView,
    LogoutView,
    RefreshTokenView,
    ScheduleListView,
    ScheduleViewSet,
    SEOKeywordSetViewSet,
    SocialAccountViewSet,
    StoryViewSet,
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
    WordstatQueryViewSet,
    WordstatResultViewSet,
)

# Extracted modules (overrides legacy implementations).
from .views_posts import PostsListView, PostToneViewSet, PostTypeViewSet, PostViewSet  # noqa: F401
from .views_products import (  # noqa: F401
    ClientProductViewSet,
    MindMapViewSet,
    MindNodePositionView,
    MindNodePropertyViewSet,
    ProductTypeViewSet,
)
from .views_social import DzenRSSFeedView, TgChannelView  # noqa: F401
from .views_websites import WebsiteScanViewSet  # noqa: F401
from .views_google import GoogleCSESearchView  # noqa: F401
