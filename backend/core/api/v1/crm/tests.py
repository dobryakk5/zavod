from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from core.models import Client as ZavodClient
from core.models import CRMClient, ClientCategory, Event, EventType, Payment, Note


class CRMTestCase(TestCase):
    def setUp(self):
        # Создаем тестового пользователя
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
        
        # Создаем Zavod клиента
        self.zavod_client = ZavodClient.objects.create(
            name='Test Company',
            slug='test-company',
            timezone='Europe/Moscow'
        )
        
        # Создаем связь пользователя с Zavod клиентом
        # (предполагаем, что у пользователя есть связанное поле или роль)
        # В реальной системе это может быть через UserTenantRole
        
        # Создаем API клиент и авторизуем его
        self.client = APIClient()
        token = AccessToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Создаем тестовые категории
        self.category = ClientCategory.objects.create(
            name='VIP',
            description='Премиум клиенты',
            color='#FFD700'
        )
        
        # Создаем тестового CRM клиента
        self.crm_client = CRMClient.objects.create(
            first_name='Иван',
            last_name='Петров',
            email='ivan@example.com',
            phone='+79991234567',
            category=self.category,
            status='active',
            notes='Тестовый клиент',
            zavod_client=self.zavod_client
        )
        
        # Создаем тип события
        self.event_type = EventType.objects.create(
            name='Консультация',
            description='Персональная консультация',
            duration_minutes=60,
            color='#4A90E2'
        )


class CRMClientAPITest(CRMTestCase):
    def test_get_clients_list(self):
        """Тест получения списка клиентов"""
        url = reverse('crm-client-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
        self.assertGreaterEqual(len(response.data['results']), 1)
        
        # Проверяем, что возвращаются правильные поля
        client_data = response.data['results'][0]
        self.assertIn('first_name', client_data)
        self.assertIn('last_name', client_data)
        self.assertIn('email', client_data)
        self.assertIn('category', client_data)
    
    def test_create_client(self):
        """Тест создания клиента"""
        url = reverse('crm-client-list')
        data = {
            'first_name': 'Мария',
            'last_name': 'Сидорова',
            'email': 'maria@example.com',
            'phone': '+79997654321',
            'category_id': self.category.id,
            'status': 'active',
            'notes': 'Новый клиент'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        
        # Проверяем, что клиент был создан
        self.assertEqual(CRMClient.objects.count(), 2)
        new_client = CRMClient.objects.get(email='maria@example.com')
        self.assertEqual(new_client.first_name, 'Мария')
    
    def test_get_single_client(self):
        """Тест получения одного клиента"""
        url = reverse('crm-client-detail', kwargs={'pk': self.crm_client.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['email'], 'ivan@example.com')
    
    def test_update_client(self):
        """Тест обновления клиента"""
        url = reverse('crm-client-detail', kwargs={'pk': self.crm_client.id})
        data = {
            'first_name': 'Иван',
            'last_name': 'Петров-Иванов',
            'email': 'ivan@example.com',
            'status': 'inactive'
        }
        
        response = self.client.put(url, data, format='json')
        self.assertEqual(response.status_code, 200)
        
        # Проверяем, что данные обновились
        self.crm_client.refresh_from_db()
        self.assertEqual(self.crm_client.last_name, 'Петров-Иванов')
        self.assertEqual(self.crm_client.status, 'inactive')
    
    def test_delete_client(self):
        """Тест удаления клиента"""
        url = reverse('crm-client-detail', kwargs={'pk': self.crm_client.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, 204)
        self.assertEqual(CRMClient.objects.count(), 0)


class CRMCategoriesAPITest(CRMTestCase):
    def test_get_categories_list(self):
        """Тест получения списка категорий"""
        url = reverse('crm-category-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)
        
        category_data = response.data[0]
        self.assertEqual(category_data['name'], 'VIP')
    
    def test_create_category(self):
        """Тест создания категории"""
        url = reverse('crm-category-list')
        data = {
            'name': 'Стандарт',
            'description': 'Обычные клиенты',
            'color': '#4A90E2'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        
        # Проверяем, что категория была создана
        self.assertEqual(ClientCategory.objects.count(), 2)
        new_category = ClientCategory.objects.get(name='Стандарт')
        self.assertEqual(new_category.description, 'Обычные клиенты')


class CRMEventsAPITest(CRMTestCase):
    def setUp(self):
        super().setUp()
        
        # Создаем событие для тестов
        self.event = Event.objects.create(
            client=self.crm_client,
            event_type=self.event_type,
            title='Консультация по стратегии',
            description='Обсуждение долгосрочной стратегии',
            start_time=timezone.now(),
            end_time=timezone.now() + timezone.timedelta(hours=1),
            location='Онлайн',
            status='scheduled'
        )
    
    def test_get_events_list(self):
        """Тест получения списка событий"""
        url = reverse('crm-event-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
        self.assertGreaterEqual(len(response.data['results']), 1)
    
    def test_create_event(self):
        """Тест создания события"""
        url = reverse('crm-event-list')
        data = {
            'client_id': self.crm_client.id,
            'event_type_id': self.event_type.id,
            'title': 'Первая встреча',
            'description': 'Знакомство',
            'start_time': '2026-02-01T10:00:00Z',
            'end_time': '2026-02-01T11:00:00Z',
            'location': 'Офис',
            'status': 'scheduled'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        
        # Проверяем, что событие было создано
        self.assertEqual(Event.objects.count(), 2)
    
    def test_get_upcoming_events(self):
        """Тест получения предстоящих событий"""
        url = reverse('crm-event-upcoming')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Должно вернуть хотя бы одно событие
        self.assertGreaterEqual(len(response.data), 1)


class CRMPaymentsAPITest(CRMTestCase):
    def setUp(self):
        super().setUp()
        
        # Создаем платеж для тестов
        self.payment = Payment.objects.create(
            client=self.crm_client,
            amount=15000.00,
            currency='RUB',
            status='paid',
            payment_method='card',
            description='Оплата за 10 сессий',
            paid_at=timezone.now()
        )
    
    def test_get_payments_list(self):
        """Тест получения списка платежей"""
        url = reverse('crm-payment-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
        self.assertGreaterEqual(len(response.data['results']), 1)
    
    def test_create_payment(self):
        """Тест создания платежа"""
        url = reverse('crm-payment-list')
        data = {
            'client_id': self.crm_client.id,
            'amount': 5000.00,
            'currency': 'RUB',
            'status': 'pending',
            'payment_method': 'transfer',
            'description': 'Предоплата за первую сессию'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        
        # Проверяем, что платеж был создан
        self.assertEqual(Payment.objects.count(), 2)
    
    def test_get_payment_summary(self):
        """Тест получения сводки по платежам"""
        url = reverse('crm-payment-summary')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_paid', response.data)
        self.assertIn('total_pending', response.data)
        self.assertIn('by_currency', response.data)


class CRMNotesAPITest(CRMTestCase):
    def setUp(self):
        super().setUp()
        
        # Создаем заметку для тестов
        self.note = Note.objects.create(
            client=self.crm_client,
            title='Предпочтения',
            content='Любит утренние встречи',
            is_important=True
        )
    
    def test_get_notes_list(self):
        """Тест получения списка заметок"""
        url = reverse('crm-note-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
        self.assertGreaterEqual(len(response.data['results']), 1)
    
    def test_create_note(self):
        """Тест создания заметки"""
        url = reverse('crm-note-list')
        data = {
            'client_id': self.crm_client.id,
            'title': 'Прогресс',
            'content': 'Хорошо реагирует на практику',
            'is_important': False
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)
        
        # Проверяем, что заметка была создана
        self.assertEqual(Note.objects.count(), 2)