"""
Настройки для CRM API
"""
from django.conf import settings


# Максимальное количество записей на одной странице
CRM_API_MAX_PAGE_SIZE = getattr(settings, 'CRM_API_MAX_PAGE_SIZE', 100)

# Количество записей на странице по умолчанию
CRM_API_DEFAULT_PAGE_SIZE = getattr(settings, 'CRM_API_DEFAULT_PAGE_SIZE', 20)

# Время жизни JWT токенов (в днях)
CRM_API_JWT_LIFETIME_DAYS = getattr(settings, 'CRM_API_JWT_LIFETIME_DAYS', 7)

# Максимальный размер загружаемого файла (в байтах)
CRM_API_MAX_FILE_SIZE = getattr(settings, 'CRM_API_MAX_FILE_SIZE', 10 * 1024 * 1024)  # 10MB

# Разрешенные типы файлов для загрузки
CRM_API_ALLOWED_FILE_TYPES = getattr(settings, 'CRM_API_ALLOWED_FILE_TYPES', [
    'image/jpeg',
    'image/png',
    'image/gif',
    'application/pdf',
    'text/csv',
])

# Лимиты на API запросы
CRM_API_RATE_LIMITS = {
    'anon': '100/hour',  # для анонимных пользователей
    'user': '1000/hour',  # для аутентифицированных пользователей
    'client': '5000/hour',  # для клиентских приложений
}

# Поля, по которым можно фильтровать клиентов
CRM_CLIENT_SEARCH_FIELDS = getattr(settings, 'CRM_CLIENT_SEARCH_FIELDS', [
    'first_name',
    'last_name',
    'email',
    'phone',
    'notes',
])

# Поля, по которым можно фильтровать события
CRM_EVENT_SEARCH_FIELDS = getattr(settings, 'CRM_EVENT_SEARCH_FIELDS', [
    'title',
    'description',
    'location',
])

# Поля, по которым можно фильтровать платежи
CRM_PAYMENT_SEARCH_FIELDS = getattr(settings, 'CRM_PAYMENT_SEARCH_FIELDS', [
    'description',
    'transaction_id',
])

# Поля, по которым можно фильтровать заметки
CRM_NOTE_SEARCH_FIELDS = getattr(settings, 'CRM_NOTE_SEARCH_FIELDS', [
    'title',
    'content',
])

# Настройки пагинации
CRM_PAGINATION_SETTINGS = {
    'page_size': CRM_API_DEFAULT_PAGE_SIZE,
    'max_page_size': CRM_API_MAX_PAGE_SIZE,
    'page_size_query_param': 'page_size',
    'max_page_size_query_param': 'max_page_size',
}

# Поля, по которым можно сортировать
CRM_ORDERING_FIELDS = {
    'client': ['created_at', 'first_name', 'last_name', 'status'],
    'event': ['start_time', 'created_at', 'status'],
    'payment': ['created_at', 'paid_at', 'amount'],
    'note': ['created_at', 'is_important'],
    'category': ['name', 'created_at'],
}

# Допустимые статусы для фильтрации
CRM_ALLOWED_STATUSES = {
    'client': ['active', 'inactive', 'archived'],
    'event': ['scheduled', 'completed', 'cancelled', 'no_show'],
    'payment': ['pending', 'paid', 'failed', 'refunded'],
}

# Цвета по умолчанию для категорий
CRM_DEFAULT_CATEGORY_COLORS = [
    '#FFD700',  # Gold
    '#4A90E2',  # Blue
    '#50C878',  # Emerald
    '#FFA500',  # Orange
    '#9B59B6',  # Purple
    '#1ABC9C',  # Turquoise
    '#E74C3C',  # Red
    '#34495E',  # Wet Asphalt
]

# Цвета по умолчанию для типов событий
CRM_DEFAULT_EVENT_TYPE_COLORS = [
    '#4A90E2',  # Blue
    '#9B59B6',  # Purple
    '#50C878',  # Emerald
    '#F39C12',  # Orange
    '#E74C3C',  # Red
    '#1ABC9C',  # Turquoise
]