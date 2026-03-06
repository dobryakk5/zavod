'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Copy, ExternalLink } from 'lucide-react';
import { clientApi } from '@/lib/api/client';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

const copyTextToClipboard = async (value: string): Promise<void> => {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText && window.isSecureContext) {
    await navigator.clipboard.writeText(value);
    return;
  }

  if (typeof document === 'undefined') {
    throw new Error('Clipboard is unavailable');
  }

  const textarea = document.createElement('textarea');
  textarea.value = value;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.top = '-9999px';
  document.body.appendChild(textarea);
  textarea.select();

  const copied = document.execCommand('copy');
  document.body.removeChild(textarea);

  if (!copied) {
    throw new Error('Copy failed');
  }
};

export function SiteTab() {
  const [clientId, setClientId] = useState<number | null>(null);

  useEffect(() => {
    const loadClientInfo = async () => {
      try {
        const info = await clientApi.info();
        setClientId(info.client.id);
      } catch {
        setClientId(null);
      }
    };
    void loadClientInfo();
  }, []);

  const publicPagePath = useMemo(() => (clientId ? `/c/${clientId}` : ''), [clientId]);
  const publicPageEditorPath = useMemo(() => (publicPagePath ? `${publicPagePath}/edit` : ''), [publicPagePath]);
  const quizEditorPath = useMemo(() => (publicPagePath ? `${publicPagePath}/quiz/edit` : ''), [publicPagePath]);
  const publicPageShareUrl = useMemo(() => {
    if (!publicPagePath) {
      return '';
    }
    if (typeof window === 'undefined') {
      return publicPagePath;
    }
    return `${window.location.origin}${publicPagePath}`;
  }, [publicPagePath]);

  const handleCopyPublicPageLink = useCallback(async () => {
    if (!publicPageShareUrl) {
      toast.error('Ссылка пока недоступна');
      return;
    }
    try {
      await copyTextToClipboard(publicPageShareUrl);
      toast.success('Ссылка скопирована');
    } catch {
      toast.error('Не удалось скопировать ссылку');
    }
  }, [publicPageShareUrl]);

  return (
    <div className="space-y-3 rounded-lg border bg-background p-5">
      <div>
        <h2 className="text-base font-semibold">Мои страницы</h2>
        <p className="text-sm text-muted-foreground">
          Управление публичной страницей клиента и квизом.
        </p>
      </div>
      <div className="space-y-2 text-sm">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-muted-foreground">1.</span>
          {publicPageEditorPath ? (
            <Link href={publicPageEditorPath} className="text-blue-600 hover:underline">
              Одностраничный сайт
            </Link>
          ) : (
            <span className="text-muted-foreground">Одностраничный сайт</span>
          )}
          {publicPagePath ? (
            <>
              <span className="text-muted-foreground">·</span>
              <a
                href={publicPagePath}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-blue-600 hover:underline"
              >
                {publicPagePath}
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => void handleCopyPublicPageLink()}
                aria-label="Скопировать ссылку на мою страницу"
              >
                <Copy className="h-3.5 w-3.5" />
              </Button>
            </>
          ) : (
            <span className="text-muted-foreground">—</span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-muted-foreground">2.</span>
          {quizEditorPath ? (
            <Link href={quizEditorPath} className="text-blue-600 hover:underline">
              Квиз (опросник)
            </Link>
          ) : (
            <span className="text-muted-foreground">Квиз (опросник)</span>
          )}
        </div>
      </div>
    </div>
  );
}
