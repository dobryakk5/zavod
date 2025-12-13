'use client';

import { useState, useEffect } from 'react';
import { socialAccountsApi } from '@/lib/api/socialAccounts';
import { clientApi } from '@/lib/api/client';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Plus, Trash2, Edit } from 'lucide-react';
import { toast } from 'sonner';
import { useRole } from '@/lib/hooks';
import type { SocialAccount } from '@/lib/types';
import { VkIntegrationsPanel } from './vk-integrations-panel';

export function SocialAccountsManager() {
  const { canEdit } = useRole();
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [telegramChannel, setTelegramChannel] = useState('');
  const [telegramLoading, setTelegramLoading] = useState(true);
  const [telegramSaving, setTelegramSaving] = useState(false);

  useEffect(() => {
    loadAccounts();
    loadTelegramChannel();
  }, []);

  const loadAccounts = async () => {
    setLoading(true);
    try {
      const data = await socialAccountsApi.list();
      setAccounts(data);
    } catch (error) {
      toast.error('Не удалось загрузить аккаунты');
    } finally {
      setLoading(false);
    }
  };

  const loadTelegramChannel = async () => {
    setTelegramLoading(true);
    try {
      const data = await clientApi.getSettings();
      setTelegramChannel(data.telegram_client_channel || '');
    } catch (error) {
      console.error(error);
      toast.error('Не удалось загрузить Telegram канал');
    } finally {
      setTelegramLoading(false);
    }
  };

  const handleSaveTelegramChannel = async () => {
    if (telegramSaving) {
      return;
    }
    setTelegramSaving(true);
    try {
      const trimmedChannel = telegramChannel.trim();
      const response = await clientApi.updateSettings({ telegram_client_channel: trimmedChannel });
      const savedValue = response.telegram_client_channel || '';
      setTelegramChannel(savedValue);
      toast.success(savedValue ? 'Telegram канал сохранен' : 'Канал очищен');
    } catch (error) {
      console.error(error);
      toast.error('Не удалось сохранить канал');
    } finally {
      setTelegramSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Вы уверены, что хотите удалить этот аккаунт?')) {
      return;
    }

    try {
      await socialAccountsApi.delete(id);
      toast.success('Аккаунт успешно удален');
      await loadAccounts();
    } catch (error) {
      toast.error('Ошибка при удалении аккаунта');
    }
  };

  const getPlatformBadgeColor = (platform: string) => {
    switch (platform) {
      case 'instagram':
        return 'bg-pink-500 text-white';
      case 'telegram':
        return 'bg-blue-500 text-white';
      case 'youtube':
        return 'bg-red-500 text-white';
      case 'vkontakte':
        return 'bg-sky-700 text-white';
      default:
        return 'bg-gray-500 text-white';
    }
  };

  return (
    <div className="space-y-10">
      <section className="space-y-4">
        <div className="space-y-1">
          <h2 className="text-2xl font-bold">Telegram канал для публикации</h2>
          <p className="text-sm text-gray-600 max-w-2xl">
            Этот канал используется при ручной публикации и в расписаниях. Укажите ссылку на канал, @username
            или t.me/идентификатор (как на странице аналитики Telegram).
          </p>
        </div>
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <Input
            type="text"
            value={telegramChannel}
            onChange={(event) => setTelegramChannel(event.target.value)}
            placeholder="https://t.me/example_channel или @example_channel"
            disabled={telegramLoading || !canEdit}
            className="md:flex-1"
          />
          <Button
            type="button"
            onClick={handleSaveTelegramChannel}
            disabled={!canEdit || telegramLoading || telegramSaving}
          >
            {telegramSaving ? 'Сохранение...' : 'Сохранить канал'}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Можно вставить ссылку, @username или t.me/handle — мы автоматически приведем её к нужному формату.
        </p>
      </section>

      <section className="space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="text-2xl font-bold">Социальные аккаунты</h2>
          {canEdit && (
            <Button
              size="sm"
              onClick={() =>
                toast.info('Скоро появится мастер подключения аккаунтов. Пока доступно подключение групп VK ниже на странице.')
              }
            >
              <Plus className="h-4 w-4 mr-2" />
              Добавить аккаунт
            </Button>
          )}
        </div>

        {loading ? (
          <div className="text-center py-8 text-gray-500">Загрузка аккаунтов...</div>
        ) : accounts.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            Нет подключенных аккаунтов
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Платформа</TableHead>
                <TableHead>Название</TableHead>
                <TableHead>Имя пользователя</TableHead>
                <TableHead>Статус</TableHead>
                <TableHead className="text-right">Действия</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {accounts.map((account) => (
                <TableRow key={account.id}>
                  <TableCell>
                    <Badge className={getPlatformBadgeColor(account.platform)}>
                      {account.platform}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-medium">{account.name}</TableCell>
                  <TableCell className="text-gray-600">
                    {account.username || '—'}
                  </TableCell>
                  <TableCell>
                    {account.is_active ? (
                      <Badge variant="outline" className="text-green-600 border-green-600">
                        Активен
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-gray-400 border-gray-400">
                        Неактивен
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {canEdit && (
                      <div className="flex gap-2 justify-end">
                        <Button variant="ghost" size="sm">
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(account.id)}
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <VkIntegrationsPanel />
    </div>
  );
}
