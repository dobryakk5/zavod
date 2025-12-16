'use client';

import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { schedulesApi } from '@/lib/api/schedules';
import { socialAccountsApi } from '@/lib/api/socialAccounts';
import { postsApi } from '@/lib/api/posts';
import type { SocialAccount } from '@/lib/types';

interface SchedulePostDialogProps {
  postId: number;
  disabled?: boolean;
  onScheduled?: () => void | Promise<void>;
}

type ContentSelection = {
  text: boolean;
  image: boolean;
  video: boolean;
};

const createDefaultContentSelection = (): ContentSelection => ({
  text: true,
  image: true,
  video: true,
});

const CONTENT_OPTIONS: Array<{ key: keyof ContentSelection; label: string }> = [
  { key: 'text', label: 'Текст' },
  { key: 'image', label: 'Фото' },
  { key: 'video', label: 'Видео' },
];

const getDefaultDateTimeValue = () => {
  const date = new Date();
  date.setHours(date.getHours() + 1, 0, 0, 0);
  return date.toISOString().slice(0, 16);
};

export function SchedulePostDialog({ postId, disabled = false, onScheduled }: SchedulePostDialogProps) {
  const [open, setOpen] = useState(false);
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<string>('');
  const [scheduledAt, setScheduledAt] = useState<string>(getDefaultDateTimeValue());
  const [loadingAccounts, setLoadingAccounts] = useState(false);
  const [loadingPostSettings, setLoadingPostSettings] = useState(false);
  const [saving, setSaving] = useState(false);
  const [contentSelection, setContentSelection] = useState<ContentSelection>(() => createDefaultContentSelection());
  const [initialContentSelection, setInitialContentSelection] =
    useState<ContentSelection>(() => createDefaultContentSelection());

  const loadAccounts = useCallback(async () => {
    setLoadingAccounts(true);
    try {
      const data = await socialAccountsApi.list();
      setAccounts(data);
      setSelectedAccountId((prev) => {
        if (data.length === 0) {
          return '';
        }
        const hasSelected = data.some((account) => String(account.id) === prev);
        return hasSelected ? prev : String(data[0].id);
      });
    } catch (err) {
      toast.error('Не удалось загрузить аккаунты');
    } finally {
      setLoadingAccounts(false);
    }
  }, []);

  const loadPostContentSettings = useCallback(async () => {
    setLoadingPostSettings(true);
    try {
      const post = await postsApi.get(postId);
      const nextSelection: ContentSelection = {
        text: post.publish_text ?? true,
        image: post.publish_image ?? true,
        video: post.publish_video ?? true,
      };
      setContentSelection(nextSelection);
      setInitialContentSelection(nextSelection);
    } catch (err) {
      toast.error('Не удалось загрузить данные поста');
      const fallbackSelection = createDefaultContentSelection();
      setContentSelection(fallbackSelection);
      setInitialContentSelection(fallbackSelection);
    } finally {
      setLoadingPostSettings(false);
    }
  }, [postId]);

  useEffect(() => {
    if (open) {
      setScheduledAt(getDefaultDateTimeValue());
      loadAccounts();
      loadPostContentSettings();
    }
  }, [open, loadAccounts, loadPostContentSettings]);

  const handleSchedule = async () => {
    if (!selectedAccountId) {
      toast.error('Выберите социальный аккаунт');
      return;
    }
    if (!scheduledAt) {
      toast.error('Укажите дату и время публикации');
      return;
    }

    const hasSelectedContent = Object.values(contentSelection).some(Boolean);
    if (!hasSelectedContent) {
      toast.error('Выберите хотя бы один тип контента');
      return;
    }

    setSaving(true);
    try {
      const shouldUpdatePostSettings =
        contentSelection.text !== initialContentSelection.text ||
        contentSelection.image !== initialContentSelection.image ||
        contentSelection.video !== initialContentSelection.video;

      if (shouldUpdatePostSettings) {
        await postsApi.update(postId, {
          publish_text: contentSelection.text,
          publish_image: contentSelection.image,
          publish_video: contentSelection.video,
        });
        setInitialContentSelection({ ...contentSelection });
      }

      await schedulesApi.create({
        post: postId,
        social_account: Number(selectedAccountId),
        scheduled_at: new Date(scheduledAt).toISOString(),
      });
      toast.success('Публикация запланирована');
      setOpen(false);
      setScheduledAt(getDefaultDateTimeValue());
      if (onScheduled) {
        await onScheduled();
      }
    } catch (err) {
      toast.error('Не удалось запланировать пост');
    } finally {
      setSaving(false);
    }
  };

  const isActionDisabled =
    disabled ||
    loadingAccounts ||
    saving ||
    accounts.length === 0 ||
    !selectedAccountId ||
    !scheduledAt;

  const isSaveDisabled = isActionDisabled || loadingPostSettings;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button disabled={disabled} size="sm">
          Запланировать
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md bg-white text-gray-900 dark:bg-white dark:text-gray-900 dark:border-gray-200">
        <DialogHeader>
          <DialogTitle>Запланировать публикацию</DialogTitle>
          <DialogDescription>
            Выберите социальный аккаунт и время публикации. Пост будет отправлен автоматически.
          </DialogDescription>
        </DialogHeader>

        {loadingAccounts ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            Загрузка доступных аккаунтов...
          </div>
        ) : accounts.length === 0 ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            Нет подключенных аккаунтов для публикации.
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="schedule-account">Социальный аккаунт</Label>
              <Select
                value={selectedAccountId}
                onValueChange={setSelectedAccountId}
                disabled={isActionDisabled}
              >
                <SelectTrigger id="schedule-account">
                  <SelectValue placeholder="Выберите аккаунт" />
                </SelectTrigger>
                <SelectContent>
                  {accounts.map((account) => (
                    <SelectItem key={account.id} value={String(account.id)}>
                      {account.name} ({account.platform})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="schedule-datetime">Дата и время</Label>
              <Input
                id="schedule-datetime"
                type="datetime-local"
                value={scheduledAt}
                onChange={(event) => setScheduledAt(event.target.value)}
                disabled={isActionDisabled}
              />
              <p className="text-xs text-muted-foreground">
                Используется часовой пояс вашего браузера.
              </p>
            </div>
            <div className="space-y-2">
              <Label>Содержимое</Label>
              <div className="flex flex-wrap gap-4 text-sm">
                {CONTENT_OPTIONS.map((option) => (
                  <label
                    key={option.key}
                    className="inline-flex items-center gap-2 text-sm font-medium text-gray-900"
                  >
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-gray-300 text-gray-900 focus:ring-2 focus:ring-gray-900 disabled:cursor-not-allowed"
                      checked={contentSelection[option.key]}
                      onChange={(event) =>
                        setContentSelection((prev) => ({
                          ...prev,
                          [option.key]: event.target.checked,
                        }))
                      }
                      disabled={loadingPostSettings || saving}
                    />
                    {option.label}
                  </label>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">Отметьте части поста для публикации.</p>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setOpen(false)}>
                Отмена
              </Button>
              <Button onClick={handleSchedule} disabled={isSaveDisabled}>
                {saving ? 'Сохраняем...' : 'Сохранить'}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
