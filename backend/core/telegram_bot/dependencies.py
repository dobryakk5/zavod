from core.services.telegram_user_service import TelegramUserService
from core.services.tenant_service import TenantService


_telegram_user_service: TelegramUserService | None = None
_tenant_service: TenantService | None = None


def init_dependencies() -> None:
    """Initialize services once at bot startup."""
    global _telegram_user_service, _tenant_service
    _telegram_user_service = TelegramUserService()
    _tenant_service = TenantService()


def get_telegram_user_service() -> TelegramUserService:
    if _telegram_user_service is None:
        return TelegramUserService()
    return _telegram_user_service


def get_tenant_service() -> TenantService:
    if _tenant_service is None:
        return TenantService()
    return _tenant_service
