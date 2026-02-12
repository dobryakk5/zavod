# Публичный доступ к документам базы знаний (Share Links)

## Описание проблемы

Ранее при создании публичной share-ссылки вида `https://fibonatty.ru/kb/share/{token}` вложенные статьи продолжали ссылаться на приватные URL (`/kb/{id}`), что делало их недоступными для публичных пользователей.

## Решение

Обновлённая система включает:

1. **Режим публичного просмотра** в компоненте `KnowledgeBaseTab`
2. **Автоматическая генерация share-ссылок** для вложенных документов
3. **API endpoints** для управления публичным доступом
4. **База данных** для хранения share-токенов

---

## Структура файлов

```
/components/
  knowledge-base-tab.tsx       # Обновлённый компонент с поддержкой share-режима

/app/kb/share/[shareToken]/
  page.tsx                     # Публичная страница просмотра (используйте kb-share-page.tsx)

/app/api/kb/
  [id]/share-url/
    route.ts                   # GET/DELETE для управления share-ссылкой документа
  share/[shareToken]/
    route.ts                   # GET для получения документа по токену

/prisma/migrations/
  xxx-kb-share.sql            # Миграция базы данных
```

---

## Миграция базы данных

Выполните SQL из `migration-kb-share.sql`:

```bash
psql -U your_user -d your_database -f migration-kb-share.sql
```

Или используйте Prisma:

```prisma
model KbDocumentShare {
  id             Int       @id @default(autoincrement())
  documentId     Int       @map("document_id")
  shareToken     String    @unique @map("share_token") @db.VarChar(255)
  isActive       Boolean   @default(true) @map("is_active")
  viewCount      Int       @default(0) @map("view_count")
  createdAt      DateTime  @default(now()) @map("created_at")
  lastViewedAt   DateTime? @map("last_viewed_at")
  expiresAt      DateTime? @map("expires_at")
  createdBy      Int?      @map("created_by")
  
  document       KbDocument @relation(fields: [documentId], references: [id], onDelete: Cascade)
  creator        User?      @relation(fields: [createdBy], references: [id])

  @@index([shareToken], map: "idx_kb_document_share_token")
  @@index([documentId], map: "idx_kb_document_share_document")
  @@map("kb_document_share")
}
```

---

## Использование

### 1. Создание share-ссылки

```typescript
// Пользователь нажимает "Поделиться" на документе
const response = await fetch(`/api/kb/${documentId}/share-url`);
const { shareUrl } = await response.json();

// shareUrl = "https://fibonatty.ru/kb/share/45b2309e4093abab9f23a234c8006108"
```

### 2. Публичная страница

```tsx
// app/kb/share/[shareToken]/page.tsx
import KbSharePage from '@/components/kb-share-page';
export default KbSharePage;
```

### 3. Приватная страница (настройки)

```tsx
// app/settings/page.tsx
import { KnowledgeBaseTab } from '@/components/knowledge-base-tab';

export default function SettingsPage() {
  return (
    <KnowledgeBaseTab 
      shareMode={false} // обычный режим с редактированием
    />
  );
}
```

---

## Как это работает

### Приватный режим (`shareMode={false}`)

- Показаны кнопки "Создать вложенную", "Архивировать", "Открыть"
- При клике на документ → переход на `/kb/{id}`
- Полный доступ к редактированию

### Публичный режим (`shareMode={true}`)

- Скрыты все кнопки редактирования
- При клике на документ → вызов `getShareUrl(id)` → переход на публичный URL
- Только чтение

### Алгоритм получения share-ссылки

```typescript
const handleOpen = async () => {
  if (shareMode && getShareUrl) {
    // 1. Запрос к API: GET /api/kb/{id}/share-url
    const shareUrl = await getShareUrl(node.id);
    
    // 2. Переход на публичный URL
    window.location.href = shareUrl;
    // Например: https://fibonatty.ru/kb/share/abc123...
  } else {
    // Обычный переход для авторизованных пользователей
    router.push(`/kb/${id}`);
  }
};
```

---

## API Endpoints

### `GET /api/kb/[id]/share-url`

Создаёт или возвращает существующую share-ссылку для документа.

**Response:**
```json
{
  "shareUrl": "https://fibonatty.ru/kb/share/45b2309e...",
  "shareToken": "45b2309e4093abab9f23a234c8006108"
}
```

### `DELETE /api/kb/[id]/share-url`

Отключает публичный доступ к документу (деактивирует все share-токены).

**Response:**
```json
{
  "success": true
}
```

### `GET /api/kb/share/[shareToken]`

Возвращает документ и все его вложенные страницы (только неархивированные).

**Response:**
```json
[
  {
    "id": 5,
    "title": "Главная статья",
    "icon": "📘",
    "content": {...},
    "parent_document": null,
    "updated_at": "2026-02-12T10:30:00Z"
  },
  {
    "id": 6,
    "title": "Вложенная статья",
    "icon": "📄",
    "content": {...},
    "parent_document": 5,
    "updated_at": "2026-02-12T11:00:00Z"
  }
]
```

---

## Безопасность

1. **Проверка активности**: share-токены можно деактивировать через `DELETE /api/kb/[id]/share-url`
2. **Истечение срока**: опциональное поле `expires_at` для временных ссылок
3. **Архивированные документы**: автоматически скрыты в публичном доступе
4. **Счётчик просмотров**: отслеживание популярности share-ссылок

---

## Дополнительные возможности

### Временные ссылки

```typescript
// При создании share-ссылки можно указать срок действия
await db.kbDocumentShare.create({
  data: {
    document_id: documentId,
    share_token: token,
    expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000), // 7 дней
  },
});

// В API проверять:
if (shareRecord.expires_at && shareRecord.expires_at < new Date()) {
  return NextResponse.json({ error: 'Ссылка истекла' }, { status: 410 });
}
```

### Аналитика

```typescript
// Отслеживание просмотров
const stats = await db.kbDocumentShare.findUnique({
  where: { share_token: token },
  select: {
    view_count: true,
    last_viewed_at: true,
    created_at: true,
  },
});

console.log(`Просмотров: ${stats.view_count}`);
console.log(`Последний просмотр: ${stats.last_viewed_at}`);
```

---

## Тестирование

1. Создайте документ с вложенными страницами
2. Нажмите "Поделиться" → скопируйте ссылку
3. Откройте в режиме инкогнито
4. Проверьте, что клик на вложенную страницу переходит на публичный URL

---

## Миграция существующих данных

Если у вас уже есть share-ссылки в старом формате, выполните:

```sql
-- Создать share-записи для существующих публичных документов
INSERT INTO kb_document_share (document_id, share_token, is_active, created_at)
SELECT id, md5(random()::text || id::text), true, NOW()
FROM kb_document
WHERE is_public = true; -- если у вас был флаг публичности
```

---

## Roadmap

- [ ] UI для копирования share-ссылки в один клик
- [ ] Настройка срока действия ссылки через интерфейс
- [ ] Список всех активных share-ссылок в настройках
- [ ] Защита паролем для приватных share-ссылок
- [ ] Webhook при создании/просмотре share-ссылки
