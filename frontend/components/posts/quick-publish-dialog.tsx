'use client';

import { useState, useEffect } from 'react';
import { postsApi } from '@/lib/api/posts';
import { socialAccountsApi } from '@/lib/api/socialAccounts';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import type { SocialAccount } from '@/lib/types';

interface QuickPublishDialogProps {
  postId: number;
  disabled?: boolean;
}

export function QuickPublishDialog({ postId, disabled = false }: QuickPublishDialogProps) {
  const [open, setOpen] = useState(false);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [publishing, setPublishing] = useState(false);

  useEffect(() => {
    if (open) {
      loadAccounts();
    }
  }, [open]);

  const loadAccounts = async () => {
    setLoading(true);
    try {
      const data = await socialAccountsApi.list();
      setAccounts(data);
    } catch (err) {
      toast.error('Не удалось загрузить аккаунты');
    } finally {
      setLoading(false);
    }
  };

  const handlePublish = async (accountId: number) => {
    setPublishing(true);
    try {
      await postsApi.quickPublish(postId, { social_account_id: accountId });
      toast.success('Публикация запущена');
      setOpen(false);
    } catch (err) {
      toast.error('Ошибка при публикации');
    } finally {
      setPublishing(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button disabled={disabled} variant="default">
          Быстрая публикация
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Выберите социальную сеть</DialogTitle>
          <DialogDescription>
            Пост будет опубликован немедленно в выбранной социальной сети
          </DialogDescription>
        </DialogHeader>

        {loading && <div className="py-4 text-center">Загрузка...</div>}

        {!loading && accounts.length === 0 && (
          <div className="py-4 text-center text-gray-500">
            Нет подключенных аккаунтов
          </div>
        )}

        {!loading && accounts.length > 0 && (
          <div className="grid gap-2 py-4">
            {accounts.map((account) => (
              <Button
                key={account.id}
                variant="outline"
                className="w-full justify-start"
                onClick={() => handlePublish(account.id)}
                disabled={publishing}
              >
                <div className="flex items-center gap-3 w-full">
                  <Badge variant="secondary">{account.platform}</Badge>
                  <span className="flex-1 text-left">{account.name}</span>
                  {account.is_active && (
                    <span className="text-xs text-green-600">Активен</span>
                  )}
                </div>
              </Button>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
