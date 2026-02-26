import logging

from celery import shared_task

from core.models import AmoCRMAccount, CRMClient
from core.services.crm.amocrm import AmoCRMAPIError, AmoCRMConfigError, AmoCRMService, log_amocrm_event

logger = logging.getLogger(__name__)

RETRYABLE_HTTP_CODES = {401, 408, 409, 425, 429, 500, 502, 503, 504}


def _maybe_retry(task, exc: Exception):
    if not hasattr(task, "retry"):
        raise exc
    if not isinstance(exc, AmoCRMAPIError):
        raise exc
    if exc.status_code not in RETRYABLE_HTTP_CODES:
        raise exc
    raise task.retry(exc=exc, countdown=min(300, 10 * (2 ** task.request.retries)))


@shared_task(bind=True, name="core.tasks.amocrm.sync_crm_client_to_amocrm_contact")
def sync_crm_client_to_amocrm_contact_task(self, account_id: int, crm_client_id: int, force: bool = False) -> dict:
    service = AmoCRMService()
    account = AmoCRMAccount.objects.filter(id=account_id).first()
    crm_client = CRMClient.objects.filter(id=crm_client_id).first()

    if not account or not crm_client:
        logger.warning("amoCRM sync skipped: account=%s crm_client=%s not found", account_id, crm_client_id)
        return {"status": "skipped", "reason": "not_found"}

    try:
        return service.sync_crm_client_to_amocrm(account=account, crm_client=crm_client, force=force)
    except (AmoCRMAPIError, AmoCRMConfigError) as exc:
        log_amocrm_event(
            account=account,
            crm_client=crm_client,
            source="sync",
            action="contact_push_task",
            level="error",
            status="error",
            message=str(exc),
            payload=getattr(exc, "response_body", None),
            error_code=str(getattr(exc, "status_code", "") or ""),
        )
        _maybe_retry(self, exc)
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected amoCRM sync task error (account=%s crm_client=%s)", account_id, crm_client_id)
        log_amocrm_event(
            account=account,
            crm_client=crm_client,
            source="sync",
            action="contact_push_task",
            level="error",
            status="error",
            message=str(exc),
        )
        raise


@shared_task(bind=True, name="core.tasks.amocrm.resync_all_crm_clients_to_amocrm")
def resync_all_crm_clients_to_amocrm_task(self, account_id: int, force: bool = True, limit: int | None = None) -> dict:
    account = AmoCRMAccount.objects.filter(id=account_id).first()
    if not account:
        logger.warning("amoCRM resync skipped: account=%s not found", account_id)
        return {"status": "skipped", "reason": "account_not_found"}

    service = AmoCRMService()
    try:
        result = service.resync_all_crm_clients(account=account, force=force, limit=limit)
        return {"status": "success", **result}
    except (AmoCRMAPIError, AmoCRMConfigError) as exc:
        log_amocrm_event(
            account=account,
            source="resync",
            action="resync_all_contacts_task",
            level="error",
            status="error",
            message=str(exc),
            payload=getattr(exc, "response_body", None),
            error_code=str(getattr(exc, "status_code", "") or ""),
        )
        _maybe_retry(self, exc)
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected amoCRM resync task error (account=%s)", account_id)
        log_amocrm_event(
            account=account,
            source="resync",
            action="resync_all_contacts_task",
            level="error",
            status="error",
            message=str(exc),
        )
        raise


@shared_task(bind=True, name="core.tasks.amocrm.process_contacts_webhook")
def process_amocrm_contacts_webhook_task(self, account_id: int, payload: dict) -> dict:
    account = AmoCRMAccount.objects.filter(id=account_id).first()
    if not account:
        logger.warning("amoCRM webhook task skipped: account=%s not found", account_id)
        return {"status": "skipped", "reason": "account_not_found"}

    service = AmoCRMService()
    try:
        return service.process_contact_webhook(account=account, payload=payload or {})
    except (AmoCRMAPIError, AmoCRMConfigError) as exc:
        log_amocrm_event(
            account=account,
            source="webhook",
            action="contacts_webhook_task",
            level="error",
            status="error",
            message=str(exc),
            payload=getattr(exc, "response_body", None) or payload,
            error_code=str(getattr(exc, "status_code", "") or ""),
        )
        _maybe_retry(self, exc)
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected amoCRM webhook task error (account=%s)", account_id)
        log_amocrm_event(
            account=account,
            source="webhook",
            action="contacts_webhook_task",
            level="error",
            status="error",
            message=str(exc),
            payload=payload,
        )
        raise

