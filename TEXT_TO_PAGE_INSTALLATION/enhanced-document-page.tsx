// app/kb/[id]/page.tsx
// Страница документа с поддержкой вложенных страниц

'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, MoreVertical, Archive, Copy, Trash2, ChevronRight } from 'lucide-react';
import EnhancedTiptapEditor from '@/components/Editor/EnhancedTiptapEditor';
import { kbDocumentsApi } from '@/lib/api/knowledgeBase';
import type { KbDocument } from '@/lib/types';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

export default function DocumentPage() {
  const params = useParams();
  const router = useRouter();
  const documentId = Number(params.id);

  const [document, setDocument] = useState<KbDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [icon, setIcon] = useState('');
  const [childDocuments, setChildDocuments] = useState<KbDocument[]>([]);

  // Загрузка документа
  useEffect(() => {
    loadDocument();
  }, [documentId]);

  const loadDocument = async () => {
    try {
      setLoading(true);
      const data = await kbDocumentsApi.get(documentId);
      setDocument(data);
      setTitle(data.title);
      setIcon(data.icon || '');
      
      // Загружаем дочерние документы
      if (data.child_documents && data.child_documents.length > 0) {
        setChildDocuments(data.child_documents);
      }
      
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load document');
    } finally {
      setLoading(false);
    }
  };

  // Обновление заголовка
  const handleTitleChange = async (newTitle: string) => {
    setTitle(newTitle);
    
    if (!document) return;
    
    try {
      await kbDocumentsApi.update(documentId, { title: newTitle });
    } catch (err) {
      console.error('Failed to update title:', err);
    }
  };

  // Обновление иконки
  const handleIconChange = () => {
    const newIcon = window.prompt('Введите эмодзи иконку:', icon);
    if (newIcon !== null) {
      setIcon(newIcon);
      kbDocumentsApi.update(documentId, { icon: newIcon }).catch(console.error);
    }
  };

  // Обработка изменения контента
  const handleContentUpdate = (content: any) => {
    console.log('Content updated');
  };

  // Обработка создания новой страницы из текста
  const handlePageCreated = async (newDocument: KbDocument) => {
    // Обновляем список дочерних документов
    setChildDocuments(prev => [...prev, newDocument]);
    
    // Показываем уведомление
    console.log('New page created:', newDocument.title);
  };

  // Дублирование документа
  const handleDuplicate = async () => {
    if (!document) return;
    
    try {
      const duplicated = await kbDocumentsApi.duplicate(documentId, {
        title: `${document.title} (копия)`,
        include_children: false,
      });
      router.push(`/kb/${duplicated.id}`);
    } catch (err) {
      console.error('Failed to duplicate document:', err);
      alert('Не удалось дублировать документ');
    }
  };

  // Архивирование
  const handleArchive = async () => {
    if (!document) return;
    
    try {
      await kbDocumentsApi.archive(documentId);
      router.push('/settings?tab=kb');
    } catch (err) {
      console.error('Failed to archive document:', err);
      alert('Не удалось архивировать документ');
    }
  };

  // Удаление
  const handleDelete = async () => {
    if (!document) return;
    
    if (!confirm('Вы уверены, что хотите удалить этот документ?')) {
      return;
    }
    
    try {
      await kbDocumentsApi.delete(documentId);
      router.push('/settings?tab=kb');
    } catch (err) {
      console.error('Failed to delete document:', err);
      alert('Не удалось удалить документ');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-gray-600">Загрузка документа...</div>
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="flex flex-col items-center justify-center h-screen">
        <div className="text-red-600 mb-4">{error || 'Документ не найден'}</div>
        <Button onClick={() => router.push('/settings?tab=kb')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Вернуться
        </Button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b border-gray-200 px-8 py-4 sticky top-0 bg-white z-10">
        <div className="flex items-center justify-between max-w-6xl mx-auto">
          <Button
            variant="ghost"
            onClick={() => router.push('/settings?tab=kb')}
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Назад
          </Button>
          
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">
              Обновлен: {new Date(document.updated_at).toLocaleDateString('ru-RU')}
            </span>
            <span className="text-sm text-gray-500">
              {document.last_edited_by?.username}
            </span>
            
            {/* Меню действий */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon">
                  <MoreVertical className="w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={handleDuplicate}>
                  <Copy className="w-4 h-4 mr-2" />
                  Дублировать
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleArchive}>
                  <Archive className="w-4 h-4 mr-2" />
                  Архивировать
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleDelete} className="text-red-600">
                  <Trash2 className="w-4 h-4 mr-2" />
                  Удалить
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      {/* Document Content */}
      <main className="max-w-4xl mx-auto py-8">
        {/* Icon */}
        <button
          onClick={handleIconChange}
          className="text-6xl mb-4 hover:bg-gray-100 rounded p-2 transition-colors"
          title="Изменить иконку"
        >
          {icon || '📄'}
        </button>

        {/* Cover Image */}
        {document.cover_image && (
          <div className="mb-8">
            <img
              src={document.cover_image}
              alt="Cover"
              className="w-full h-64 object-cover rounded-lg"
            />
          </div>
        )}

        {/* Title */}
        <input
          type="text"
          value={title}
          onChange={(e) => handleTitleChange(e.target.value)}
          className="w-full text-4xl font-bold mb-8 border-none outline-none focus:ring-0"
          placeholder="Без названия"
        />

        {/* Editor */}
        <EnhancedTiptapEditor
          document={document}
          onUpdate={handleContentUpdate}
          onPageCreated={handlePageCreated}
          editable={true}
        />

        {/* Child Documents Section */}
        {childDocuments.length > 0 && (
          <div className="mt-12 border-t pt-8">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <ChevronRight className="w-5 h-5" />
              Вложенные страницы ({childDocuments.length})
            </h3>
            <div className="space-y-2">
              {childDocuments.map((child) => (
                <button
                  key={child.id}
                  onClick={() => router.push(`/kb/${child.id}`)}
                  className="flex items-center gap-3 w-full p-3 rounded-lg hover:bg-gray-50 transition-colors text-left"
                >
                  <span className="text-2xl">{child.icon || '📄'}</span>
                  <div className="flex-1">
                    <div className="font-medium text-gray-900">{child.title}</div>
                    <div className="text-sm text-gray-500">
                      Обновлено: {new Date(child.updated_at).toLocaleDateString('ru-RU')}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
