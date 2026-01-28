from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from core.models import CRMClient, Event, Payment, Note


# Сигналы для CRMClient
@receiver(post_save, sender=CRMClient)
def crm_client_saved(sender, instance, created, **kwargs):
    """
    Сигнал при сохранении CRM клиента
    """
    if created:
        # При создании клиента можно выполнить какие-то действия
        pass
    else:
        # При обновлении клиента
        pass


@receiver(pre_delete, sender=CRMClient)
def crm_client_deleted(sender, instance, **kwargs):
    """
    Сигнал перед удалением CRM клиента
    """
    # Можно выполнить очистку связанных данных
    pass


# Сигналы для Event
@receiver(post_save, sender=Event)
def event_saved(sender, instance, created, **kwargs):
    """
    Сигнал при сохранении события
    """
    if created:
        # При создании события можно отправить уведомление клиенту
        pass


@receiver(pre_delete, sender=Event)
def event_deleted(sender, instance, **kwargs):
    """
    Сигнал перед удалением события
    """
    # Можно выполнить очистку или уведомления
    pass


# Сигналы для Payment
@receiver(post_save, sender=Payment)
def payment_saved(sender, instance, created, **kwargs):
    """
    Сигнал при сохранении платежа
    """
    if created and instance.status == 'paid':
        # При успешной оплате можно обновить статус клиента или отправить уведомление
        pass


# Сигналы для Note
@receiver(post_save, sender=Note)
def note_saved(sender, instance, created, **kwargs):
    """
    Сигнал при сохранении заметки
    """
    if created and instance.is_important:
        # При создании важной заметки можно отправить уведомление
        pass