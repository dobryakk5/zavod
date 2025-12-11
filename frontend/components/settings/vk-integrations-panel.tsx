'use client';

import { useEffect, useState } from 'react';
import { VkConnectButton } from '@/components/vk/vk-connect-button';
import { VkPublishDialog } from '@/components/vk/vk-publish-dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useRole } from '@/lib/hooks';
import { vkApi } from '@/lib/api/vk';
import { toast } from 'sonner';
import { ExternalLink, RefreshCw, Trash2 } from 'lucide-react';
import type { VkIntegration } from '@/lib/types';

const formatDateTime = (value?: string | null) => {
  if (!value) {
    return '—';
  }
  try {
    return new Date(value).toLocaleString('ru-RU');
  } catch {
    return value;
  }
};

const formatStatus = (status?: string): { label: string; className: string } => {
  if (!status) {
    return {
      label: 'Активен',
      className: 'text-green-600 border-green-600',
    };
  }

  switch (status) {
    case 'pending':
      return { label: 'Ожидание', className: 'text-blue-600 border-blue-600' };
    case 'error':
      return { label: 'Ошибка доступа', className: 'text-red-600 border-red-600' };
    case 'disabled':
      return { label: 'Отключен', className: 'text-gray-500 border-gray-400' };
    default:
      return { label: status, className: 'text-green-600 border-green-600' };
  }
};

export function VkIntegrationsPanel() {
  const { canEdit } = useRole();
  const [integrations, setIntegrations] = useState<VkIntegration[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadIntegrations();
  }, []);

  const loadIntegrations = async () => {
    setLoading(true);
    try {
      const data = await vkApi.listIntegrations();
      setIntegrations(data);
    } catch (error) {
      console.error(error);
      toast.error('Не удалось загрузить группы VK');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Отключить эту группу VK?')) {
      return;
    }
    try {
      await vkApi.deleteIntegration(id);
      toast.success('Группа отключена');
      await loadIntegrations();
    } catch (error) {
      console.error(error);
      toast.error('Не удалось отключить интеграцию');
    }
  };

  const handleConnectCompleted = () => {
    toast.info('Проверяем подключение VK...');
    loadIntegrations();
  };

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h3 className="text-xl font-semibold">Группы VKontakte</h3>
          <p className="text-sm text-muted-foreground max-w-2xl">
            Подключите сообщества VK для публикации постов напрямую через Zavod.
            Добавление происходит через официальный OAuth VK — токены хранятся только на
            сервере.
          </p>
        </div>
        {canEdit && (
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={loadIntegrations}
              disabled={loading}
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Обновить список
            </Button>
            <VkConnectButton onConnected={handleConnectCompleted}>
              Подключить группу VK
            </VkConnectButton>
          </div>
        )}
      </div>

      {loading && integrations.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">Загрузка групп VK...</div>
      ) : integrations.length === 0 ? (
        <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
          Пока нет подключенных групп VK. Нажмите «Подключить группу VK», чтобы пройти
          авторизацию и выбрать сообщество.
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Группа</TableHead>
              <TableHead>Добавил</TableHead>
              <TableHead>Статус</TableHead>
              <TableHead>Последняя публикация</TableHead>
              <TableHead className="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {integrations.map((integration) => {
              const statusMeta = formatStatus(integration.status);
              const groupLink = integration.screen_name
                ? `https://vk.com/${integration.screen_name.replace(/^@/, '')}`
                : null;
              return (
                <TableRow key={integration.id}>
                  <TableCell>
                    <div className="font-medium">
                      {integration.group_name || `Группа #${integration.group_id}`}
                    </div>
                    <div className="text-xs text-muted-foreground flex items-center gap-2 flex-wrap">
                      <span>ID: {integration.group_id}</span>
                      {groupLink && (
                        <a
                          href={groupLink}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-blue-600 hover:underline"
                        >
                          {integration.screen_name.replace(/^@/, '')}
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>{integration.owner_name || '—'}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className={statusMeta.className}>
                      {statusMeta.label}
                    </Badge>
                  </TableCell>
                  <TableCell>{formatDateTime(integration.last_published_at)}</TableCell>
                  <TableCell className="text-right">
                    {canEdit ? (
                      <div className="flex justify-end gap-2">
                        <VkPublishDialog integration={integration} onPublished={loadIntegrations} />
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleDelete(integration.id)}
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">Нет доступа</span>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
