import type { Metadata } from 'next';
import SharedDocumentClient from './shared-document-client';
import type { KbDocumentShare } from '@/lib/types';

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4000/api').replace(/\/+$/, '');

async function fetchShare(token: string): Promise<KbDocumentShare | null> {
  const response = await fetch(`${API_BASE_URL}/kb/shares/by_token/${encodeURIComponent(token)}/`, {
    cache: 'no-store',
  });

  if (!response.ok) {
    return null;
  }

  return (await response.json()) as KbDocumentShare;
}

type SharedDocumentPageProps = {
  params: Promise<{ token: string }>;
};

export async function generateMetadata({ params }: SharedDocumentPageProps): Promise<Metadata> {
  const { token } = await params;
  const share = await fetchShare(token);
  const title = share?.document_detail?.title?.trim();

  if (!title) {
    return { title: 'Документ недоступен' };
  }

  return {
    title,
    description: 'Публичный документ в базе знаний',
  };
}

export default async function SharedDocumentPage({ params }: SharedDocumentPageProps) {
  const { token } = await params;
  const share = await fetchShare(token);

  if (!share?.document_detail) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">Ссылка недоступна или истекла</p>
      </div>
    );
  }

  return <SharedDocumentClient document={share.document_detail} />;
}
