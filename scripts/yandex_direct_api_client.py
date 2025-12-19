"""
Yandex Direct API Client

Этот модуль реализует клиент для работы с Yandex Direct API с соблюдением всех требований:
- Правильная обработка ошибок
- Учет ограничений API (rate limiting)
- Логирование всех операций
- Последовательность вызова методов

Для получения полного доступа к Direct Pro необходимо описать:
1. Названия методов, которые использует программа
2. Схему и последовательность вызова методов
3. С какой частотой производится вызов каждого метода
4. Как программа обрабатывает ошибки
5. Как программа учитывает текущие ограничения API Директа

Используемые методы API:
- Campaigns.get - получение списка рекламных кампаний
- AdGroups.get - получение групп объявлений
- Keywords.get - получение ключевых слов
- Ads.get - получение объявлений
- Reports.get - получение отчетов по эффективности
- Bids.get - получение текущих ставок
- Sitelinks.get - получение быстрых ссылок
"""

import time
import os
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class APIError(Exception):
    """Базовый класс для ошибок API"""
    pass


class RateLimitError(APIError):
    """Ошибка превышения лимита запросов"""
    pass


class APIRequestError(APIError):
    """Ошибка запроса к API"""
    pass


class ErrorCode(Enum):
    """Коды ошибок Yandex Direct API"""
    # Ошибки авторизации
    AUTHENTICATION_ERROR = 152
    INVALID_TOKEN = 53
    
    # Ошибки лимитов
    RATE_LIMIT_EXCEEDED = 506
    TOO_MANY_REQUESTS = 509
    
    # Ошибки валидации
    INVALID_PARAMETER = 1000
    MISSING_PARAMETER = 1001
    
    # Ошибки бизнес-логики
    CAMPAIGN_NOT_FOUND = 2000
    ADGROUP_NOT_FOUND = 2001
    KEYWORD_NOT_FOUND = 2002


@dataclass
class RateLimiter:
    """
    Класс для контроля частоты запросов к API.
    
    Yandex Direct API имеет следующие ограничения:
    - Максимум 10,000 запросов в день на один токен
    - Максимум 5 запросов в секунду
    - Для методов Reports - максимум 100 запросов в день
    """
    requests_per_second: float = 4.0  # Безопасное значение: 4 запроса/сек (ниже лимита 5)
    requests_per_day: int = 9000  # Безопасное значение: 9000 запросов/день (ниже лимита 10000)
    reports_per_day: int = 90  # Безопасное значение: 90 запросов/день (ниже лимита 100)
    
    def __post_init__(self):
        self.last_request_time: float = 0.0
        self.daily_request_count: int = 0
        self.daily_report_count: int = 0
        self.day_start: datetime = datetime.now()
    
    def wait_if_needed(self):
        """Ожидание перед запросом для соблюдения rate limit"""
        current_time = time.time()
        
        # Проверка сброса дневного счетчика
        if (datetime.now() - self.day_start).days >= 1:
            self.daily_request_count = 0
            self.daily_report_count = 0
            self.day_start = datetime.now()
            logger.info("Сброс дневных счетчиков запросов")
        
        # Проверка дневного лимита
        if self.daily_request_count >= self.requests_per_day:
            raise RateLimitError(
                f"Достигнут дневной лимит запросов: {self.requests_per_day}. "
                f"Попробуйте завтра или запросите увеличение лимита."
            )
        
        # Ожидание между запросами (rate limiting по секундам)
        time_since_last = current_time - self.last_request_time
        min_interval = 1.0 / self.requests_per_second
        
        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            logger.debug(f"Ожидание {sleep_time:.3f} сек для соблюдения rate limit")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
        self.daily_request_count += 1
    
    def check_report_limit(self):
        """Проверка лимита для запросов отчетов"""
        if self.daily_report_count >= self.reports_per_day:
            raise RateLimitError(
                f"Достигнут дневной лимит запросов отчетов: {self.reports_per_day}. "
                f"Попробуйте завтра или запросите увеличение лимита."
            )
        self.daily_report_count += 1


class YandexDirectAPIClient:
    """
    Клиент для работы с Yandex Direct API.
    
    Последовательность работы:
    1. Инициализация клиента с токеном
    2. Получение списка кампаний (Campaigns.get)
    3. Для каждой кампании получение групп объявлений (AdGroups.get)
    4. Для каждой группы получение ключевых слов (Keywords.get)
    5. Получение объявлений (Ads.get)
    6. Получение ставок (Bids.get)
    7. Получение отчетов (Reports.get) - с ограниченной частотой
    """
    
    API_BASE_URL = "https://api.direct.yandex.com/json/v5"
    API_SANDBOX_URL = "https://api-sandbox.direct.yandex.com/json/v5"
    
    def __init__(
        self,
        access_token: str,
        login: str,
        use_sandbox: bool = False,
        rate_limiter: Optional[RateLimiter] = None
    ):
        """
        Инициализация клиента.
        
        Args:
            access_token: OAuth токен доступа
            login: Логин рекламодателя
            use_sandbox: Использовать песочницу (для тестирования)
            rate_limiter: Объект для контроля rate limiting
        """
        self.access_token = access_token
        self.login = login
        self.base_url = self.API_SANDBOX_URL if use_sandbox else self.API_BASE_URL
        self.rate_limiter = rate_limiter or RateLimiter()
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.access_token}',
            'Client-Login': self.login,
            'Accept-Language': 'ru',
        })
        
        logger.info(f"Инициализирован клиент Yandex Direct API для логина: {self.login}")
    
    def _make_request(
        self,
        method: str,
        params: Dict[str, Any],
        is_report: bool = False
    ) -> Dict[str, Any]:
        """
        Выполнение запроса к API с обработкой ошибок и rate limiting.
        
        Args:
            method: Название метода API (например, 'Campaigns.get')
            params: Параметры запроса
            is_report: Флаг, что это запрос отчета (для отдельного лимита)
        
        Returns:
            Ответ API
        
        Raises:
            RateLimitError: При превышении лимитов
            APIRequestError: При ошибках запроса
        """
        # Проверка rate limit
        if is_report:
            self.rate_limiter.check_report_limit()
        self.rate_limiter.wait_if_needed()
        
        try:
            service_name, action_name = method.split('.', 1)
        except ValueError:
            raise ValueError("Название метода должно быть в формате 'Service.Method'")
        
        endpoint = f"{self.base_url}/{service_name.lower()}"
        action_method = action_name[:1].lower() + action_name[1:]
        request_data = {
            'method': action_method,
            'params': params
        }
        
        logger.info(
            f"Выполнение запроса: {service_name}.{action_name} с параметрами: {params}"
        )
        
        try:
            response = self.session.post(
                endpoint,
                json=request_data,
                timeout=30
            )
            response.raise_for_status()
            is_reports_service = service_name.lower() == 'reports'
            
            if is_reports_service:
                content_type = response.headers.get('Content-Type', '').lower()
                if 'application/json' not in content_type:
                    logger.info(f"Успешный ответ от {service_name}.{action_name}")
                    return {'Report': response.text}
            
            result = response.json()
            
            # Обработка ошибок API
            if 'error' in result:
                error = result['error']
                error_code = error.get('error_code')
                error_string = error.get('error_string', '')
                error_detail = error.get('error_detail', '')
                
                logger.error(
                    f"Ошибка API {method}: код={error_code}, "
                    f"сообщение={error_string}, детали={error_detail}"
                )
                
                # Специальная обработка ошибок rate limit
                if error_code in [ErrorCode.RATE_LIMIT_EXCEEDED.value, ErrorCode.TOO_MANY_REQUESTS.value]:
                    raise RateLimitError(
                        f"Превышен лимит запросов: {error_string}. "
                        f"Детали: {error_detail}"
                    )
                
                # Обработка ошибок авторизации
                if error_code in [ErrorCode.AUTHENTICATION_ERROR.value, ErrorCode.INVALID_TOKEN.value]:
                    raise APIRequestError(
                        f"Ошибка авторизации: {error_string}. "
                        f"Проверьте токен доступа."
                    )
                
                # Общая обработка ошибок
                raise APIRequestError(
                    f"Ошибка API {method}: {error_string} (код: {error_code}). "
                    f"Детали: {error_detail}"
                )
            
            # Проверка наличия результата
            if 'result' not in result:
                logger.warning(f"Ответ API {method} не содержит поля 'result'")
                return {}
            
            logger.info(f"Успешный ответ от {method}")
            return result['result']
            
        except requests.exceptions.Timeout:
            logger.error(f"Таймаут при запросе {method}")
            raise APIRequestError(f"Таймаут при запросе к API: {method}")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при запросе {method}: {e}")
            raise APIRequestError(f"Ошибка сети: {e}")
        
        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе {method}: {e}", exc_info=True)
            raise APIRequestError(f"Неожиданная ошибка: {e}")
    
    def get_campaigns(
        self,
        campaign_ids: Optional[List[int]] = None,
        states: Optional[List[str]] = None,
        types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Получение списка рекламных кампаний.
        
        Метод: Campaigns.get
        Частота вызова: 1 раз при инициализации, затем по требованию (не чаще 1 раза в минуту)
        
        Args:
            campaign_ids: Список ID кампаний (None = все кампании)
            states: Фильтр по статусам (например, ['ON', 'OFF'])
            types: Фильтр по типам (например, ['TEXT_CAMPAIGN'])
        
        Returns:
            Список кампаний
        """
        params = {
            'SelectionCriteria': {}
        }
        
        if campaign_ids:
            params['SelectionCriteria']['Ids'] = campaign_ids
        
        if states:
            params['SelectionCriteria']['States'] = states
        
        if types:
            params['SelectionCriteria']['Types'] = types
        
        # Поля для получения
        params['FieldNames'] = [
            'Id', 'Name', 'Type', 'State', 'Status', 'DailyBudget',
            'Currency', 'Funds', 'Statistics', 'StartDate', 'EndDate'
        ]
        
        try:
            result = self._make_request('Campaigns.get', params)
            campaigns = result.get('Campaigns', [])
            logger.info(f"Получено кампаний: {len(campaigns)}")
            return campaigns
        
        except APIError as e:
            logger.error(f"Ошибка при получении кампаний: {e}")
            raise
    
    def get_ad_groups(
        self,
        campaign_ids: List[int],
        ad_group_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Получение групп объявлений.
        
        Метод: AdGroups.get
        Частота вызова: После получения кампаний, для каждой кампании (не чаще 2 раз в секунду)
        
        Args:
            campaign_ids: Список ID кампаний
            ad_group_ids: Опциональный список ID групп
        
        Returns:
            Список групп объявлений
        """
        params = {
            'SelectionCriteria': {
                'CampaignIds': campaign_ids
            }
        }
        
        if ad_group_ids:
            params['SelectionCriteria']['Ids'] = ad_group_ids
        
        params['FieldNames'] = [
            'Id', 'Name', 'CampaignId', 'NegativeKeywords', 'NegativeKeywordSharedSetIds',
            'TrackingParams', 'Type', 'Subtype', 'ServingStatus', 'Status'
        ]
        
        try:
            result = self._make_request('AdGroups.get', params)
            ad_groups = result.get('AdGroups', [])
            logger.info(f"Получено групп объявлений: {len(ad_groups)}")
            return ad_groups
        
        except APIError as e:
            logger.error(f"Ошибка при получении групп объявлений: {e}")
            raise
    
    def get_keywords(
        self,
        campaign_ids: Optional[List[int]] = None,
        ad_group_ids: Optional[List[int]] = None,
        keyword_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Получение ключевых слов.
        
        Метод: Keywords.get
        Частота вызова: После получения групп объявлений (не чаще 2 раз в секунду)
        
        Args:
            campaign_ids: Список ID кампаний
            ad_group_ids: Список ID групп объявлений
            keyword_ids: Опциональный список ID ключевых слов
        
        Returns:
            Список ключевых слов
        """
        params = {
            'SelectionCriteria': {}
        }
        
        if campaign_ids:
            params['SelectionCriteria']['CampaignIds'] = campaign_ids
        
        if ad_group_ids:
            params['SelectionCriteria']['AdGroupIds'] = ad_group_ids
        
        if keyword_ids:
            params['SelectionCriteria']['Ids'] = keyword_ids
        
        params['FieldNames'] = [
            'Id', 'Keyword', 'AdGroupId', 'CampaignId', 'Bid', 'ContextBid',
            'StrategyPriority', 'State', 'Status', 'Productivity', 'StatisticsSearch',
            'StatisticsNetwork'
        ]
        
        try:
            result = self._make_request('Keywords.get', params)
            keywords = result.get('Keywords', [])
            logger.info(f"Получено ключевых слов: {len(keywords)}")
            return keywords
        
        except APIError as e:
            logger.error(f"Ошибка при получении ключевых слов: {e}")
            raise
    
    def get_ads(
        self,
        campaign_ids: Optional[List[int]] = None,
        ad_group_ids: Optional[List[int]] = None,
        ad_ids: Optional[List[int]] = None,
        states: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Получение объявлений.
        
        Метод: Ads.get
        Частота вызова: После получения групп объявлений (не чаще 2 раз в секунду)
        
        Args:
            campaign_ids: Список ID кампаний
            ad_group_ids: Список ID групп объявлений
            ad_ids: Опциональный список ID объявлений
            states: Фильтр по статусам
        
        Returns:
            Список объявлений
        """
        params = {
            'SelectionCriteria': {}
        }
        
        if campaign_ids:
            params['SelectionCriteria']['CampaignIds'] = campaign_ids
        
        if ad_group_ids:
            params['SelectionCriteria']['AdGroupIds'] = ad_group_ids
        
        if ad_ids:
            params['SelectionCriteria']['Ids'] = ad_ids
        
        if states:
            params['SelectionCriteria']['States'] = states
        
        params['FieldNames'] = [
            'Id', 'AdGroupId', 'CampaignId', 'AdCategories', 'AgeLabel',
            'Type', 'Subtype', 'Status', 'State', 'TextAd', 'MobileAppAd',
            'DynamicTextAd', 'TextImageAd', 'MobileAppImageAd', 'TextAdBuilderAd',
            'CpcVideoAdBuilderAd', 'CpmBannerAdBuilderAd', 'CpmVideoAdBuilderAd'
        ]
        
        try:
            result = self._make_request('Ads.get', params)
            ads = result.get('Ads', [])
            logger.info(f"Получено объявлений: {len(ads)}")
            return ads
        
        except APIError as e:
            logger.error(f"Ошибка при получении объявлений: {e}")
            raise
    
    def get_bids(
        self,
        campaign_ids: Optional[List[int]] = None,
        ad_group_ids: Optional[List[int]] = None,
        keyword_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Получение текущих ставок.
        
        Метод: Bids.get
        Частота вызова: После получения ключевых слов (не чаще 1 раза в минуту)
        
        Args:
            campaign_ids: Список ID кампаний
            ad_group_ids: Список ID групп объявлений
            keyword_ids: Список ID ключевых слов
        
        Returns:
            Список ставок
        """
        params = {
            'SelectionCriteria': {}
        }
        
        if campaign_ids:
            params['SelectionCriteria']['CampaignIds'] = campaign_ids
        
        if ad_group_ids:
            params['SelectionCriteria']['AdGroupIds'] = ad_group_ids
        
        if keyword_ids:
            params['SelectionCriteria']['KeywordIds'] = keyword_ids
        
        params['FieldNames'] = [
            'KeywordId', 'AdGroupId', 'CampaignId', 'Bid', 'ContextBid',
            'StrategyPriority', 'CompetitorsBids', 'SearchPrices', 'ContextCoverage',
            'MinSearchPrice', 'CurrentSearchPrice', 'AuctionBids'
        ]
        
        try:
            result = self._make_request('Bids.get', params)
            bids = result.get('Bids', [])
            logger.info(f"Получено ставок: {len(bids)}")
            return bids
        
        except APIError as e:
            logger.error(f"Ошибка при получении ставок: {e}")
            raise
    
    def get_sitelinks(
        self,
        ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Получение быстрых ссылок.
        
        Метод: Sitelinks.get
        Частота вызова: По требованию (не чаще 1 раза в минуту)
        
        Args:
            ids: Опциональный список ID быстрых ссылок
        
        Returns:
            Список быстрых ссылок
        """
        params = {}
        
        if ids:
            params['SelectionCriteria'] = {'Ids': ids}
        
        params['FieldNames'] = [
            'Id', 'Sitelinks', 'SitelinksSets'
        ]
        
        try:
            result = self._make_request('Sitelinks.get', params)
            sitelinks = result.get('SitelinksSets', [])
            logger.info(f"Получено наборов быстрых ссылок: {len(sitelinks)}")
            return sitelinks
        
        except APIError as e:
            logger.error(f"Ошибка при получении быстрых ссылок: {e}")
            raise
    
    def get_report(
        self,
        report_type: str = 'ACCOUNT_PERFORMANCE_REPORT',
        date_range_type: str = 'LAST_30_DAYS',
        format: str = 'TSV',
        include_vat: str = 'YES'
    ) -> str:
        """
        Получение отчета по эффективности.
        
        Метод: Reports.get
        Частота вызова: Не чаще 1 раза в час (ограничение: 100 запросов в день)
        
        Args:
            report_type: Тип отчета (ACCOUNT_PERFORMANCE_REPORT, CAMPAIGN_PERFORMANCE_REPORT, etc.)
            date_range_type: Период отчета (LAST_7_DAYS, LAST_30_DAYS, etc.)
            format: Формат отчета (TSV, CSV)
            include_vat: Включать НДС (YES/NO)
        
        Returns:
            Данные отчета в виде строки
        """
        params = {
            'ReportType': report_type,
            'DateRangeType': date_range_type,
            'Format': format,
            'IncludeVAT': include_vat,
            'IncludeDiscount': 'NO',
            'ReportName': f'Report_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        }
        
        # Поля отчета
        params['FieldNames'] = [
            'CampaignName', 'CampaignId', 'AdGroupName', 'AdGroupId',
            'Criterion', 'CriterionId', 'CriterionType', 'Impressions',
            'Clicks', 'Cost', 'Ctr', 'AvgCpc', 'Conversions'
        ]
        
        try:
            result = self._make_request('Reports.get', params, is_report=True)
            report_data = result.get('Report', '')
            logger.info(f"Получен отчет: {report_type}, размер: {len(report_data)} байт")
            return report_data
        
        except APIError as e:
            logger.error(f"Ошибка при получении отчета: {e}")
            raise

    def find_keywords(
        self,
        keyword_texts: List[str],
        region_ids: Optional[List[int]] = None,
        minus_keywords: Optional[List[str]] = None,
        field_names: Optional[List[str]] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Получение частотности и рекомендуемых ставок по ключевым фразам.

        Метод: KeywordsResearch.findKeywords
        Частота вызова: по требованию (учитывается общий rate limit)

        Args:
            keyword_texts: Список ключевых фраз
            region_ids: Идентификаторы регионов (GeoId)
            minus_keywords: Список минус-слов
            field_names: Поля ответа (по умолчанию базовый набор)
            limit: Количество записей на странице
            offset: Смещение для пагинации

        Returns:
            Ответ API с массивом Keywords
        """
        if not keyword_texts:
            raise ValueError("Список keyword_texts не может быть пустым")

        params: Dict[str, Any] = {
            'SelectionCriteria': {
                'KeywordTexts': keyword_texts
            },
            'FieldNames': field_names or ['Keyword', 'Shows', 'Bid', 'Competition'],
            'Page': {
                'Limit': limit,
                'Offset': offset
            }
        }

        if region_ids:
            params['SelectionCriteria']['GeoId'] = region_ids

        if minus_keywords:
            params['SelectionCriteria']['MinusKeywords'] = minus_keywords

        try:
            result = self._make_request('KeywordsResearch.findKeywords', params)
            logger.info(
                "Получены данные KeywordResearch: %s записей",
                len(result.get('Keywords', []))
            )
            return result

        except APIError as e:
            logger.error(f"Ошибка при вызове KeywordResearch: {e}")
            raise
    
    def get_full_campaign_data(
        self,
        campaign_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Получение полных данных по кампаниям (последовательный вызов методов).
        
        Схема вызова:
        1. Campaigns.get - получение списка кампаний
        2. AdGroups.get - получение групп объявлений для каждой кампании
        3. Keywords.get - получение ключевых слов для каждой группы
        4. Ads.get - получение объявлений для каждой группы
        5. Bids.get - получение ставок для ключевых слов
        
        Частота вызова: Не чаще 1 раза в 5 минут
        
        Args:
            campaign_ids: Опциональный список ID кампаний
        
        Returns:
            Словарь с полными данными по кампаниям
        """
        logger.info("Начало получения полных данных по кампаниям")
        
        try:
            # Шаг 1: Получение кампаний
            campaigns = self.get_campaigns(campaign_ids=campaign_ids)
            
            if not campaigns:
                logger.warning("Не найдено кампаний")
                return {
                    'campaigns': [],
                    'ad_groups': [],
                    'keywords': [],
                    'ads': [],
                    'bids': []
                }
            
            campaign_ids_list = [c['Id'] for c in campaigns]
            
            # Шаг 2: Получение групп объявлений
            ad_groups = self.get_ad_groups(campaign_ids=campaign_ids_list)
            
            if not ad_groups:
                logger.warning("Не найдено групп объявлений")
                return {
                    'campaigns': campaigns,
                    'ad_groups': [],
                    'keywords': [],
                    'ads': [],
                    'bids': []
                }
            
            ad_group_ids_list = [ag['Id'] for ag in ad_groups]
            
            # Шаг 3: Получение ключевых слов
            keywords = self.get_keywords(ad_group_ids=ad_group_ids_list)
            keyword_ids_list = [k['Id'] for k in keywords] if keywords else []
            
            # Шаг 4: Получение объявлений
            ads = self.get_ads(ad_group_ids=ad_group_ids_list)
            
            # Шаг 5: Получение ставок (только если есть ключевые слова)
            bids = []
            if keyword_ids_list:
                bids = self.get_bids(keyword_ids=keyword_ids_list)
            
            result = {
                'campaigns': campaigns,
                'ad_groups': ad_groups,
                'keywords': keywords,
                'ads': ads,
                'bids': bids
            }
            
            logger.info(
                f"Успешно получены данные: "
                f"кампаний={len(campaigns)}, "
                f"групп={len(ad_groups)}, "
                f"ключевых слов={len(keywords)}, "
                f"объявлений={len(ads)}, "
                f"ставок={len(bids)}"
            )
            
            return result
        
        except APIError as e:
            logger.error(f"Ошибка при получении полных данных: {e}")
            raise


# Пример использования
if __name__ == "__main__":
    """
    Пример использования клиента Yandex Direct API.
    
    Для работы необходимо:
    1. Получить OAuth токен доступа
    2. Указать логин рекламодателя
    3. Настроить параметры rate limiting при необходимости
    """
    
    # Настройки (можно передать через переменные окружения)
    ACCESS_TOKEN = os.environ.get("YD_TOKEN", "your_access_token_here")
    LOGIN = os.environ.get("YD_LOGIN", "your_login_here")
    USE_SANDBOX = os.environ.get("YD_USE_SANDBOX", "true").lower() in {"1", "true", "yes"}

    if ACCESS_TOKEN == "your_access_token_here" or LOGIN == "your_login_here":
        raise RuntimeError(
            "Задайте переменные окружения YD_TOKEN и YD_LOGIN или отредактируйте значения в примере."
        )
    
    try:
        # Инициализация клиента
        client = YandexDirectAPIClient(
            access_token=ACCESS_TOKEN,
            login=LOGIN,
            use_sandbox=USE_SANDBOX
        )
        
        # Пример 1: Получение списка кампаний
        print("Получение списка кампаний...")
        campaigns = client.get_campaigns()
        print(f"Найдено кампаний: {len(campaigns)}")
        
        # Пример 2: Получение полных данных по кампаниям
        if campaigns:
            print("\nПолучение полных данных по кампаниям...")
            full_data = client.get_full_campaign_data()
            print(f"Получено данных: {len(full_data['campaigns'])} кампаний")
        
        # Пример 3: Получение отчета (с ограниченной частотой)
        print("\nПолучение отчета...")
        report = client.get_report(
            report_type='ACCOUNT_PERFORMANCE_REPORT',
            date_range_type='LAST_7_DAYS'
        )
        print(f"Размер отчета: {len(report)} байт")
        
    except RateLimitError as e:
        print(f"Ошибка лимита запросов: {e}")
        print("Подождите перед следующим запросом")
    
    except APIRequestError as e:
        print(f"Ошибка запроса: {e}")
        print("Проверьте токен доступа и параметры запроса")
    
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
