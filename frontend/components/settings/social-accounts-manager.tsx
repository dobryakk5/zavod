'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import { useRole } from '@/lib/hooks';
import { toast } from 'sonner';
import { Edit, ExternalLink, Plus, Trash2 } from 'lucide-react';
import type { Platform, SocialAccount } from '@/lib/types';

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
  socialAccount?: SocialAccount;
  isPlaceholder?: boolean;
};

const PLATFORM_LABELS: Record<Platform, string> = {
  telegram: 'Telegram',
  instagram: 'Instagram',
  youtube: 'YouTube',
  vkontakte: 'VKontakte',
  rss_zen: 'RSS Дзен',
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

  if (account.access_token && /^https?:\/\//i.test(account.access_token)) {
    return {
      label: formatLinkLabel(account.access_token),
      url: account.access_token,
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
  const [loading, setLoading] = useState(true);
  const [channelDialogMode, setChannelDialogMode] = useState<'add' | 'edit' | null>(null);
  const [channelDialogValue, setChannelDialogValue] = useState('');
  const [channelDialogLoading, setChannelDialogLoading] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const accountsData = await socialAccountsApi.list();
      setAccounts(accountsData);
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

  const isChannelDialogOpen = channelDialogMode !== null;
  const isChannelDialogEditMode = channelDialogMode === 'edit';

  const closeChannelDialog = () => {
    setChannelDialogMode(null);
    setChannelDialogValue('');
    setChannelDialogLoading(false);
  };

  const handleChannelDialogOpenChange = (open: boolean) => {
    if (!open && !channelDialogLoading) {
      closeChannelDialog();
    }
  };

  const handleAddTelegramAccount = () => {
    if (!canEdit) {
      return;
    }
    setChannelDialogMode('add');
    setChannelDialogValue('');
  };

  const handleEditRow = (row: TableRowData) => {
    if (!canEdit || row.isPlaceholder) {
      return;
    }

    if (row.socialAccount?.platform === 'telegram') {
      const extra = row.socialAccount.extra as Record<string, unknown> | undefined;
      const currentChannel = getExtraString(extra, 'channel') ?? '';
      setChannelDialogMode('edit');
      setChannelDialogValue(currentChannel);
      return;
    }

    toast.info(`Редактирование настроек для ${row.platformLabel} появится позже`);
  };

  const handleChannelDialogSubmit = async (event?: React.FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    if (!channelDialogMode || !canEdit || channelDialogLoading) {
      return;
    }

    const trimmedValue = channelDialogValue.trim();

    if (channelDialogMode === 'add') {
      if (!trimmedValue) {
        toast.error('Введите Telegram канал');
        return;
      }

      const channel = normalizeTelegramChannel(trimmedValue);
      if (!channel) {
        toast.error('Введите корректный Telegram канал');
        return;
      }

      setChannelDialogLoading(true);
      try {
        await socialAccountsApi.create({
          platform: 'telegram',
          name: channel,
          access_token: '',
          extra: { source: 'manual', channel },
        });
        toast.success('Аккаунт добавлен');
        await loadData();
        closeChannelDialog();
      } catch (error) {
        console.error(error);
        toast.error('Не удалось создать аккаунт');
      } finally {
        setChannelDialogLoading(false);
      }
      return;
    }

    setChannelDialogLoading(true);
    try {
      await clientApi.updateSettings({ telegram_client_channel: trimmedValue });
      toast.success(trimmedValue ? 'Telegram канал обновлен' : 'Канал очищен');
      await loadData();
      closeChannelDialog();
    } catch (error) {
      console.error(error);
      toast.error('Не удалось сохранить Telegram канал');
    } finally {
      setChannelDialogLoading(false);
    }
  };

  const handleDeleteSocialAccount = async (account?: SocialAccount) => {
    if (!canEdit || !account || !confirm('Удалить этот социальный аккаунт?')) {
      return;
    }

    const extra = account.extra as Record<string, unknown> | undefined;
    const source = typeof extra?.source === 'string' ? extra.source : undefined;
    const isClientSettingsTelegram = account.platform === 'telegram' && source === 'client_settings';

    if (isClientSettingsTelegram) {
      try {
        await clientApi.updateSettings({ telegram_client_channel: '' });
        toast.success('Telegram канал отключен');
        await loadData();
      } catch (error) {
        console.error(error);
        toast.error('Не удалось отключить Telegram канал');
      }
      return;
    }

    try {
      await socialAccountsApi.delete(account.id);
      toast.success('Аккаунт удален');
      await loadData();
    } catch (error) {
      console.error(error);
      toast.error('Не удалось удалить аккаунт');
    }
  };

  const rows: TableRowData[] = useMemo(() => {
    const filteredAccounts = accounts.filter((account) => account.platform !== 'vkontakte');
    const socialRows: TableRowData[] = filteredAccounts.map((account) => {
      const extra = account.extra as Record<string, unknown> | undefined;
      const displayName =
        account.platform === 'telegram'
          ? getExtraString(extra, 'channel') ?? account.name
          : account.name;
      const isRssZen = account.platform === 'rss_zen';

      return {
        id: `social-${account.id}`,
        platformKey: account.platform,
        platformLabel: PLATFORM_LABELS[account.platform] ?? account.platform,
        name: displayName,
        link: getSocialAccountLink(account),
        socialAccount: account,
        isPlaceholder: isRssZen,
      };
    });

    const platformsReferenced = new Set(filteredAccounts.map((account) => account.platform));

    if (!platformsReferenced.has('telegram')) {
      socialRows.push({
        id: 'telegram-placeholder',
        platformKey: 'telegram',
        platformLabel: PLATFORM_LABELS.telegram,
        name: 'Не подключено',
        link: null,
        isPlaceholder: true,
      });
    }

    return socialRows;
  }, [accounts]);

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold">Социальные аккаунты</h2>
          <p className="text-sm text-muted-foreground">
            Управляйте каналами для публикаций. Telegram добавляется вручную, RSS Дзен создаётся автоматически.
          </p>
        </div>
        {canEdit && (
          <Button size="sm" onClick={handleAddTelegramAccount}>
            <Plus className="h-4 w-4 mr-2" />
            Добавить аккаунт
          </Button>
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
                      {row.platformKey === 'telegram' && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={handleAddTelegramAccount}
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
                        onClick={() => handleDeleteSocialAccount(row.socialAccount)}
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

      <Dialog open={isChannelDialogOpen} onOpenChange={handleChannelDialogOpenChange}>
        <DialogContent className="sm:max-w-md bg-white text-gray-900 dark:bg-white dark:text-gray-900 dark:border-gray-200">
          <DialogHeader>
            <DialogTitle>
              {isChannelDialogEditMode ? 'Настроить Telegram канал' : 'Добавить Telegram канал'}
            </DialogTitle>
            <DialogDescription>
              {isChannelDialogEditMode
                ? 'Укажите основной Telegram канал, который будет использоваться для публикаций.'
                : 'Введите @username или ссылку на Telegram канал для публикаций.'}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleChannelDialogSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="telegram-channel-input">Telegram канал</Label>
              <Input
                id="telegram-channel-input"
                placeholder="@example_channel"
                autoFocus
                value={channelDialogValue}
                onChange={(event) => setChannelDialogValue(event.target.value)}
                disabled={channelDialogLoading}
              />
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={closeChannelDialog}
                disabled={channelDialogLoading}
              >
                Отмена
              </Button>
              <Button type="submit" disabled={channelDialogLoading}>
                {channelDialogLoading
                  ? 'Сохраняем...'
                  : isChannelDialogEditMode
                    ? 'Сохранить'
                    : 'Добавить'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </section>
  );
}
