from __future__ import annotations

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle

from api.utils import get_active_client


class _BaseTeamInvitationThrottle(SimpleRateThrottle):
    def get_rate(self):
        rates = getattr(settings, "REST_FRAMEWORK", {}).get("DEFAULT_THROTTLE_RATES", {})
        if not self.scope or self.scope not in rates:
            return None
        return rates[self.scope]

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None

        try:
            client = get_active_client(user)
        except Exception:
            return None

        return self.cache_format % {
            "scope": self.scope,
            "ident": f"{user.pk}:{client.id}",
        }


class TeamInvitationMinuteThrottle(_BaseTeamInvitationThrottle):
    scope = "team_invitation_minute"


class TeamInvitationDayThrottle(_BaseTeamInvitationThrottle):
    scope = "team_invitation_day"
