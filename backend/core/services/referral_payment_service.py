import logging

from django.db import transaction

from core.referral import Referral, ReferralFirstPayment

logger = logging.getLogger(__name__)


def handle_succeeded_payment(yookassa_payment) -> ReferralFirstPayment | None:
    """
    Обрабатывает успешный платёж YooKassa и фиксирует первый платёж реферала.
    Возвращает созданный ReferralFirstPayment либо None.
    """
    client = yookassa_payment.client

    # Идемпотентность: этот payment_id уже обработан.
    if ReferralFirstPayment.objects.filter(yookassa_payment=yookassa_payment).exists():
        return None

    referral = (
        Referral.objects.select_related("referral_code", "referrer")
        .filter(
            referee=client,
            status__in=[Referral.STATUS_REGISTERED, Referral.STATUS_REWARDED],
        )
        .first()
    )

    if referral is None:
        return None

    # Идемпотентность: первый платёж по этому рефералу уже зафиксирован.
    if ReferralFirstPayment.objects.filter(referral=referral).exists():
        return None

    try:
        with transaction.atomic():
            first_payment = ReferralFirstPayment.objects.create(
                referral=referral,
                referrer=referral.referrer,
                referee=client,
                yookassa_payment=yookassa_payment,
                amount=yookassa_payment.amount,
                currency=getattr(yookassa_payment, "currency", "RUB"),
                plan_code=yookassa_payment.plan_code or "",
                paid_at=yookassa_payment.updated_at,
            )

            if referral.status != Referral.STATUS_REWARDED:
                referral.mark_rewarded()

            logger.info(
                "referral: first payment created referral_id=%s referee_id=%s yk_payment=%s",
                referral.id,
                client.id,
                yookassa_payment.payment_id,
            )
            return first_payment
    except Exception:
        logger.exception(
            "referral: failed to create first payment yk_payment=%s client_id=%s",
            yookassa_payment.payment_id,
            client.id,
        )
        return None
