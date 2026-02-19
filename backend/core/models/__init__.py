# flake8: noqa
# isort: skip_file
"""
Пакет core/models/

Все существующие импорты вида:
    from core.models import Client, Post, ...
продолжают работать без изменений.

Порядок импортов важен из-за зависимостей между модулями.
"""

# --- Mixins (без зависимостей) ---
from ._mixins import TaskStatusMixin

# --- Core entities ---
from .payments import PaymentPlan, YooKassaPayment
from .client import Client, UserTenantRole

# --- CRM ---
from .crm import ClientCategory, CRMClient, Event, EventType, Payment, Note

# --- Integrations ---
from .integrations import VkIntegration, SocialAccount, Connection, UserSocialAccount

# --- Content ---
from .story import Topic, TrendItem, Story
from .content_template import (
    PostType,
    PostTone,
    ContentTemplateQuerySet,
    ContentTemplateManager,
    ContentTemplate,
)
from .content import PostJob, Post, PostImage, PostVideo, VeoVideoExport, Schedule

# --- Articles ---
from .article import Article, ArticleBlock, ArticleBlockPromptTemplate, Articles

# --- SEO & Semantics ---
from .seo import (
    SEOKeywordSet,
    ProjectSemanticSet,
    SemanticGroup,
    SemanticCluster,
    WordstatPhrase,
    SemanticPhrase,
    ClusterPhrase,
)
from .wordstat import WordstatQuery, WordstatCluster, WordstatResult

# --- Website & analysis ---
from .website import WebsiteScan, WebsiteScanPage, WebsiteScanPageContent, CompetitorSite
from .weekly import (
    ChannelAnalysis,
    ProjectChannelAnalysisRun,
    ProjectChannelPostStat,
    WeeklySourceReport,
    WeeklySourceBatch,
    WeeklySalesPlan,
    WeeklyContentStrategy,
)

# --- System ---
from .system import SystemSetting, GeneratorPrompt, GenerationEvent

# --- Map CRM (map.* schema, managed=False) ---
from .map_crm import (
    MapContact,
    MapCRMPayment,
    MapCRMTag,
    MapContactTag,
    MapCRMCategory,
    MapCRMEventType,
    MapCRMEvent,
    MapAvailabilityEvent,
    MapCRMNote,
)

# --- Unmanaged (managed=False, map.* и chains.*) ---
from .unmanaged import (
    ProductType,
    ClientProduct,
    MindMap,
    MindMapMember,
    MindNode,
    MindEdge,
    MindNodeProperty,
    MindNodePosition,
    KbFolder,
    KbDocument,
    KbDocumentVersion,
    KbComment,
    KbTag,
    KbDocumentTag,
    KbDocumentShare,
    Chain,
    ChainNode,
    ChainEdge,
    ChainCondition,
    ChainSession,
    UserTenantBinding,
    TelegramTask,
    CRMTask,
    CRMTaskHistory,
)

# --- Referral ---
from core.referral import ReferralCode, Referral, ReferralFirstPayment

__all__ = [
    # Mixins
    "TaskStatusMixin",
    # Client
    "Client",
    "UserTenantRole",
    # Payments
    "PaymentPlan",
    "YooKassaPayment",
    # CRM
    "ClientCategory",
    "CRMClient",
    "Event",
    "EventType",
    "Payment",
    "Note",
    # Integrations
    "VkIntegration",
    "SocialAccount",
    "Connection",
    "UserSocialAccount",
    # Story / Topics
    "Topic",
    "TrendItem",
    "Story",
    # Content templates
    "PostType",
    "PostTone",
    "ContentTemplateQuerySet",
    "ContentTemplateManager",
    "ContentTemplate",
    # Content
    "PostJob",
    "Post",
    "PostImage",
    "PostVideo",
    "VeoVideoExport",
    "Schedule",
    # Articles
    "Article",
    "ArticleBlock",
    "ArticleBlockPromptTemplate",
    "Articles",
    # SEO
    "SEOKeywordSet",
    "ProjectSemanticSet",
    "SemanticGroup",
    "SemanticCluster",
    "WordstatPhrase",
    "SemanticPhrase",
    "ClusterPhrase",
    # Wordstat
    "WordstatQuery",
    "WordstatCluster",
    "WordstatResult",
    # Website
    "WebsiteScan",
    "WebsiteScanPage",
    "WebsiteScanPageContent",
    "CompetitorSite",
    # Weekly / Channel
    "ChannelAnalysis",
    "ProjectChannelAnalysisRun",
    "ProjectChannelPostStat",
    "WeeklySourceReport",
    "WeeklySourceBatch",
    "WeeklySalesPlan",
    "WeeklyContentStrategy",
    # System
    "SystemSetting",
    "GeneratorPrompt",
    "GenerationEvent",
    # Map CRM
    "MapContact",
    "MapCRMPayment",
    "MapCRMTag",
    "MapContactTag",
    "MapCRMCategory",
    "MapCRMEventType",
    "MapCRMEvent",
    "MapAvailabilityEvent",
    "MapCRMNote",
    # Unmanaged
    "ProductType",
    "ClientProduct",
    "MindMap",
    "MindMapMember",
    "MindNode",
    "MindEdge",
    "MindNodeProperty",
    "MindNodePosition",
    "KbFolder",
    "KbDocument",
    "KbDocumentVersion",
    "KbComment",
    "KbTag",
    "KbDocumentTag",
    "KbDocumentShare",
    "Chain",
    "ChainNode",
    "ChainEdge",
    "ChainCondition",
    "ChainSession",
    "UserTenantBinding",
    "TelegramTask",
    "CRMTask",
    "CRMTaskHistory",
    # Referral
    "ReferralCode",
    "Referral",
    "ReferralFirstPayment",
]
