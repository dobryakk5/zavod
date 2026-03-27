from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from core.models import (
    Client, ChannelAnalysis, ProjectChannelAnalysisRun, ProjectChannelPostStat,
    WebsiteScan, CompetitorSite, WebsiteScanPage, WebsiteScanPageContent,
    WeeklySourceReport, WeeklySourceBatch, WeeklySalesPlan, WeeklyContentStrategy,
    ProjectTeamInvite, UserActiveClientPreference, UserTenantRole, VkIntegration,
    SocialAccount, Connection, PostJob, Post,
    PostImage, PostVideo, VeoVideoExport, Schedule, Topic, TrendItem, Story,
    Article, ArticleBlock, ArticleBlockPromptTemplate, Articles, PostType,
    PostTone, ContentTemplate, SEOKeywordSet, ProjectSemanticSet, SemanticGroup,
    SemanticCluster, WordstatPhrase, SemanticPhrase, ClusterPhrase,
    WordstatQuery, WordstatCluster, WordstatResult, SystemSetting, GeneratorPrompt,
    PaymentPlan, GenerationEvent, ProductType, ClientProduct, MindMap,
    MindMapMember, MindNode, MindEdge, MindNodeProperty, MindNodePosition,
    TelegramTask
)
from core.models import CRMClient, ClientCategory, Event, EventType, Payment, Note


@admin.register(ClientCategory)
class ClientCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CRMClient)
class CRMClientAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'phone', 'category', 'status', 'zavod_client_link', 'created_at']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['first_name', 'last_name', 'email', 'phone', 'notes']
    readonly_fields = ['created_at', 'updated_at']
    
    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    full_name.short_description = 'Имя'
    
    def zavod_client_link(self, obj):
        if obj.zavod_client:
            return format_html(
                '<a href="/admin/core/client/{}/change/">{}</a>',
                obj.zavod_client.id,
                obj.zavod_client.name
            )
        return "-"
    zavod_client_link.short_description = 'Zavod клиент'


@admin.register(EventType)
class EventTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'duration_minutes', 'color', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'client_link', 'event_type', 'start_time', 'status', 'created_at']
    list_filter = ['status', 'event_type', 'start_time']
    search_fields = ['title', 'description', 'location']
    readonly_fields = ['created_at', 'updated_at']
    
    def client_link(self, obj):
        return format_html(
            '<a href="/admin/core/crmclient/{}/change/">{}</a>',
            obj.client.id,
            obj.client
        )
    client_link.short_description = 'Клиент'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['client_link', 'amount', 'currency', 'status', 'payment_method', 'paid_at', 'created_at']
    list_filter = ['status', 'currency', 'payment_method', 'paid_at', 'created_at']
    search_fields = ['transaction_id', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    def client_link(self, obj):
        return format_html(
            '<a href="/admin/core/crmclient/{}/change/">{}</a>',
            obj.client.id,
            obj.client
        )
    client_link.short_description = 'Клиент'


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ['title', 'client_link', 'is_important', 'created_at']
    list_filter = ['is_important', 'created_at']
    search_fields = ['title', 'content']
    readonly_fields = ['created_at', 'updated_at']
    
    def client_link(self, obj):
        return format_html(
            '<a href="/admin/core/crmclient/{}/change/">{}</a>',
            obj.client.id,
            obj.client
        )
    client_link.short_description = 'Клиент'


# Остальные регистрации админ-панели из оригинального кода
@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'niche', 'plan']
    list_filter = ['plan']
    search_fields = ['name', 'slug', 'niche']
    readonly_fields = []


@admin.register(UserTenantRole)
class UserTenantRoleAdmin(admin.ModelAdmin):
    list_display = ['user', 'client', 'role']
    list_filter = ['role', 'client']
    search_fields = ['user__username', 'user__email', 'client__name']


@admin.register(UserActiveClientPreference)
class UserActiveClientPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'client', 'updated_at']
    list_filter = ['client']
    search_fields = ['user__username', 'user__email', 'client__name']
    readonly_fields = ['updated_at']


@admin.register(ProjectTeamInvite)
class ProjectTeamInviteAdmin(admin.ModelAdmin):
    list_display = ['client', 'provider', 'account_handle_normalized', 'status', 'role', 'invited_by', 'accepted_user', 'created_at']
    list_filter = ['status', 'provider', 'role', 'client']
    search_fields = [
        'client__name',
        'client__slug',
        'account_handle_raw',
        'account_handle_normalized',
        'invited_by__username',
        'accepted_user__username',
    ]
    readonly_fields = ['created_at', 'accepted_at', 'revoked_at']


@admin.register(ChannelAnalysis)
class ChannelAnalysisAdmin(admin.ModelAdmin):
    list_display = ['client', 'channel_type', 'status', 'progress', 'created_at']
    list_filter = ['status', 'channel_type', 'created_at']
    search_fields = ['client__name', 'channel_url']


@admin.register(WebsiteScan)
class WebsiteScanAdmin(admin.ModelAdmin):
    list_display = ['client', 'base_url', 'status', 'progress', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['client__name', 'base_url']


@admin.register(CompetitorSite)
class CompetitorSiteAdmin(admin.ModelAdmin):
    list_display = ['client', 'domain', 'home_title', 'analysis_status', 'created_at']
    list_filter = ['analysis_status', 'created_at']
    search_fields = ['client__name', 'domain', 'home_title']


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['client', 'title', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['client__name', 'title', 'text']


@admin.register(ContentTemplate)
class ContentTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'type', 'tone', 'is_default', 'created_at']
    list_filter = ['type', 'tone', 'is_default', 'created_at']
    search_fields = ['name', 'client__name']


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['client', 'wordstat', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['client__name', 'wordstat']


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ['id', 'default_ai_model', 'post_ai_model', 'updated_at']
    
    def has_add_permission(self, request):
        # Только один экземпляр настроек
        return SystemSetting.objects.count() == 0
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GeneratorPrompt)
class GeneratorPromptAdmin(admin.ModelAdmin):
    list_display = ['code', 'group', 'created_at']
    list_filter = ['group', 'created_at']
    search_fields = ['code', 'comment']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PaymentPlan)
class PaymentPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'amount', 'currency', 'period', 'is_active']
    list_filter = ['is_active', 'currency', 'period']
    search_fields = ['name', 'code', 'description']


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'client__name']


@admin.register(TrendItem)
class TrendItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'topic', 'source', 'relevance_score', 'discovered_at']
    list_filter = ['source', 'discovered_at']
    search_fields = ['title', 'description', 'topic__name']
