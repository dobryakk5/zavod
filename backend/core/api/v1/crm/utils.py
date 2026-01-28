from datetime import datetime, timedelta
from django.db.models import Q, Count, Sum
from core.models import CRMClient, Event, Payment, Note


def get_crm_statistics(zavod_client, start_date=None, end_date=None):
    """
    Получить статистику по CRM данным
    
    Args:
        zavod_client: Объект Zavod клиента
        start_date: Начальная дата для фильтрации (опционально)
        end_date: Конечная дата для фильтрации (опционально)
    
    Returns:
        dict: Словарь со статистикой
    """
    # Фильтр по дате, если указан
    date_filter = Q()
    if start_date:
        date_filter &= Q(created_at__gte=start_date)
    if end_date:
        date_filter &= Q(created_at__lte=end_date)
    
    # Статистика по клиентам
    clients_qs = CRMClient.objects.filter(zavod_client=zavod_client)
    clients_stats = {
        'total': clients_qs.count(),
        'active': clients_qs.filter(status='active').count(),
        'inactive': clients_qs.filter(status='inactive').count(),
        'archived': clients_qs.filter(status='archived').count(),
    }
    
    # Статистика по событиям
    events_qs = Event.objects.filter(client__zavod_client=zavod_client)
    if start_date or end_date:
        if start_date:
            events_qs = events_qs.filter(start_time__gte=start_date)
        if end_date:
            events_qs = events_qs.filter(start_time__lte=end_date)
    
    events_stats = {
        'total': events_qs.count(),
        'scheduled': events_qs.filter(status='scheduled').count(),
        'completed': events_qs.filter(status='completed').count(),
        'cancelled': events_qs.filter(status='cancelled').count(),
        'no_show': events_qs.filter(status='no_show').count(),
    }
    
    # Статистика по платежам
    payments_qs = Payment.objects.filter(client__zavod_client=zavod_client)
    if start_date or end_date:
        if start_date:
            payments_qs = payments_qs.filter(created_at__gte=start_date)
        if end_date:
            payments_qs = payments_qs.filter(created_at__lte=end_date)
    
    payments_stats = {
        'total_count': payments_qs.count(),
        'paid_count': payments_qs.filter(status='paid').count(),
        'pending_count': payments_qs.filter(status='pending').count(),
        'total_amount': float(payments_qs.filter(status='paid').aggregate(
            total=Sum('amount')
        )['total'] or 0),
        'paid_amount': float(payments_qs.filter(status='paid').aggregate(
            total=Sum('amount')
        )['total'] or 0),
        'pending_amount': float(payments_qs.filter(status='pending').aggregate(
            total=Sum('amount')
        )['total'] or 0),
    }
    
    # Статистика по заметкам
    notes_qs = Note.objects.filter(client__zavod_client=zavod_client)
    if start_date or end_date:
        if start_date:
            notes_qs = notes_qs.filter(created_at__gte=start_date)
        if end_date:
            notes_qs = notes_qs.filter(created_at__lte=end_date)
    
    notes_stats = {
        'total': notes_qs.count(),
        'important': notes_qs.filter(is_important=True).count(),
    }
    
    return {
        'clients': clients_stats,
        'events': events_stats,
        'payments': payments_stats,
        'notes': notes_stats,
        'period_start': start_date.isoformat() if start_date else None,
        'period_end': end_date.isoformat() if end_date else None,
    }


def get_upcoming_events(zavod_client, days=7):
    """
    Получить предстоящие события для клиента
    
    Args:
        zavod_client: Объект Zavod клиента
        days: Количество дней в будущем для поиска (по умолчанию 7)
    
    Returns:
        QuerySet: События в ближайшие дни
    """
    from django.utils import timezone
    now = timezone.now()
    end_date = now + timedelta(days=days)
    
    return Event.objects.filter(
        client__zavod_client=zavod_client,
        start_time__gte=now,
        start_time__lte=end_date,
        status='scheduled'
    ).select_related('client', 'event_type').order_by('start_time')


def get_client_lifetime_value(client):
    """
    Рассчитать Lifetime Value клиента (общую сумму его платежей)
    
    Args:
        client: Объект CRMClient
    
    Returns:
        float: Общая сумма платежей клиента
    """
    total_paid = client.payments.filter(status='paid').aggregate(
        total=Sum('amount')
    )['total']
    
    return float(total_paid or 0)


def get_revenue_by_period(zavod_client, period='month'):
    """
    Получить выручку по периодам
    
    Args:
        zavod_client: Объект Zavod клиента
        period: Период ('day', 'week', 'month', 'quarter', 'year')
    
    Returns:
        list: Список словарей с датой и суммой
    """
    from django.db.models import DateField
    from django.db.models.functions import Trunc
    
    payments = Payment.objects.filter(
        client__zavod_client=zavod_client,
        status='paid'
    )
    
    # Определяем функцию для тронирования даты в зависимости от периода
    if period == 'day':
        date_trunc = Trunc('paid_at', 'day', output_field=DateField())
    elif period == 'week':
        date_trunc = Trunc('paid_at', 'week', output_field=DateField())
    elif period == 'month':
        date_trunc = Trunc('paid_at', 'month', output_field=DateField())
    elif period == 'quarter':
        date_trunc = Trunc('paid_at', 'quarter', output_field=DateField())
    elif period == 'year':
        date_trunc = Trunc('paid_at', 'year', output_field=DateField())
    else:
        raise ValueError(f"Неподдерживаемый период: {period}")
    
    revenue_by_period = payments.annotate(
        period_date=date_trunc
    ).values(
        'period_date'
    ).annotate(
        total_revenue=Sum('amount')
    ).order_by('period_date')
    
    return [
        {
            'date': item['period_date'].isoformat(),
            'revenue': float(item['total_revenue'])
        }
        for item in revenue_by_period
    ]