'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { socialAccountsApi } from '@/lib/api/socialAccounts';
import { clientApi } from '@/lib/api/client';
import { vkApi } from '@/lib/api/vk';
import { VkConnectButton } from '@/components/vk/vk-connect-button';
import { useRole } from '@/lib/hooks';
import { toast } from 'sonner';
import { Edit, ExternalLink, Plus, Trash2 } from 'lucide-react';
import type { Platform, SocialAccount, VkIntegration } from '@/lib/types';

type RowLink = {
  label: string;
  url: string;
};

type TableRowData = {
  id: string;
  platformKey: Platform;
  platformLabel: string;
  name: string;
  link: RowLink | null;
  source: 'social' | 'vk';
  socialAccount?: SocialAccount;
  vkIntegration?: VkIntegration;
  isPlaceholder?: boolean;
};

const PLATFORM_LABELS: Record<Platform, string> = {
  telegram: 'Telegram',
  instagram: 'Instagram',
  youtube: 'YouTube',
  vkontakte: 'VKontakte',
};

const formatLinkLabel = (value: string) => value.replace(/^https?:\/\//i, '').replace(/\/$/, '');

const getExtraString = (
  extra: Record<string, unknown> | undefined,
  key: string,
): string | null => {
  if (!extra) {
    return null;
  }
  const value = extra[key];
  if (typeof value !== 'string') {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
};

const buildTelegramLink = (rawValue: string): RowLink => {
  if (/^https?:\/\//i.test(rawValue)) {
    return {
      label: formatLinkLabel(rawValue),
      url: rawValue,
    };
  }
  const handle = rawValue.replace(/^@/, '');
  return {
    label: rawValue.startsWith('@') ? rawValue : `@${handle}`,
    url: `https://t.me/${handle}`,
  };
};

const getSocialAccountLink = (account: SocialAccount): RowLink | null => {
  const extra = account.extra as Record<string, unknown> | undefined;

  const channel = getExtraString(extra, 'channel');
  if (channel) {
    return buildTelegramLink(channel);
  }

  const url = getExtraString(extra, 'url') ?? getExtraString(extra, 'link');
  if (url) {
    return {
      label: formatLinkLabel(url),
      url,
    };
  }

  if (account.platform === 'instagram' && account.username) {
    const handle = account.username.replace(/^@/, '');
    return {
      label: `instagram.com/${handle}`,
      url: `https://instagram.com/${handle}`,
    };
  }

  return null;
};

const getVkIntegrationLink = (integration: VkIntegration): RowLink | null => {
  const slug = integration.screen_name
    ? integration.screen_name.replace(/^@/, '')
    : integration.group_id
    ? `club${integration.group_id}`
    : null;

  if (!slug) {
    return null;
  }

  return {
    label: `vk.com/${slug}`,
    url: `https://vk.com/${slug}`,
  };
};

const normalizeTelegramChannel = (rawValue: string): string => {
  let candidate = rawValue.trim();
  candidate = candidate.replace(/^https?:\/\//i, '');
  candidate = candidate.replace(/^t\.me\//i, '').replace(/^telegram\.me\//i, '');
  candidate = candidate.replace(/^@/, '').replace(/\/$/, '');
  if (!candidate) {
    return '';
  }
  return candidate.startsWith('@') ? candidate : `@${candidate}`;
};

export function SocialAccountsManager() {
  const { canEdit } = useRole();
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [vkIntegrations, setVkIntegrations] = useState<VkIntegration[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [accountsData, vkData] = await Promise.all([
        socialAccountsApi.list(),
        vkApi.listIntegrations(),
      ]);
      setAccounts(accountsData);
      setVkIntegrations(vkData);
    } catch (error) {
      console.error(error);
      toast.error('Не удалось загрузить социальные аккаунты');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAddAccount = async (platform?: Platform) => {
    if (!canEdit) {
      return;
    }

    let targetPlatform = platform;
    if (!targetPlatform) {
      const choice = prompt('Укажите платформу (telegram, instagram, youtube)');
      if (!choice) {
        return;
      }
      const normalizedChoice = choice.trim().toLowerCase() as Platform;
      if (!PLATFORM_LABELS[normalizedChoice]) {
        toast.error('Неизвестная платформа');
        return;
      }
      targetPlatform = normalizedChoice;
    }

    if (targetPlatform === 'vkontakte') {
      toast.info('Используйте кнопку VK для подключения группы.');
      return;
    }

    const defaultName =
      targetPlatform === 'telegram' ? '@example_channel' : `${PLATFORM_LABELS[targetPlatform]} аккаунт`;
    const nameOrHandle = prompt('Введите название или ссылку на канал', defaultName);
    if (!nameOrHandle) {
      return;
    }
    const trimmedValue = nameOrHandle.trim();
    if (!trimmedValue) {
      toast.error('Пустое значение');
      return;
    }

    let preparedName = trimmedValue;
    const extra: Record<string, unknown> = { source: 'manual' };

    if (targetPlatform === 'telegram') {
      const channel = normalizeTelegramChannel(trimmedValue);
      if (!channel) {
        toast.error('Введите корректный Telegram канал');
        return;
      }
      extra.channel = channel;
      preparedName = channel;
    } else {
      extra.url = trimmedValue;
    }

    try {
      await socialAccountsApi.create({
        platform: targetPlatform,
        name: preparedName,
        access_token: '',
        extra,
      });
      toast.success('Аккаунт добавлен');
      await loadData();
    } catch (error) {
      console.error(error);
      toast.error('Не удалось создать аккаунт');
    }
  };

  const handleEditRow = async (row: TableRowData) => {
    if (!canEdit || row.isPlaceholder) {
      return;
    }

    if (row.source === 'social' && row.socialAccount?.platform === 'telegram') {
      const extra = row.socialAccount.extra as Record<string, unknown> | undefined;
      const currentChannel = getExtraString(extra, 'channel') ?? '';
      const newChannel = prompt('Укажите Telegram канал для публикаций', currentChannel) ?? undefined;
      if (newChannel === undefined) {
        return;
      }
      try {
        const payload = newChannel.trim();
        await clientApi.updateSettings({ telegram_client_channel: payload });
        toast.success(payload ? 'Telegram канал обновлен' : 'Канал очищен');
        await loadData();
      } catch (error) {
        console.error(error);
        toast.error('Не удалось сохранить Telegram канал');
      }
      return;
    }

    toast.info(`Редактирование настроек для ${row.platformLabel} появится позже`);
  };

  const handleDeleteSocialAccount = async (accountId?: number) => {
    if (!canEdit || !accountId || !confirm('Удалить этот социальный аккаунт?')) {
      return;
    }

    try {
      await socialAccountsApi.delete(accountId);
      toast.success('Аккаунт удален');
      await loadData();
    } catch (error) {
      console.error(error);
      toast.error('Не удалось удалить аккаунт');
    }
  };

  const handleDeleteVkIntegration = async (integration?: VkIntegration) => {
    if (!canEdit || !integration) {
      return;
    }
    if (!confirm('Отключить эту группу VK?')) {
      return;
    }
    try {
      await vkApi.deleteIntegration(integration.id);
      toast.success('Группа VK отключена');
      await loadData();
    } catch (error) {
      console.error(error);
      toast.error('Не удалось отключить группу VK');
    }
  };

  const rows: TableRowData[] = useMemo(() => {
    const socialRows: TableRowData[] = accounts.map((account) => {
      const extra = account.extra as Record<string, unknown> | undefined;
      const displayName =
        account.platform === 'telegram'
          ? getExtraString(extra, 'channel') ?? account.name
          : account.name;

      return {
        id: `social-${account.id}`,
        platformKey: account.platform,
        platformLabel: PLATFORM_LABELS[account.platform] ?? account.platform,
        name: displayName,
        link: getSocialAccountLink(account),
        source: 'social',
        socialAccount: account,
      };
    });

    const platformsReferenced = new Set(socialRows.map((row) => row.platformKey));

    if (!platformsReferenced.has('telegram')) {
      socialRows.push({
        id: 'telegram-placeholder',
        platformKey: 'telegram',
        platformLabel: PLATFORM_LABELS.telegram,
        name: 'Не подключено',
        link: null,
        source: 'social',
        isPlaceholder: true,
      });
    }

    if (vkIntegrations.length === 0) {
      return [
        ...socialRows,
        {
          id: 'vk-placeholder',
          platformKey: 'vkontakte',
          platformLabel: PLATFORM_LABELS.vkontakte,
          name: 'Не подключено',
          link: null,
          source: 'vk',
          isPlaceholder: true,
        },
      ];
    }

    const vkRows: TableRowData[] = vkIntegrations.map((integration) => ({
      id: `vk-${integration.id}`,
      platformKey: 'vkontakte',
      platformLabel: PLATFORM_LABELS.vkontakte,
      name: integration.group_name || `Группа #${integration.group_id}`,
      link: getVkIntegrationLink(integration),
      source: 'vk',
      vkIntegration: integration,
    }));

    return [...socialRows, ...vkRows];
  }, [accounts, vkIntegrations]);

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold">Социальные аккаунты</h2>
          <p className="text-sm text-muted-foreground">
            Управляйте каналами для публикаций. Сейчас поддерживаются Telegram и VKontakte.
          </p>
        </div>
        {canEdit && (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => loadData()} disabled={loading}>
              Обновить список
            </Button>
            <Button size="sm" onClick={() => handleAddAccount()}>
              <Plus className="h-4 w-4 mr-2" />
              Добавить аккаунт
            </Button>
          </div>
        )}
      </div>

      {loading ? (
        <div className="rounded-md border border-dashed py-8 text-center text-muted-foreground">
          Загружаем социальные аккаунты...
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-md border border-dashed py-8 text-center text-muted-foreground">
          Пока нет подключенных соцсетей.
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Платформа</TableHead>
              <TableHead>Название</TableHead>
              <TableHead>Ссылка</TableHead>
              <TableHead className="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell className="font-medium">{row.platformLabel}</TableCell>
                <TableCell>{row.name || '—'}</TableCell>
                <TableCell>
                  {row.link ? (
                    <a
                      href={row.link.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      {row.link.label}
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {canEdit ? (
                    <div className="flex justify-end gap-2">
                      {row.platformKey === 'vkontakte' ? (
                        <VkConnectButton
                          onConnected={loadData}
                          variant="ghost"
                          size="icon"
                          className="border border-transparent hover:border-muted"
                        >
                          <Plus className="h-4 w-4" />
                        </VkConnectButton>
                      ) : (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => handleAddAccount(row.platformKey)}
                        >
                          <Plus className="h-4 w-4" />
                        </Button>
                      )}
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => handleEditRow(row)}
                        disabled={row.isPlaceholder}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          if (row.source === 'vk') {
                            handleDeleteVkIntegration(row.vkIntegration);
                          } else {
                            handleDeleteSocialAccount(row.socialAccount?.id);
                          }
                        }}
                        disabled={row.isPlaceholder}
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                  ) : (
                    <span className="text-xs text-muted-foreground">Нет доступа</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
