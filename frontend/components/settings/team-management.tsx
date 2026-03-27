'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ApiError } from '@/lib/api';
import { clientApi } from '@/lib/api/client';
import { useRole } from '@/lib/hooks';
import type { PendingTeamInvite, TeamMember, TeamOverview } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';

const providerLabels: Record<string, string> = {
  telegram: 'Telegram',
  vk: 'VK',
};

function formatInviteDate(value: string) {
  try {
    return new Intl.DateTimeFormat('ru-RU', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function parseApiError(error: unknown, fallback: string) {
  if (!(error instanceof ApiError)) {
    return fallback;
  }
  if (!error.body) {
    return fallback;
  }
  try {
    const payload = JSON.parse(error.body) as { error?: string; detail?: string };
    return payload.detail || payload.error || fallback;
  } catch {
    return error.body || fallback;
  }
}

export function TeamManagement() {
  const { role } = useRole();
  const [team, setTeam] = useState<TeamOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [busyMemberId, setBusyMemberId] = useState<number | null>(null);
  const [busyInviteId, setBusyInviteId] = useState<number | null>(null);
  const [provider, setProvider] = useState<'telegram' | 'vk'>('telegram');
  const [accountHandle, setAccountHandle] = useState('');

  const loadTeam = useCallback(async () => {
    setLoading(true);
    try {
      const data = await clientApi.getTeam();
      setTeam(data);
    } catch (error) {
      toast.error(parseApiError(error, 'Не удалось загрузить команду'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (role === 'owner') {
      void loadTeam();
    } else {
      setLoading(false);
    }
  }, [loadTeam, role]);

  const slotsText = useMemo(() => {
    if (!team) {
      return '';
    }
    return `${team.used_slots} из ${team.limit} мест занято`;
  }, [team]);

  const handleInvite = async () => {
    const normalizedHandle = accountHandle.trim();
    if (!normalizedHandle) {
      toast.error('Введите аккаунт для приглашения');
      return;
    }

    setSubmitting(true);
    try {
      const response = await clientApi.createTeamInvitation({
        provider,
        account_handle: normalizedHandle,
      });
      toast.success(response.message);
      setAccountHandle('');
      await loadTeam();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        toast.error('Лимит команды достигнут');
      } else if (error instanceof ApiError && error.status === 429) {
        toast.error('Слишком много приглашений. Попробуйте позже.');
      } else {
        toast.error(parseApiError(error, 'Не удалось создать приглашение'));
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemoveMember = async (member: TeamMember) => {
    if (member.role === 'owner') {
      return;
    }
    if (!confirm(`Удалить доступ для ${member.display_name}?`)) {
      return;
    }

    setBusyMemberId(member.user_id);
    try {
      await clientApi.removeTeamMember(member.user_id);
      toast.success('Доступ участника отозван');
      await loadTeam();
    } catch (error) {
      toast.error(parseApiError(error, 'Не удалось удалить участника'));
    } finally {
      setBusyMemberId(null);
    }
  };

  const handleRevokeInvite = async (invite: PendingTeamInvite) => {
    if (!confirm(`Отозвать приглашение для ${invite.account_handle_raw}?`)) {
      return;
    }

    setBusyInviteId(invite.id);
    try {
      await clientApi.revokeTeamInvitation(invite.id);
      toast.success('Приглашение отозвано');
      await loadTeam();
    } catch (error) {
      toast.error(parseApiError(error, 'Не удалось отозвать приглашение'));
    } finally {
      setBusyInviteId(null);
    }
  };

  if (role !== 'owner') {
    return (
      <div className="rounded-xl border bg-background p-5 text-sm text-muted-foreground">
        Управление командой доступно только владельцу проекта.
      </div>
    );
  }

  if (loading) {
    return <div className="rounded-xl border bg-background p-5 text-sm text-muted-foreground">Загрузка команды...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border bg-background p-5">
        <div className="mb-4">
          <h3 className="text-base font-semibold">Пригласить в команду</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Введите Telegram или VK аккаунт. Доступ выдастся, когда пользователь войдет этим аккаунтом.
          </p>
          {team && <p className="mt-2 text-xs text-muted-foreground">{slotsText}</p>}
        </div>

        <div className="grid gap-4 md:grid-cols-[180px_minmax(0,1fr)_auto]">
          <div className="space-y-2">
            <Label htmlFor="team-provider">Платформа</Label>
            <Select value={provider} onValueChange={(value: 'telegram' | 'vk') => setProvider(value)}>
              <SelectTrigger id="team-provider">
                <SelectValue placeholder="Выберите платформу" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="telegram">Telegram</SelectItem>
                <SelectItem value="vk">VK</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="team-account-handle">Аккаунт</Label>
            <Input
              id="team-account-handle"
              value={accountHandle}
              onChange={(event) => setAccountHandle(event.target.value)}
              placeholder={provider === 'telegram' ? '@username' : 'screen_name'}
              disabled={submitting}
            />
          </div>

          <div className="flex items-end">
            <Button type="button" onClick={() => void handleInvite()} disabled={submitting}>
              {submitting ? 'Отправляем...' : 'Пригласить'}
            </Button>
          </div>
        </div>
      </div>

      <div className="rounded-xl border bg-background p-5">
        <div className="mb-4">
          <h3 className="text-base font-semibold">Участники</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Текущие участники проекта и их доступ.
          </p>
        </div>

        <div className="space-y-3">
          {team?.members.length ? (
            team.members.map((member) => (
              <div key={member.user_id} className="flex flex-col gap-3 rounded-lg border p-4 md:flex-row md:items-center md:justify-between">
                <div className="space-y-1">
                  <div className="font-medium">{member.display_name}</div>
                  <div className="text-sm text-muted-foreground">
                    @{member.username} · {member.role}
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                    {member.provider_accounts.map((account) => (
                      <span key={`${member.user_id}-${account.provider}-${account.handle || account.display_name}`} className="rounded-full bg-muted px-2 py-1">
                        {providerLabels[account.provider] || account.provider}
                        {account.handle ? ` · @${account.handle}` : ''}
                      </span>
                    ))}
                  </div>
                  {member.invited_by ? (
                    <div className="text-xs text-muted-foreground">Пригласил: {member.invited_by}</div>
                  ) : null}
                </div>

                {member.role !== 'owner' ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void handleRemoveMember(member)}
                    disabled={busyMemberId === member.user_id}
                  >
                    {busyMemberId === member.user_id ? 'Удаляем...' : 'Удалить доступ'}
                  </Button>
                ) : (
                  <div className="text-xs text-muted-foreground">Владелец проекта</div>
                )}
              </div>
            ))
          ) : (
            <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
              В проекте пока только владелец.
            </div>
          )}
        </div>
      </div>

      <div className="rounded-xl border bg-background p-5">
        <div className="mb-4">
          <h3 className="text-base font-semibold">Ожидающие приглашения</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Эти приглашения активируются, когда пользователь войдет нужным аккаунтом.
          </p>
        </div>

        <div className="space-y-3">
          {team?.pending_invites.length ? (
            team.pending_invites.map((invite) => (
              <div key={invite.id} className="flex flex-col gap-3 rounded-lg border p-4 md:flex-row md:items-center md:justify-between">
                <div className="space-y-1">
                  <div className="font-medium">{invite.account_handle_raw}</div>
                  <div className="text-sm text-muted-foreground">
                    {providerLabels[invite.provider] || invite.provider} · {invite.role}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Пригласил {invite.invited_by_name} · {formatInviteDate(invite.created_at)}
                  </div>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void handleRevokeInvite(invite)}
                  disabled={busyInviteId === invite.id}
                >
                  {busyInviteId === invite.id ? 'Отзываем...' : 'Отозвать'}
                </Button>
              </div>
            ))
          ) : (
            <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
              Ожидающих приглашений нет.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
