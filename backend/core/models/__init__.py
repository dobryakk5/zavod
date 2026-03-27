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
from .payments import ContactProductPurchase, ContactProductServiceUsage, PaymentPlan, YooKassaPayment
from .client import Client, ProjectTeamInvite, UserActiveClientPreference, UserTenantRole

# --- CRM ---
from .crm import ClientCategory, CRMClient, Event, EventType, Payment, Note
from .amocrm import AmoCRMAccount, AmoCRMContactMapping, AmoCRMLogEntry
from .bitrix24 import Bitrix24Account, Bitrix24ContactMapping, Bitrix24LogEntry, Bitrix24WebhookEvent
from .coaching import ContactCoachingProfile

# --- Integrations ---
from .integrations import VkIntegration, SocialAccount, Connection, UserSocialAccount

# --- Messaging / Inbox ---
from .inbox import InboxEmailMessage, InboxReplyMessage

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
    MapCRMDeal,
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
    ProductCourse,
    ProductCourseModule,
    ProductCourseLesson,
    ProductCourseProgress,
    ProductCourseEvent,
    ProductCourseComment,
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
    Quiz,
    QuizScreen,
    QuizOption,
    QuizResultRule,
    QuizResultCondition,
    QuizAnswer,
    UserTenantBinding,
    ContactFact,
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
    "ProjectTeamInvite",
    "UserActiveClientPreference",
    "UserTenantRole",
    # Payments
    "PaymentPlan",
    "YooKassaPayment",
    "ContactProductPurchase",
    "ContactProductServiceUsage",
    # CRM
    "ClientCategory",
    "CRMClient",
    "Event",
    "EventType",
    "Payment",
    "Note",
    "AmoCRMAccount",
    "AmoCRMContactMapping",
    "AmoCRMLogEntry",
    "Bitrix24Account",
    "Bitrix24ContactMapping",
    "Bitrix24LogEntry",
    "Bitrix24WebhookEvent",
    "ContactCoachingProfile",
    # Integrations
    "VkIntegration",
    "SocialAccount",
    "Connection",
    "UserSocialAccount",
    "InboxEmailMessage",
    "InboxReplyMessage",
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
    "MapCRMDeal",
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
    "ProductCourse",
    "ProductCourseModule",
    "ProductCourseLesson",
    "ProductCourseProgress",
    "ProductCourseEvent",
    "ProductCourseComment",
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
    "Quiz",
    "QuizScreen",
    "QuizOption",
    "QuizResultRule",
    "QuizResultCondition",
    "QuizAnswer",
    "UserTenantBinding",
    "ContactFact",
    "TelegramTask",
    "CRMTask",
    "CRMTaskHistory",
    # Referral
    "ReferralCode",
    "Referral",
    "ReferralFirstPayment",
]
