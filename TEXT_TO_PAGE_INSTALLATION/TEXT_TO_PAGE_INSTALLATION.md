# Инструкция по установке функции "Создание страницы из текста"

## Что добавлено?

Новая функция позволяет выделить текст в редакторе и создать из него вложенную страницу (как в Craft). При этом:
1. Создается новый документ с выделенным текстом в качестве заголовка
2. Текст заменяется на интерактивную ссылку на новую страницу
3. Новая страница становится дочерней по отношению к текущей

## Установка

### 1. Установи дополнительные пакеги для Next.js

```bash
npm install lucide-react
npm install @tiptap/extension-bubble-menu
```

### 2. Файлы которые нужно добавить/обновить

**Новые файлы:**

1. `components/Editor/EnhancedTiptapEditor.tsx` - Обновленный редактор с Bubble Menu
2. `components/Editor/extensions/page-link.ts` - Кастомное расширение для ссылок на страницы
3. `components/Editor/extensions/PageLinkComponent.tsx` - React компонент для рендеринга ссылок
4. `app/kb/[id]/page.tsx` - Обновленная страница документа с вложенными страницами
5. `lib/api/knowledgeBase.ts` - Обновленный API клиент
6. `styles/tiptap-editor.css` - Стили для редактора

**Структура директорий:**

```
your-next-app/
├── app/
│   └── kb/
│       └── [id]/
│           └── page.tsx
├── components/
│   ├── Editor/
│   │   ├── EnhancedTiptapEditor.tsx
│   │   └── extensions/
│   │       ├── page-link.ts
│   │       └── PageLinkComponent.tsx
│   └── ui/
│       ├── button.tsx
│       └── dropdown-menu.tsx
├── lib/
│   └── api/
│       └── knowledgeBase.ts
└── styles/
    └── tiptap-editor.css
```

### 3. Импорт стилей

Добавь в `app/globals.css` или `app/layout.tsx`:

```css
@import '../styles/tiptap-editor.css';
```

### 4. Обновление типов

Создай или обнови `lib/types.ts`:

```typescript
export interface KbDocument {
  id: number;
  title: string;
  icon: string | null;
  cover_image: string | null;
  content: any;
  parent_document: number | null;
  created_by?: {
    id: number;
    username: string;
    email: string;
  };
  last_edited_by?: {
    id: number;
    username: string;
  };
  created_at: string;
  updated_at: string;
  is_archived: boolean;
  child_documents?: KbDocument[];
}

export interface KbDocumentList {
  id: number;
  title: string;
  icon: string | null;
  created_at: string;
  updated_at: string;
  is_archived: boolean;
}
```

## Использование

### Для пользователя:

1. Открой любой документ в редакторе
2. Выделите текст, который хочешь превратить в страницу
3. В появившемся Bubble Menu нажми кнопку "Создать страницу"
4. Текст заменится на интерактивную ссылку
5. Клик по ссылке откроет новую вложенную страницу

### Пример кода использования:

```tsx
import EnhancedTiptapEditor from '@/components/Editor/EnhancedTiptapEditor';

function MyDocumentPage() {
  const [document, setDocument] = useState<KbDocument | null>(null);

  const handlePageCreated = (newDoc: KbDocument) => {
    console.log('New page created:', newDoc.title);
    // Можно добавить уведомление или обновить UI
  };

  return (
    <EnhancedTiptapEditor
      document={document}
      onPageCreated={handlePageCreated}
      editable={true}
    />
  );
}
```

## Backend требования

Убедись что в Django API есть endpoint для создания документа с `parent_document`:

```python
# views.py
class DocumentViewSet(viewsets.ModelViewSet):
    def perform_create(self, serializer):
        document = serializer.save(
            created_by=self.request.user,
            last_edited_by=self.request.user
        )
        # parent_document будет установлен автоматически из validated_data
```

## Особенности реализации

### 1. Кастомное расширение PageLink

Создает новый тип узла в Tiptap, который:
- Хранит ID страницы, заголовок и иконку
- Рендерится как интерактивная ссылка
- Кликабелен и ведет на страницу

### 2. Bubble Menu

Появляется при выделении текста и содержит:
- Стандартные кнопки форматирования (Bold, Italic, Underline)
- Кнопку "Создать страницу"

### 3. Вложенные страницы

Страницы связаны через `parent_document`:
```
Document 1
  ├── Document 2 (child)
  ├── Document 3 (child)
  └── Document 4 (child)
      └── Document 5 (nested child)
```

## Тестирование

1. Создай новый документ
2. Напиши текст: "Это тестовая страница"
3. Выдели "тестовая страница"
4. Нажми "Создать страницу" в Bubble Menu
5. Убедись что:
   - Текст заменился на ссылку
   - Ссылка кликабельна
   - Новая страница создана
   - В списке дочерних страниц появилась новая

## Возможные проблемы и решения

### Ошибка: "Cannot find module lucide-react"
```bash
npm install lucide-react
```

### Стили не применяются
Проверь что `tiptap-editor.css` импортирован в `globals.css`

### Ссылка не кликабельна
Убедись что:
1. `PageLinkComponent` правильно обрабатывает клик
2. `useRouter` импортирован из `next/navigation`

### Новая страница не создается
Проверь:
1. API endpoint `/api/documents/` доступен
2. Токен авторизации передается
3. В консоли нет ошибок

## Дополнительные возможности

### 1. Drag & Drop для перемещения страниц

Можно добавить:
```typescript
const handleDragStart = (doc: KbDocument) => {
  // Логика drag & drop
};
```

### 2. Breadcrumbs навигация

Показывать путь к текущей странице:
```
Home > Parent Document > Current Document
```

### 3. Поиск по вложенным страницам

Рекурсивный поиск по всем дочерним документам.

## Поддержка

Если возникли проблемы, проверь:
1. Версии пакетов в `package.json`
2. Логи Django в консоли
3. Network tab в DevTools браузера
