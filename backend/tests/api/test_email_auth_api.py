import pytest
from django.urls import reverse
from rest_framework import status

from backend.api.email_auth import EmailAuthStorageUnavailableError


@pytest.mark.django_db
def test_send_magic_link_returns_503_when_email_auth_storage_is_unavailable(api_client, monkeypatch):
    def raise_storage_unavailable(email: str):
        raise EmailAuthStorageUnavailableError("storage unavailable")

    monkeypatch.setattr("backend.api.views_email_auth.issue_email_auth_token", raise_storage_unavailable)

    response = api_client.post(
        reverse("email-magic-link-send"),
        {"email": "user@example.com"},
        format="json",
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "временно недоступен" in response.data["detail"].lower()
