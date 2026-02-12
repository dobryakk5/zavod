import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';

// GET /api/kb/share/[shareToken]
// Получить документ и все его вложенные страницы по публичной ссылке
export async function GET(
  request: NextRequest,
  { params }: { params: { shareToken: string } }
) {
  try {
    const { shareToken } = params;

    // Проверяем существование и активность share-токена
    const shareRecord = await db.kbDocumentShare.findFirst({
      where: {
        share_token: shareToken,
        is_active: true,
      },
    });

    if (!shareRecord) {
      return NextResponse.json(
        { error: 'Документ не найден или доступ запрещён' },
        { status: 404 }
      );
    }

    // Получаем основной документ
    const mainDocument = await db.kbDocument.findUnique({
      where: { id: shareRecord.document_id },
      select: {
        id: true,
        title: true,
        icon: true,
        content: true,
        created_at: true,
        updated_at: true,
        parent_document: true,
        is_archived: true,
      },
    });

    if (!mainDocument || mainDocument.is_archived) {
      return NextResponse.json(
        { error: 'Документ не найден' },
        { status: 404 }
      );
    }

    // Получаем все вложенные документы (рекурсивно)
    const childDocuments = await getChildDocumentsRecursive(shareRecord.document_id);

    // Возвращаем основной документ + все вложенные
    const allDocuments = [mainDocument, ...childDocuments];

    // Увеличиваем счётчик просмотров (опционально)
    await db.kbDocumentShare.update({
      where: { id: shareRecord.id },
      data: {
        view_count: {
          increment: 1,
        },
        last_viewed_at: new Date(),
      },
    });

    return NextResponse.json(allDocuments);
  } catch (error) {
    console.error('Error loading shared document:', error);
    return NextResponse.json(
      { error: 'Не удалось загрузить документ' },
      { status: 500 }
    );
  }
}

// Рекурсивная функция для получения всех вложенных документов
async function getChildDocumentsRecursive(parentId: number): Promise<any[]> {
  const children = await db.kbDocument.findMany({
    where: {
      parent_document: parentId,
      is_archived: false, // показываем только неархивированные
    },
    select: {
      id: true,
      title: true,
      icon: true,
      content: true,
      created_at: true,
      updated_at: true,
      parent_document: true,
      is_archived: true,
    },
  });

  const allChildren = [...children];

  // Рекурсивно получаем вложенные документы для каждого ребёнка
  for (const child of children) {
    const nestedChildren = await getChildDocumentsRecursive(child.id);
    allChildren.push(...nestedChildren);
  }

  return allChildren;
}
