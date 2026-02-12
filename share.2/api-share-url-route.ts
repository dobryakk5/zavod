import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db'; // ваша база данных

// GET /api/kb/[id]/share-url
// Получить или создать публичную share-ссылку для документа
export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const documentId = parseInt(params.id, 10);

    if (isNaN(documentId)) {
      return NextResponse.json(
        { error: 'Неверный ID документа' },
        { status: 400 }
      );
    }

    // Проверяем, существует ли уже share-токен для этого документа
    let shareRecord = await db.kbDocumentShare.findFirst({
      where: {
        document_id: documentId,
        is_active: true,
      },
    });

    // Если нет - создаём новый
    if (!shareRecord) {
      const shareToken = generateShareToken();
      shareRecord = await db.kbDocumentShare.create({
        data: {
          document_id: documentId,
          share_token: shareToken,
          is_active: true,
          created_at: new Date(),
        },
      });
    }

    const shareUrl = `${process.env.NEXT_PUBLIC_BASE_URL || 'https://fibonatty.ru'}/kb/share/${shareRecord.share_token}`;

    return NextResponse.json({
      shareUrl,
      shareToken: shareRecord.share_token,
    });
  } catch (error) {
    console.error('Error generating share URL:', error);
    return NextResponse.json(
      { error: 'Не удалось создать публичную ссылку' },
      { status: 500 }
    );
  }
}

// Генерация уникального токена для share-ссылки
function generateShareToken(): string {
  const crypto = require('crypto');
  return crypto.randomBytes(16).toString('hex');
}

// DELETE /api/kb/[id]/share-url
// Отключить публичный доступ к документу
export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const documentId = parseInt(params.id, 10);

    if (isNaN(documentId)) {
      return NextResponse.json(
        { error: 'Неверный ID документа' },
        { status: 400 }
      );
    }

    // Деактивируем все share-записи для этого документа
    await db.kbDocumentShare.updateMany({
      where: {
        document_id: documentId,
      },
      data: {
        is_active: false,
      },
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error removing share URL:', error);
    return NextResponse.json(
      { error: 'Не удалось отключить публичный доступ' },
      { status: 500 }
    );
  }
}
