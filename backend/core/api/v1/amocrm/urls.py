from django.urls import path

from core.api.v1.amocrm.views import (
    AmoCRMAccountStatusView,
    AmoCRMLogsView,
    AmoCRMOAuthCallbackView,
    AmoCRMOAuthStartView,
    AmoCRMResyncAllView,
    AmoCRMResyncOneView,
    AmoCRMWebhookView,
)

urlpatterns = [
    path("oauth/start/", AmoCRMOAuthStartView.as_view(), name="amocrm-oauth-start"),
    path("oauth/callback/", AmoCRMOAuthCallbackView.as_view(), name="amocrm-oauth-callback"),
    path("webhook/<uuid:webhook_secret>/", AmoCRMWebhookView.as_view(), name="amocrm-webhook"),
    path("account/", AmoCRMAccountStatusView.as_view(), name="amocrm-account-status"),
    path("logs/", AmoCRMLogsView.as_view(), name="amocrm-logs"),
    path("resync/contacts/", AmoCRMResyncAllView.as_view(), name="amocrm-resync-all"),
    path("resync/contacts/<int:crm_client_id>/", AmoCRMResyncOneView.as_view(), name="amocrm-resync-one"),
]

