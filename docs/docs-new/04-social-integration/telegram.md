# Telegram Publishing

В этом документе описана интеграция с Telegram для автоматической публикации контента.

## Содержание

- [Требования](#требования)
- [Настройка Telegram Bot](#настройка-telegram-bot)
- [Настройка канала](#настройка-канала)
- [Backend интеграция](#backend-интеграция)
- [Frontend интеграция](#frontend-интеграция)
- [Публикация](#публикация)
- [Очередь задач](#очередь-задач)
- [Тестирование](#тестирование)

## Требования

1. **Telegram Bot** (созданный через @BotFather)
2. **Telegram Channel** для публикации
3. **Bot является администратором канала**
4. **Django backend** с Celery
5. **aiogram** библиотека

## Настройка Telegram Bot

### 1. Создание бота

1. Найдите @BotFather в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям:
   - Выберите имя бота (например, "Content Publisher Bot")
   - Выберите username (например, "content_publisher_bot")
4. Скопируйте токен (например, `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Настройка бота

```python
# config/settings.py
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_BOT_USERNAME = os.environ.get('TELEGRAM_BOT_USERNAME', 'content_publisher_bot')
```

### 3. Проверка бота

```python
import requests

def check_telegram_bot(token):
    """Проверка работоспособности бота"""
    url = f"https://api.telegram.org/bot{token}/getMe"
    
    response = requests.get(url)
    result = response.json()
    
    if result.get('ok'):
        print(f"Bot: {result['result']['first_name']}")
        print(f"Username: @{result['result']['username']}")
        return True
    else:
        print(f"Error: {result.get('description')}")
        return False

# Тест
check_telegram_bot(TELEGRAM_BOT_TOKEN)
```

## Настройка канала

### 1. Создание канала

1. Откройте Telegram
2. Нажмите на значок меню (три линии)
3. Выберите "Новый канал"
4. Укажите имя канала (например, "Контент студии")
5. Укажите username (например, "content_studio_channel")
6. Добавьте описание и аватар

### 2. Добавление бота как администратора

1. Откройте канал
2. Перейдите в "Участники" → "Администраторы" → "Добавить администратора"
3. Найдите вашего бота (например, @content_publisher_bot)
4. Дайте права:
   - **Публикация сообщений** (обязательно)
   - **Редактирование сообщений** (опционально)
   - **Удаление сообщений** (опционально)

### 3. Проверка канала

```python
def check_telegram_channel(token, chat_id):
    """Проверка доступа к каналу"""
    url = f"https://api.telegram.org/bot{token}/getChat"
    data = {'chat_id': chat_id}
    
    response = requests.post(url, data=data)
    result = response.json()
    
    if result.get('ok'):
        chat = result['result']
        print(f"Channel: {chat['title']}")
        print(f"Type: {chat['type']}")
        return True
    else:
        print(f"Error: {result.get('description')}")
        return False

# Тест
check_telegram_channel(TELEGRAM_BOT_TOKEN, '@content_studio_channel')
```

## Backend интеграция

### 1. Модель SocialAccount

```python
# core/models.py
class SocialAccount(models.Model):
    PLATFORM_CHOICES = [
        ('telegram', 'Telegram'),
        ('instagram', 'Instagram'),
        ('youtube', 'YouTube'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    name = models.CharField(max_length=255)
    username = models.CharField(max_length=255)
    access_token = models.TextField()  # Bot token
    is_active = models.BooleanField(default=True)
    extra = models.JSONField(default=dict, blank=True)
    
    class Meta:
        unique_together = ('client', 'platform', 'username')
    
    def __str__(self):
        return f"{self.client.name} - {self.platform} - {self.username}"
```

### 2. Telegram Publisher

```python
# core/services/telegram_publisher.py
import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class TelegramPublisher:
    """Сервис для публикации в Telegram"""
    
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def send_text(self, chat_id: str, text: str, parse_mode: str = 'HTML') -> Dict[str, Any]:
        """Отправка текстового сообщения"""
        url = f"{self.base_url}/sendMessage"
        
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_web_page_preview': False
        }
        
        response = requests.post(url, data=data)
        response.raise_for_status()
        
        return response.json()
    
    def send_photo(self, chat_id: str, photo_url: str, caption: str = None, parse_mode: str = 'HTML') -> Dict[str, Any]:
        """Отправка фото с подписью"""
        url = f"{self.base_url}/sendPhoto"
        
        data = {
            'chat_id': chat_id,
            'parse_mode': parse_mode
        }
        
        if caption:
            data['caption'] = caption
        
        # Загрузка фото
        photo_data = requests.get(photo_url).content
        
        files = {
            'photo': photo_data
        }
        
        response = requests.post(url, data=data, files=files)
        response.raise_for_status()
        
        return response.json()
    
    def send_video(self, chat_id: str, video_url: str, caption: str = None, parse_mode: str = 'HTML') -> Dict[str, Any]:
        """Отправка видео"""
        url = f"{self.base_url}/sendVideo"
        
        data = {
            'chat_id': chat_id,
            'parse_mode': parse_mode
        }
        
        if caption:
            data['caption'] = caption
        
        # Загрузка видео
        video_data = requests.get(video_url).content
        
        files = {
            'video': video_data
        }
        
        response = requests.post(url, data=data, files=files)
        response.raise_for_status()
        
        return response.json()
    
    def send_media_group(self, chat_id: str, media: list, parse_mode: str = 'HTML') -> Dict[str, Any]:
        """Отправка группы медиа (несколько фото/видео)"""
        url = f"{self.base_url}/sendMediaGroup"
        
        media_data = []
        
        for item in media:
            if item['type'] == 'photo':
                media_data.append({
                    'type': 'photo',
                    'media': item['url'],
                    'caption': item.get('caption', ''),
                    'parse_mode': parse_mode
                })
            elif item['type'] == 'video':
                media_data.append({
                    'type': 'video',
                    'media': item['url'],
                    'caption': item.get('caption', ''),
                    'parse_mode': parse_mode
                })
        
        data = {
            'chat_id': chat_id,
            'media': json.dumps(media_data)
        }
        
        response = requests.post(url, data=data)
        response.raise_for_status()
        
        return response.json()
    
    def edit_message_text(self, chat_id: str, message_id: int, text: str, parse_mode: str = 'HTML') -> Dict[str, Any]:
        """Редактирование текста сообщения"""
        url = f"{self.base_url}/editMessageText"
        
        data = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text,
            'parse_mode': parse_mode
        }
        
        response = requests.post(url, data=data)
        response.raise_for_status()
        
        return response.json()
    
    def delete_message(self, chat_id: str, message_id: int) -> bool:
        """Удаление сообщения"""
        url = f"{self.base_url}/deleteMessage"
        
        data = {
            'chat_id': chat_id,
            'message_id': message_id
        }
        
        response = requests.post(url, data=data)
        
        return response.status_code == 200
```

### 3. API Endpoints

```python
# api/views.py
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from core.services.telegram_publisher import TelegramPublisher

class SocialAccountViewSet(ModelViewSet):
    serializer_class = SocialAccountSerializer
    permission_classes = [IsTenantOwnerOrEditor]
    
    def get_queryset(self):
        client = get_active_client(self.request.user)
        return SocialAccount.objects.filter(client=client, platform='telegram')
    
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """Тестирование подключения к Telegram"""
        social_account = self.get_object()
        
        try:
            publisher = TelegramPublisher(social_account.access_token)
            result = publisher.send_text(
                chat_id=social_account.extra.get('chat_id', social_account.username),
                text="Тестовое сообщение от Zavod"
            )
            
            if result.get('ok'):
                return Response({
                    'success': True,
                    'message': 'Connection successful',
                    'message_id': result['result']['message_id']
                })
            else:
                return Response({
                    'success': False,
                    'error': result.get('description', 'Unknown error')
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def send_test_message(self, request, pk=None):
        """Отправка тестового сообщения"""
        social_account = self.get_object()
        
        serializer = TestMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            publisher = TelegramPublisher(social_account.access_token)
            result = publisher.send_text(
                chat_id=social_account.extra.get('chat_id', social_account.username),
                text=serializer.validated_data['text']
            )
            
            return Response({
                'success': True,
                'message_id': result['result']['message_id']
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

### 4. Serializers

```python
# api/serializers.py
class TestMessageSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=4096)
```

## Frontend интеграция

### 1. API Functions

```typescript
// lib/api/social-accounts.ts
import { SocialAccount } from '@/lib/types';

export const socialAccountsApi = {
  // Список аккаунтов
  list: (platform?: string) =>
    apiFetch<SocialAccount[]>('/api/social-accounts/', { params: { platform } }),
  
  // Получение аккаунта
  get: (id: number) =>
    apiFetch<SocialAccount>(`/api/social-accounts/${id}/`),
  
  // Создание аккаунта
  create: (data: Partial<SocialAccount>) =>
    apiFetch<SocialAccount>('/api/social-accounts/', {
      method: 'POST',
      body: data
    }),
  
  // Обновление аккаунта
  update: (id: number, data: Partial<SocialAccount>) =>
    apiFetch<SocialAccount>(`/api/social-accounts/${id}/`, {
      method: 'PATCH',
      body: data
    }),
  
  // Удаление аккаунта
  delete: (id: number) =>
    apiFetch(`/api/social-accounts/${id}/`, { method: 'DELETE' }),
  
  // Тест подключения
  testConnection: (id: number) =>
    apiFetch(`/api/social-accounts/${id}/test_connection/`, {
      method: 'POST'
    }),
  
  // Отправка тестового сообщения
  sendTestMessage: (id: number, text: string) =>
    apiFetch(`/api/social-accounts/${id}/send_test_message/`, {
      method: 'POST',
      body: { text }
    })
};
```

### 2. Telegram Account Form

```tsx
// components/settings/telegram-account-form.tsx
'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/use-toast';
import { socialAccountsApi } from '@/lib/api';

interface TelegramAccountFormProps {
  account?: SocialAccount;
  onSuccess?: () => void;
}

export function TelegramAccountForm({ account, onSuccess }: TelegramAccountFormProps) {
  const { toast } = useToast();
  const [isTesting, setIsTesting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  
  const { register, handleSubmit, formState: { errors } } = useForm({
    defaultValues: account || {
      platform: 'telegram',
      name: '',
      username: '',
      access_token: '',
      extra: {}
    }
  });
  
  const onSubmit = async (data: any) => {
    setIsSaving(true);
    
    try {
      if (account) {
        await socialAccountsApi.update(account.id, data);
        toast({
          title: 'Успешно',
          description: 'Аккаунт обновлен'
        });
      } else {
        await socialAccountsApi.create(data);
        toast({
          title: 'Успешно',
          description: 'Аккаунт создан'
        });
      }
      
      onSuccess?.();
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось сохранить аккаунт',
        variant: 'destructive'
      });
    } finally {
      setIsSaving(false);
    }
  };
  
  const handleTestConnection = async () => {
    setIsTesting(true);
    
    try {
      const result = await socialAccountsApi.testConnection(account?.id!);
      
      if (result.success) {
        toast({
          title: 'Подключение успешно',
          description: 'Бот работает корректно'
        });
      } else {
        toast({
          title: 'Ошибка подключения',
          description: result.error,
          variant: 'destructive'
        });
      }
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось проверить подключение',
        variant: 'destructive'
      });
    } finally {
      setIsTesting(false);
    }
  };
  
  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Название</label>
          <Input {...register('name', { required: 'Обязательное поле' })} />
          {errors.name && (
            <p className="text-sm text-red-500">{errors.name.message}</p>
          )}
        </div>
        
        <div className="space-y-2">
          <label className="text-sm font-medium">Username</label>
          <Input 
            {...register('username', { required: 'Обязательное поле' })}
            placeholder="@channel_name"
          />
          {errors.username && (
            <p className="text-sm text-red-500">{errors.username.message}</p>
          )}
        </div>
      </div>
      
      <div className="space-y-2">
        <label className="text-sm font-medium">Bot Token</label>
        <Input 
          {...register('access_token', { required: 'Обязательное поле' })}
          type="password"
          placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
        />
        {errors.access_token && (
          <p className="text-sm text-red-500">{errors.access_token.message}</p>
        )}
      </div>
      
      <div className="flex gap-2">
        <Button type="submit" disabled={isSaving}>
          {isSaving ? 'Сохранение...' : 'Сохранить'}
        </Button>
        
        {account && (
          <Button 
            type="button" 
            variant="outline" 
            onClick={handleTestConnection}
            disabled={isTesting}
          >
            {isTesting ? 'Проверка...' : 'Проверить подключение'}
          </Button>
        )}
      </div>
    </form>
  );
}
```

### 3. Telegram Manager

```tsx
// components/settings/telegram-accounts-manager.tsx
'use client';

import { useState } from 'react';
import { useSocialAccounts } from '@/lib/hooks';
import { TelegramAccountForm } from './telegram-account-form';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus } from 'lucide-react';

export function TelegramAccountsManager() {
  const { accounts, loading, error, refetch } = useSocialAccounts('telegram');
  const [showForm, setShowForm] = useState(false);
  const [editingAccount, setEditingAccount] = useState<SocialAccount | null>(null);
  
  const handleSuccess = () => {
    setShowForm(false);
    setEditingAccount(null);
    refetch();
  };
  
  const handleEdit = (account: SocialAccount) => {
    setEditingAccount(account);
    setShowForm(true);
  };
  
  const handleDelete = async (account: SocialAccount) => {
    if (confirm('Вы уверены, что хотите удалить этот аккаунт?')) {
      try {
        await socialAccountsApi.delete(account.id);
        refetch();
      } catch (error) {
        console.error('Error deleting account:', error);
      }
    }
  };
  
  if (loading) {
    return <div>Загрузка...</div>;
  }
  
  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Telegram аккаунты</h2>
        <Button onClick={() => setShowForm(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Добавить аккаунт
        </Button>
      </div>
      
      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>
              {editingAccount ? 'Редактировать аккаунт' : 'Новый Telegram аккаунт'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <TelegramAccountForm 
              account={editingAccount} 
              onSuccess={handleSuccess} 
            />
          </CardContent>
        </Card>
      )}
      
      <div className="grid gap-4">
        {accounts.map((account) => (
          <Card key={account.id}>
            <CardHeader>
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle>{account.name}</CardTitle>
                  <p className="text-sm text-gray-500">{account.username}</p>
                </div>
                <div className="flex gap-2">
                  <Button 
                    variant="outline" 
                    onClick={() => handleEdit(account)}
                  >
                    Редактировать
                  </Button>
                  <Button 
                    variant="destructive" 
                    onClick={() => handleDelete(account)}
                  >
                    Удалить
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-600">
                Bot Token: {account.access_token ? '••••••••••••••••' : 'Не указан'}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
```

## Публикация

### 1. Post Publishing

```python
# core/services/publish_services.py
from .telegram_publisher import TelegramPublisher

class TelegramPublishService:
    """Сервис публикации постов в Telegram"""
    
    def __init__(self, social_account: SocialAccount):
        self.social_account = social_account
        self.publisher = TelegramPublisher(social_account.access_token)
    
    def publish(self, post: Post) -> Dict[str, Any]:
        """Публикация поста"""
        try:
            chat_id = self.social_account.extra.get('chat_id', self.social_account.username)
            
            # Определение типа контента
            if post.video:
                # Публикация видео
                result = self.publisher.send_video(
                    chat_id=chat_id,
                    video_url=post.video.url,
                    caption=post.text
                )
            elif post.image:
                # Публикация изображения
                result = self.publisher.send_photo(
                    chat_id=chat_id,
                    photo_url=post.image.url,
                    caption=post.text
                )
            else:
                # Публикация текста
                result = self.publisher.send_text(
                    chat_id=chat_id,
                    text=post.text
                )
            
            if result.get('ok'):
                return {
                    'success': True,
                    'external_id': str(result['result']['message_id']),
                    'url': f"https://t.me/{self.social_account.username}/{result['result']['message_id']}"
                }
            else:
                return {
                    'success': False,
                    'error': result.get('description', 'Unknown error')
                }
                
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error publishing post {post.id} to Telegram: {e}")
            return {
                'success': False,
                'error': str(e)
            }
```

### 2. Quick Publish

```python
# api/views.py
class PostViewSet(ModelViewSet):
    # ... другие методы ...
    
    @action(detail=True, methods=['post'])
    def quick_publish(self, request, pk=None):
        """Быстрая публикация поста"""
        post = self.get_object()
        
        serializer = QuickPublishSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        social_account_id = serializer.validated_data['social_account_id']
        
        try:
            social_account = SocialAccount.objects.get(
                id=social_account_id,
                client=post.client,
                platform='telegram'
            )
        except SocialAccount.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Social account not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Публикация
        service = TelegramPublishService(social_account)
        result = service.publish(post)
        
        if result['success']:
            # Обновление статуса поста
            post.status = 'published'
            post.published_at = timezone.now()
            post.save()
            
            # Создание записи в Schedule
            Schedule.objects.create(
                client=post.client,
                post=post,
                social_account=social_account,
                scheduled_at=timezone.now(),
                status='published',
                external_id=result['external_id'],
                published_at=timezone.now()
            )
        
        return Response(result)
```

### 3. Quick Publish Serializer

```python
# api/serializers.py
class QuickPublishSerializer(serializers.Serializer):
    social_account_id = serializers.IntegerField()
```

## Очередь задач

### 1. Celery Task

```python
# core/tasks.py
from celery import shared_task
from .services.publish_services import TelegramPublishService

@shared_task(bind=True, max_retries=3)
def publish_to_telegram(self, schedule_id):
    """Публикация в Telegram через Celery"""
    try:
        schedule = Schedule.objects.get(id=schedule_id)
        post = schedule.post
        social_account = schedule.social_account
        
        # Публикация
        service = TelegramPublishService(social_account)
        result = service.publish(post)
        
        # Обновление статуса
        if result['success']:
            schedule.status = 'published'
            schedule.external_id = result['external_id']
            schedule.published_at = timezone.now()
            schedule.save()
            
            # Обновление статуса поста
            post.status = 'published'
            post.published_at = timezone.now()
            post.save()
        else:
            schedule.status = 'failed'
            schedule.log = result['error']
            schedule.save()
        
        return result
        
    except Exception as exc:
        # Ретраи с экспоненциальной задержкой
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** retry_count))
        
        # После всех ретраев - помечаем как failed
        schedule = Schedule.objects.get(id=schedule_id)
        schedule.status = 'failed'
        schedule.log = f"Max retries exceeded: {exc}"
        schedule.save()
        
        return {'success': False, 'error': str(exc)}
```

### 2. Scheduled Publishing

```python
# api/views.py
class ScheduleViewSet(ModelViewSet):
    # ... другие методы ...
    
    @action(detail=True, methods=['post'])
    def publish_now(self, request, pk=None):
        """Немедленная публикация"""
        schedule = self.get_object()
        
        if schedule.status != 'pending':
            return Response({
                'success': False,
                'error': 'Schedule is not pending'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Запуск задачи
        from core.tasks import publish_to_telegram
        task = publish_to_telegram.delay(schedule.id)
        
        return Response({
            'success': True,
            'task_id': task.id
        })
```

## Тестирование

### 1. Unit Tests

```python
# core/tests/test_telegram_publisher.py
from django.test import TestCase
from unittest.mock import patch, MagicMock
from core.services.telegram_publisher import TelegramPublisher

class TelegramPublisherTest(TestCase):
    def setUp(self):
        self.publisher = TelegramPublisher('test_token')
    
    @patch('requests.post')
    def test_send_text(self, mock_post):
        """Тест отправки текстового сообщения"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'ok': True,
            'result': {'message_id': 123}
        }
        mock_post.return_value = mock_response
        
        result = self.publisher.send_text('@test_channel', 'Test message')
        
        self.assertTrue(result['ok'])
        self.assertEqual(result['result']['message_id'], 123)
    
    @patch('requests.post')
    def test_send_photo(self, mock_post):
        """Тест отправки фото"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'ok': True,
            'result': {'message_id': 456}
        }
        mock_post.return_value = mock_response
        
        with patch('requests.get') as mock_get:
            mock_get.return_value.content = b'test_image_data'
            
            result = self.publisher.send_photo(
                '@test_channel',
                'http://example.com/image.jpg',
                'Test caption'
            )
            
            self.assertTrue(result['ok'])
            self.assertEqual(result['result']['message_id'], 456)
```

### 2. Integration Tests

```python
# core/tests/test_telegram_integration.py
from django.test import TestCase
from core.models import Client, SocialAccount, Post
from core.services.telegram_publisher import TelegramPublishService

class TelegramIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client.objects.create(
            name='Test Client',
            slug='test-client'
        )
        
        self.social_account = SocialAccount.objects.create(
            client=self.client,
            platform='telegram',
            name='Test Channel',
            username='@test_channel',
            access_token='test_token'
        )
    
    @patch('core.services.telegram_publisher.TelegramPublisher.send_text')
    def test_publish_service(self, mock_send_text):
        """Тест сервиса публикации"""
        mock_send_text.return_value = {
            'ok': True,
            'result': {'message_id': 123}
        }
        
        service = TelegramPublishService(self.social_account)
        result = service.publish_text('Test message')
        
        self.assertTrue(result['success'])
        self.assertEqual(result['external_id'], '123')
```

### 3. Management Command

```python
# management/commands/test_telegram.py
from django.core.management.base import BaseCommand
from core.services.telegram_publisher import TelegramPublisher

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--token', type=str, help='Telegram Bot Token')
        parser.add_argument('--chat-id', type=str, help='Chat ID or @username')
    
    def handle(self, *args, **options):
        token = options['token']
        chat_id = options['chat_id']
        
        if not token or not chat_id:
            self.stdout.write(
                self.style.ERROR('Please provide --token and --chat-id')
            )
            return
        
        publisher = TelegramPublisher(token)
        
        try:
            # Тест отправки сообщения
            result = publisher.send_text(
                chat_id=chat_id,
                text="Тестовое сообщение от Django management command"
            )
            
            if result.get('ok'):
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Message sent successfully! Message ID: {result['result']['message_id']}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"Failed to send message: {result.get('description')}"
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error: {e}")
            )
```

---

**Далее:**
- [Instagram](./instagram.md) - Интеграция с Instagram
- [YouTube](./youtube.md) - Интеграция с YouTube
- [Deployment](../07-deployment/docker.md) - Деплоймент системы
