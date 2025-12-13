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
import type { SocialAccount } from '@/lib/types';

interface SchedulePostDialogProps {
  postId: number;
  disabled?: boolean;
  onScheduled?: () => void | Promise<void>;
}

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
  const [saving, setSaving] = useState(false);

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

  useEffect(() => {
    if (open) {
      setScheduledAt(getDefaultDateTimeValue());
      loadAccounts();
    }
  }, [open, loadAccounts]);

  const handleSchedule = async () => {
    if (!selectedAccountId) {
      toast.error('Выберите социальный аккаунт');
      return;
    }
    if (!scheduledAt) {
      toast.error('Укажите дату и время публикации');
      return;
    }

    setSaving(true);
    try {
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

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button disabled={disabled} size="sm">
          Запланировать
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
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
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setOpen(false)}>
                Отмена
              </Button>
              <Button onClick={handleSchedule} disabled={isActionDisabled}>
                {saving ? 'Сохраняем...' : 'Сохранить'}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
