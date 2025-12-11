# Telegram Authentication

В этом документе описана система аутентификации через Telegram WebApp.

## Содержание

- [Требования](#требования)
- [Telegram WebApp](#telegram-webapp)
- [Backend аутентификация](#backend-аутентификация)
- [Frontend интеграция](#frontend-интеграция)
- [Dev mode](#dev-mode)
- [Тестирование](#тестирование)

## Требования

1. **Telegram Bot** (созданный через @BotFather)
2. **Telegram WebApp** - для аутентификации
3. **Django backend** с JWT аутентификацией
4. **Frontend** (Next.js/React)

## Telegram WebApp

### 1. Создание WebApp

Telegram WebApp позволяет запускать веб-приложения прямо в Telegram.

#### Настройка бота

1. **Найдите @BotFather** в Telegram
2. **Отправьте команду** `/mybots`
3. **Выберите вашего бота**
4. **Выберите "Edit Bot"**
5. **Выберите "Edit Webhook"**
6. **Укажите URL** вашего WebApp (например, `https://your-domain.com/telegram-webapp`)

#### Пример WebApp

```html
<!DOCTYPE html>
<html>
<head>
    <title>Telegram Auth</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
    <div id="app"></div>
    
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <script>
        // Инициализация Telegram WebApp
        const tg = window.Telegram.WebApp;
        
        // Готовим приложение
        tg.ready();
        
        // Функция аутентификации
        function authenticate() {
            const user = tg.initDataUnsafe.user;
            
            if (user) {
                // Отправка данных на backend
                fetch('/api/auth/telegram', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        id: user.id,
                        first_name: user.first_name,
                        last_name: user.last_name,
                        username: user.username,
                        photo_url: user.photo_url,
                        hash: tg.initDataUnsafe.hash
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Сохранение токена
                        localStorage.setItem('token', data.token);
                        // Перенаправление в основное приложение
                        window.location.href = '/dashboard';
                    } else {
                        alert('Authentication failed');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                });
            } else {
                alert('User data not available');
            }
        }
        
        // Автоматическая аутентификация при загрузке
        if (tg.initDataUnsafe.user) {
            authenticate();
        }
    </script>
</body>
</html>
```

### 2. Telegram Login Widget

Альтернативный способ - использование Telegram Login Widget.

```html
<div id="telegram-login" class="telegram-login-button"></div>

<script async src="https://telegram.org/js/telegram-widget.js?22" 
        data-telegram-login="your_bot_username" 
        data-size="large" 
        data-auth-url="https://your-domain.com/api/auth/telegram" 
        data-request-access="write"></script>
```

## Backend аутентификация

### 1. Telegram Auth View

```python
# api/views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
from core.models import Client, UserTenantRole
import hashlib
import hmac
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def telegram_auth(request):
    """Аутентификация через Telegram"""
    try:
        import json
        data = json.loads(request.body)
        
        # Проверка хеша
        if not validate_telegram_data(data):
            return JsonResponse({
                'success': False,
                'error': 'Invalid hash'
            }, status=400)
        
        telegram_id = str(data['id'])
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        username = data.get('username', '')
        photo_url = data.get('photo_url', '')
        
        # Поиск или создание пользователя
        user, created = User.objects.get_or_create(
            username=f"telegram_{telegram_id}",
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'email': f"{telegram_id}@telegram.fake"
            }
        )
        
        # Обновление данных пользователя
        user.telegram_id = telegram_id
        user.first_name = first_name
        user.last_name = last_name
        user.username = username or f"telegram_{telegram_id}"
        user.photo_url = photo_url
        user.save()
        
        # Генерация JWT токенов
        refresh = RefreshToken.for_user(user)
        
        # Получение информации о клиенте
        client_info = get_client_info(user)
        
        return JsonResponse({
            'success': True,
            'user': {
                'id': user.id,
                'telegram_id': user.telegram_id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'photo_url': user.photo_url,
                'is_dev': user.is_dev
            },
            'client': client_info['client'],
            'role': client_info['role'],
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }
        })
        
    except Exception as e:
        logger.error(f"Telegram auth error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def validate_telegram_data(data):
    """Проверка подлинности данных от Telegram"""
    bot_token = settings.TELEGRAM_BOT_TOKEN
    
    # Формируем строку для проверки
    check_string = []
    for key in sorted(data.keys()):
        if key != 'hash':
            value = data[key]
            if isinstance(value, dict):
                value = json.dumps(value, separators=(',', ':'), sort_keys=True)
            check_string.append(f"{key}={value}")
    
    check_string = '\n'.join(check_string)
    
    # Создаем хеш
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    hash_value = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    
    return hash_value == data.get('hash')

def get_client_info(user):
    """Получение информации о клиенте и роли пользователя"""
    # Поиск роли пользователя
    role_obj = UserTenantRole.objects.filter(user=user).first()
    
    if role_obj:
        return {
            'client': {
                'id': role_obj.client.id,
                'name': role_obj.client.name,
                'slug': role_obj.client.slug
            },
            'role': role_obj.role
        }
    else:
        # Создаем роль по умолчанию для dev пользователей
        if user.is_dev:
            client = Client.objects.first()
            if client:
                role_obj = UserTenantRole.objects.create(
                    user=user,
                    client=client,
                    role='owner'
                )
                return {
                    'client': {
                        'id': client.id,
                        'name': client.name,
                        'slug': client.slug
                    },
                    'role': 'owner'
                }
        
        return {'client': None, 'role': None}
```

### 2. Dev Mode Auth

```python
@csrf_exempt
@require_http_methods(["PUT"])
def telegram_dev_login(request):
    """Dev mode login - создает пользователя с telegram_id=1"""
    if not settings.DEBUG:
        return JsonResponse({
            'success': False,
            'error': 'Dev mode only available in DEBUG mode'
        }, status=400)
    
    try:
        # Создаем или получаем пользователя
        user, created = User.objects.get_or_create(
            telegram_id='1',
            defaults={
                'username': 'dev_user',
                'first_name': 'Dev',
                'last_name': 'User',
                'email': 'dev@example.com',
                'is_dev': True
            }
        )
        
        # Генерация JWT токенов
        refresh = RefreshToken.for_user(user)
        
        # Получение информации о клиенте
        client_info = get_client_info(user)
        
        return JsonResponse({
            'success': True,
            'user': {
                'id': user.id,
                'telegram_id': user.telegram_id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'photo_url': user.photo_url,
                'is_dev': user.is_dev
            },
            'client': client_info['client'],
            'role': client_info['role'],
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }
        })
        
    except Exception as e:
        logger.error(f"Dev login error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
```

### 3. Logout

```python
@csrf_exempt
@require_http_methods(["DELETE"])
def telegram_logout(request):
    """Logout пользователя"""
    try:
        # В простой реализации просто удаляем токен
        # В реальной системе можно использовать blacklist токенов
        
        return JsonResponse({
            'success': True,
            'message': 'Logged out successfully'
        })
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
```

### 4. URLs

```python
# api/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # ... другие URL-ы ...
    path('auth/telegram/', views.telegram_auth, name='telegram_auth'),
    path('auth/telegram/dev/', views.telegram_dev_login, name='telegram_dev_login'),
    path('auth/telegram/logout/', views.telegram_logout, name='telegram_logout'),
    path('client/info/', views.get_client_info, name='client_info'),
]
```

## Frontend интеграция

### 1. Telegram Auth Component

```tsx
// components/auth/TelegramAuth.tsx
'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/contexts/auth-context';

export function TelegramAuth() {
  const { login } = useAuth();
  const [isInTelegram, setIsInTelegram] = useState(false);
  
  const authMutation = useMutation({
    mutationFn: (userData: TelegramUser) => {
      return fetch('/api/auth/telegram', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(userData)
      }).then(res => res.json());
    },
    onSuccess: (data) => {
      if (data.success) {
        login(data);
      } else {
        console.error('Auth failed:', data.error);
      }
    }
  });
  
  const handleTelegramAuth = () => {
    // Проверка, что мы в Telegram
    if (window.Telegram?.WebApp) {
      const user = window.Telegram.WebApp.initDataUnsafe.user;
      if (user) {
        authMutation.mutate(user);
      }
    }
  };
  
  const handleDevLogin = () => {
    fetch('/api/auth/telegram/dev', {
      method: 'PUT'
    })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        login(data);
      }
    });
  };
  
  return (
    <div className="space-y-4">
      <div className="text-center">
        <h2 className="text-2xl font-bold">Добро пожаловать в Zavod</h2>
        <p className="text-gray-600">Аутентифицируйтесь через Telegram</p>
      </div>
      
      <div className="space-y-2">
        {window.Telegram?.WebApp ? (
          <Button 
            onClick={handleTelegramAuth}
            disabled={authMutation.isPending}
            className="w-full"
          >
            {authMutation.isPending ? 'Вход...' : 'Войти через Telegram'}
          </Button>
        ) : (
          <Button 
            onClick={handleDevLogin}
            className="w-full"
          >
            Dev Login
          </Button>
        )}
      </div>
      
      {authMutation.error && (
        <p className="text-red-500">Ошибка аутентификации</p>
      )}
    </div>
  );
}
```

### 2. Auth Context

```tsx
// lib/contexts/auth-context.tsx
'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authApi } from '@/lib/api';

interface User {
  id: number;
  telegram_id: string;
  first_name: string;
  last_name: string;
  username: string;
  photo_url: string | null;
  is_dev: boolean;
}

interface Client {
  id: number;
  name: string;
  slug: string;
}

interface AuthContextType {
  user: User | null;
  client: Client | null;
  role: string | null;
  loading: boolean;
  login: (data: AuthResponse) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [client, setClient] = useState<Client | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Проверка аутентификации при загрузке
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const token = localStorage.getItem('token');
      if (token) {
        const response = await authApi.clientInfo();
        setUser(response.data.user);
        setClient(response.data.client);
        setRole(response.data.role);
      }
    } catch (error) {
      // Пользователь не авторизован
      console.error('Auth check failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const login = (data: AuthResponse) => {
    setUser(data.user);
    setClient(data.client);
    setRole(data.role);
    localStorage.setItem('token', data.tokens.access);
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch (error) {
      console.error('Logout failed:', error);
    } finally {
      setUser(null);
      setClient(null);
      setRole(null);
      localStorage.removeItem('token');
    }
  };

  return (
    <AuthContext.Provider value={{ user, client, role, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
```

### 3. API Functions

```tsx
// lib/api/auth.ts
import apiClient from './client';

export interface AuthResponse {
  success: boolean;
  user: {
    id: number;
    telegram_id: string;
    first_name: string;
    last_name: string;
    username: string;
    photo_url: string | null;
    is_dev: boolean;
  };
  client: {
    id: number;
    name: string;
    slug: string;
  } | null;
  role: string | null;
  tokens: {
    access: string;
    refresh: string;
  };
}

export const authApi = {
  // Telegram аутентификация
  telegram: (userData: TelegramUser) =>
    apiClient.post<AuthResponse>('/api/auth/telegram', userData),
  
  // Dev mode login
  devLogin: () =>
    apiClient.put<AuthResponse>('/api/auth/telegram/dev'),
  
  // Logout
  logout: () =>
    apiClient.delete('/api/auth/telegram/logout'),
  
  // Получение информации о клиенте
  clientInfo: () =>
    apiClient.get('/api/client/info/'),
};
```

### 4. Protected Route

```tsx
// components/layout/protected-route.tsx
'use client';

import { useAuth } from '@/lib/contexts/auth-context';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { TelegramAuth } from '@/components/auth/telegram-auth';

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { loading, user } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner />
      </div>
    );
  }

  if (!user) {
    return <TelegramAuth />;
  }

  return <>{children}</>;
}
```

## Dev mode

### 1. Dev User

В dev mode создается пользователь с telegram_id=1, который автоматически становится owner первого клиента.

```python
# settings.py
DEBUG = True
DEV_MODE = True
```

### 2. Dev Login Endpoint

```python
# api/views.py
@csrf_exempt
@require_http_methods(["PUT"])
def telegram_dev_login(request):
    """Dev mode login - создает пользователя с telegram_id=1"""
    if not settings.DEBUG:
        return JsonResponse({
            'success': False,
            'error': 'Dev mode only available in DEBUG mode'
        }, status=400)
    
    try:
        # Создаем или получаем пользователя
        user, created = User.objects.get_or_create(
            telegram_id='1',
            defaults={
                'username': 'dev_user',
                'first_name': 'Dev',
                'last_name': 'User',
                'email': 'dev@example.com',
                'is_dev': True
            }
        )
        
        # Генерация JWT токенов
        refresh = RefreshToken.for_user(user)
        
        # Получение информации о клиенте
        client_info = get_client_info(user)
        
        return JsonResponse({
            'success': True,
            'user': {
                'id': user.id,
                'telegram_id': user.telegram_id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'photo_url': user.photo_url,
                'is_dev': user.is_dev
            },
            'client': client_info['client'],
            'role': client_info['role'],
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }
        })
        
    except Exception as e:
        logger.error(f"Dev login error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
```

### 3. Frontend Dev Login

```tsx
// components/auth/dev-login.tsx
'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/contexts/auth-context';

export function DevLogin() {
  const { login } = useAuth();
  const [loading, setLoading] = useState(false);
  
  const handleDevLogin = async () => {
    setLoading(true);
    
    try {
      const response = await fetch('/api/auth/telegram/dev', {
        method: 'PUT'
      });
      
      const data = await response.json();
      
      if (data.success) {
        login(data);
      } else {
        console.error('Dev login failed:', data.error);
      }
    } catch (error) {
      console.error('Dev login error:', error);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="space-y-4">
      <div className="text-center">
        <h2 className="text-2xl font-bold">Dev Mode</h2>
        <p className="text-gray-600">Login as development user</p>
      </div>
      
      <Button 
        onClick={handleDevLogin}
        disabled={loading}
        className="w-full"
      >
        {loading ? 'Вход...' : 'Dev Login'}
      </Button>
    </div>
  );
}
```

## Тестирование

### 1. Backend Tests

```python
# api/tests/test_telegram_auth.py
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch
import json

User = get_user_model()

class TelegramAuthTest(TestCase):
    def test_telegram_auth_success(self):
        """Тест успешной аутентификации"""
        user_data = {
            'id': 123456789,
            'first_name': 'Test',
            'last_name': 'User',
            'username': 'testuser',
            'hash': 'valid_hash'
        }
        
        with patch('api.views.validate_telegram_data', return_value=True):
            response = self.client.post(
                reverse('api:telegram_auth'),
                data=json.dumps(user_data),
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data['success'])
            self.assertEqual(data['user']['telegram_id'], '123456789')
    
    def test_telegram_auth_invalid_hash(self):
        """Тест аутентификации с невалидным хешем"""
        user_data = {
            'id': 123456789,
            'first_name': 'Test',
            'last_name': 'User',
            'username': 'testuser',
            'hash': 'invalid_hash'
        }
        
        response = self.client.post(
            reverse('api:telegram_auth'),
            data=json.dumps(user_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
    
    def test_dev_login(self):
        """Тест dev mode login"""
        with self.settings(DEBUG=True):
            response = self.client.put(reverse('api:telegram_dev_login'))
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data['success'])
            self.assertTrue(data['user']['is_dev'])
```

### 2. Frontend Tests

```tsx
// __tests__/components/TelegramAuth.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { TelegramAuth } from '@/components/auth/telegram-auth';
import { AuthProvider } from '@/lib/contexts/auth-context';

// Mock Telegram WebApp
Object.defineProperty(window, 'Telegram', {
  value: {
    WebApp: {
      initDataUnsafe: {
        user: {
          id: 123456789,
          first_name: 'Test',
          last_name: 'User',
          username: 'testuser'
        }
      }
    }
  },
  writable: true
});

jest.mock('@/lib/api', () => ({
  authApi: {
    telegram: jest.fn(),
    clientInfo: jest.fn()
  }
}));

const mockAuthApi = authApi as jest.Mocked<typeof authApi>;

describe('TelegramAuth', () => {
  it('renders auth form', () => {
    render(
      <AuthProvider>
        <TelegramAuth />
      </AuthProvider>
    );
    
    expect(screen.getByText('Добро пожаловать в Zavod')).toBeInTheDocument();
    expect(screen.getByText('Войти через Telegram')).toBeInTheDocument();
  });

  it('handles telegram auth', async () => {
    mockAuthApi.telegram.mockResolvedValue({
      success: true,
      user: { id: 1, telegram_id: '123456789' }
    } as any);
    
    render(
      <AuthProvider>
        <TelegramAuth />
      </AuthProvider>
    );
    
    fireEvent.click(screen.getByText('Войти через Telegram'));
    
    await waitFor(() => {
      expect(mockAuthApi.telegram).toHaveBeenCalled();
    });
  });
});
```

### 3. Management Command

```python
# management/commands/test_telegram_auth.py
from django.core.management.base import BaseCommand
from django.test.client import Client
import json

class Command(BaseCommand):
    def handle(self, *args, **options):
        client = Client()
        
        # Тест dev login
        response = client.put('/api/auth/telegram/dev')
        result = response.json()
        
        if result['success']:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dev login successful! User: {result['user']['username']}"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"Dev login failed: {result['error']}")
            )
```

---

**Далее:**
- [Authentication](./authentication.md) - Общая система аутентификации
- [API Overview](./overview.md) - Обзор API
- [Frontend Integration](../05-frontend/overview.md) - Frontend интеграция
