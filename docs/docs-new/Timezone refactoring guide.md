# Руководство по рефакторингу timezone в CRM

## Текущие проблемы

1. **Python бот**: Использует `timezone.localtime()` и `timezone.get_current_timezone()` — это серверная timezone, а не клиентская
2. **React компонент**: Работает с датами через `new Date()`, но не учитывает timezone tenant
3. **Нет единого источника правды** для timezone клиента

---

## Архитектура решения

### 1. База данных (добавить если нет)

```sql
-- В таблице tenants
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'Europe/Moscow';

```

### 2. Модели Django (models.py)

```python
from django.db import models
from zoneinfo import ZoneInfo

class Tenant(models.Model):
    timezone = models.CharField(max_length=50, default='Europe/Moscow')
    
    def get_timezone(self):
        """Возвращает ZoneInfo объект для tenant"""
        try:
            return ZoneInfo(self.timezone)
        except:
            return ZoneInfo('Europe/Moscow')

class Event(models.Model):
    # Всегда храним в UTC
    start_time = models.DateTimeField()  # UTC
    end_time = models.DateTimeField()    # UTC
    
    def get_local_start(self, tenant):
        """Конвертирует start_time в timezone клиента"""
        return self.start_time.astimezone(tenant.get_timezone())
```

---

## Изменения в Python боте

### Файл: run_telegram_tasks_bot.py

#### Шаг 1: Обновить функции конвертации

```python
# ЗАМЕНИТЬ функции _ensure_aware и _format_dt

def _get_tenant_timezone(tenant_id: int) -> ZoneInfo:
    """Получить timezone конкретного tenant"""
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT timezone FROM {_map_schema()}.tenants WHERE id = %s",
            [tenant_id]
        )
        row = cursor.fetchone()
        if row and row[0]:
            try:
                return ZoneInfo(row[0])
            except ZoneInfoNotFoundError:
                pass
    return ZoneInfo("Europe/Moscow")  # fallback


def _to_tenant_local(dt: datetime, tenant_tz: ZoneInfo) -> datetime:
    """Конвертировать UTC datetime в timezone клиента"""
    if dt.tzinfo is None:
        # Если naive, считаем что это UTC
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(tenant_tz)


def _format_dt(dt: datetime, tenant_tz: ZoneInfo) -> str:
    """Форматировать datetime в локальной timezone клиента"""
    local_dt = _to_tenant_local(dt, tenant_tz)
    return local_dt.strftime("%d.%m.%Y %H:%M")


def _format_time_range(start: datetime, end: datetime, tenant_tz: ZoneInfo) -> str:
    """Форматировать временной диапазон в timezone клиента"""
    start_local = _to_tenant_local(start, tenant_tz)
    end_local = _to_tenant_local(end, tenant_tz)
    
    if start_local.date() != end_local.date():
        return f"{start_local.strftime('%d.%m.%Y %H:%M')}–{end_local.strftime('%d.%m.%Y %H:%M')}"
    return f"{start_local.strftime('%d.%m.%Y %H:%M')}–{end_local.strftime('%H:%M')}"
```

#### Шаг 2: Обновить создание событий

```python
# В функции handle_meeting_confirm (строки 1553-1655)
# ИЗМЕНИТЬ создание start_dt и end_dt

# СТАРЫЙ КОД (строки 1529-1532):
# start_dt = datetime.combine(selected_date, chosen_time)
# if timezone.is_naive(start_dt):
#     start_dt = timezone.make_aware(start_dt, timezone.get_current_timezone())

# НОВЫЙ КОД:
tenant_id = data.get("tenant_id")
tenant_tz = _get_tenant_timezone(tenant_id)

# Пользователь выбрал время в СВОЕЙ timezone
start_dt_local = datetime.combine(selected_date, chosen_time)
# Делаем aware в timezone клиента
start_dt_local = start_dt_local.replace(tzinfo=tenant_tz)
# Конвертируем в UTC для сохранения в БД
start_dt = start_dt_local.astimezone(ZoneInfo("UTC"))
end_dt = start_dt + timedelta(minutes=duration_minutes)
```

#### Шаг 3: Обновить отображение времени

```python
# В функции _confirmation_text и других местах
# СТАРОЕ:
# text.append(f"📅 Дата: {_format_dt(start_dt)}")

# НОВОЕ:
tenant_id = data.get("tenant_id")
tenant_tz = _get_tenant_timezone(tenant_id)
text.append(f"📅 Дата: {_format_dt(start_dt, tenant_tz)}")
```

#### Шаг 4: Обновить scheduler задач

```python
# В функции send_task_notifications (если она есть)
# Проверка задач для отправки

def should_send_notification(task, now_utc: datetime) -> bool:
    """
    Проверяет, нужно ли отправить уведомление
    task.scheduled_time хранится в UTC
    """
    # Просто сравниваем UTC с UTC
    return task.scheduled_time <= now_utc

# При отправке уведомления - показываем время в timezone клиента
def format_notification_message(task):
    tenant_tz = _get_tenant_timezone(task.tenant_id)
    local_time = _to_tenant_local(task.scheduled_time, tenant_tz)
    return f"Напоминание: встреча в {local_time.strftime('%H:%M')}"
```

---

## Изменения в React компоненте

### Файл: clients-schedule.tsx

#### Шаг 1: Добавить timezone в API responses

```typescript
// В типах API (добавить в lib/api/crm.ts или где у вас типы)
type Tenant = {
  id: number;
  timezone: string; // "Europe/Helsinki", "America/New_York", etc
  // ... остальные поля
}

type Event = {
  id: number;
  start_time: string; // ISO 8601 в UTC: "2026-02-01T10:00:00Z"
  end_time: string;
  // ... остальные поля
}
```

#### Шаг 2: Получить timezone tenant в компоненте

```typescript
// В компоненте ClientsSchedulePage
export default function ClientsSchedulePage() {
  const [tenantTimezone, setTenantTimezone] = useState<string>('UTC');
  
  useEffect(() => {
    // Загрузить timezone из API tenant
    async function loadTenantSettings() {
      try {
        const tenant = await getTenantSettings(); // ваш API
        setTenantTimezone(tenant.timezone || 'UTC');
      } catch (err) {
        console.error('Failed to load tenant timezone', err);
      }
    }
    loadTenantSettings();
  }, []);
  
  // ...
}
```

#### Шаг 3: Конвертация дат в компоненте

```typescript
// Функция для конвертации UTC в локальное время клиента
function formatTimeInTenantTz(utcTime: string, timezone: string): string {
  return new Date(utcTime).toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: timezone
  });
}

function formatDateTimeInTenantTz(utcTime: string, timezone: string): string {
  return new Date(utcTime).toLocaleString('ru-RU', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: timezone
  });
}

// ИЗМЕНИТЬ функцию formatTimeRange (строки 71-79):
function formatTimeRange(start: string, end: string, timezone: string) {
  const startDate = new Date(start);
  if (Number.isNaN(startDate.getTime())) return '';
  
  const startTime = startDate.toLocaleTimeString('ru-RU', { 
    hour: '2-digit', 
    minute: '2-digit',
    timeZone: timezone 
  });
  
  const endDate = new Date(end);
  if (Number.isNaN(endDate.getTime())) return startTime;
  
  const endTime = endDate.toLocaleTimeString('ru-RU', { 
    hour: '2-digit', 
    minute: '2-digit',
    timeZone: timezone 
  });
  
  return startTime === endTime ? startTime : `${startTime}–${endTime}`;
}
```

#### Шаг 4: Обновить создание событий

```typescript
// При сохранении availability или события
async function handleAvailabilitySave(event: FormEvent<HTMLFormElement>) {
  event.preventDefault();
  
  // Пользователь ввёл время в UI
  const [hours, minutes] = availabilityTime.split(':').map(Number);
  
  // Создаём дату в timezone клиента
  const localDate = new Date(availabilityDate);
  localDate.setHours(hours, minutes, 0, 0);
  
  // Конвертируем в UTC для отправки на сервер
  const utcDate = new Date(localDate.toLocaleString('en-US', {
    timeZone: 'UTC'
  }));
  
  // Отправляем на сервер в ISO формате (UTC)
  await crmAvailabilityEventsApi.create({
    start_time: utcDate.toISOString(), // "2026-02-01T08:00:00.000Z"
    duration_minutes: parseInt(availabilityDuration),
    // ...
  });
}
```

#### Шаг 5: Передать timezone в дочерние компоненты

```typescript
// Обновить eventToCalendarItem
function eventToCalendarItem(
  event: Event,
  contactsById: Map<number, Contact>,
  eventTypesById: Map<number, EventType>,
  tenantTimezone: string  // ДОБАВИТЬ параметр
): CalendarEventItem | null {
  // ...
  return {
    // ...
    time: formatTimeRange(event.start_time, event.end_time, tenantTimezone),
    // ...
  };
}

// В useMemo где создаёте items
const items = useMemo(() => {
  // ...
  const eventItems = events.map(e => 
    eventToCalendarItem(e, contactsById, eventTypesById, tenantTimezone)
  );
  // ...
}, [events, contacts, eventTypes, tenantTimezone]); // добавить tenantTimezone
```

---

## Итоговая схема работы

### 1. При создании события/слота

```
Пользователь выбирает → 14:00 в UI (его локальное время)
                         ↓
React конвертирует      → в UTC (например, 11:00 UTC)
                         ↓
API получает            → "2026-02-01T11:00:00Z"
                         ↓
БД сохраняет            → timestamp in UTC
```

### 2. При отображении события

```
БД возвращает           → "2026-02-01T11:00:00Z" (UTC)
                         ↓
React получает          → UTC string
                         ↓
React конвертирует      → в timezone клиента (14:00)
                         ↓
Пользователь видит      → 14:00 (его локальное время)
```

### 3. При отправке Telegram уведомления

```
Scheduler проверяет     → scheduled_time <= NOW() (оба в UTC)
                         ↓
Если пора отправить     → получаем tenant.timezone
                         ↓
Конвертируем для текста → "Встреча в 14:00" (локальное)
                         ↓
Отправляем уведомление
```

---

## Критические правила

✅ **ВСЕГДА:**
- Храните в БД только UTC
- Конвертируйте в локальное время только при отображении
- Используйте `ZoneInfo` в Python, `timeZone` в JavaScript

❌ **НИКОГДА:**
- Не храните локальное время в БД
- Не используйте `timezone.get_current_timezone()` (это серверное время!)
- Не делайте конвертации при записи в БД

---

## Тестирование

```python
# Тест в Python
def test_timezone_conversion():
    tenant_tz = ZoneInfo("America/New_York")  # UTC-5
    utc_time = datetime(2026, 2, 1, 15, 0, tzinfo=ZoneInfo("UTC"))
    
    local = utc_time.astimezone(tenant_tz)
    assert local.hour == 10  # 15:00 UTC = 10:00 NY
```

```typescript
// Тест в JavaScript
const utcTime = "2026-02-01T15:00:00Z";
const nyTime = new Date(utcTime).toLocaleTimeString('en-US', {
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'America/New_York'
});
console.log(nyTime); // "10:00 AM"
```

---

## План миграции

1. ✅ Добавить колонку `timezone` в таблицу `tenants`
2. ✅ Обновить функции конвертации в Python боте
3. ✅ Обновить API для возврата timezone tenant
4. ✅ Обновить React компонент для использования tenant timezone
5. ✅ Протестировать с клиентами в разных timezone
6. ✅ Убрать все использования `timezone.get_current_timezone()`

---

## FAQ

**Q: А что если пользователь в другой timezone чем tenant?**  
A: Добавьте `users.timezone` и используйте её с приоритетом над `tenant.timezone`

**Q: Как быть с летним/зимним временем?**  
A: `ZoneInfo` и `timeZone` автоматически учитывают DST. Просто используйте правильные названия timezone ("Europe/Helsinki", не "UTC+2")

**Q: Можно ли хранить offset вместо timezone name?**  
A: Нет! Offset меняется с летним временем. Только IANA названия ("Europe/Helsinki")