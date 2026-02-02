'use client';

import { useEffect, useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { clientApi } from '@/lib/api/client';
import { useRole } from '@/lib/hooks';
import { formatTenantOffsetLabel } from '@/lib/timezone';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const DEFAULT_TIMEZONE_VALUE = 'Europe/Moscow';
type TimezoneOption = {
  value: string;
  label: string;
};

const normalizeTimezone = (value?: string | null) => (value ?? '').trim();

const isValidTimeZone = (value: string) => {
  if (!value) return false;
  try {
    new Intl.DateTimeFormat('en-US', { timeZone: value });
    return true;
  } catch {
    return false;
  }
};

const resolveTimezoneValue = (value?: string | null) => {
  const normalized = normalizeTimezone(value);
  if (!normalized) {
    return '';
  }
  const [firstToken] = normalized.split(/\s+/);
  if (!firstToken) {
    return normalized;
  }
  const upper = firstToken.toUpperCase();
  if (upper === 'UTC' || upper.startsWith('UTC') || upper.startsWith('GMT')) {
    return 'UTC';
  }
  return firstToken;
};

const buildFallbackOption = (value: string): TimezoneOption => {
  if (isValidTimeZone(value)) {
    return { value, label: `${value} ${formatTenantOffsetLabel(value)}` };
  }
  return { value, label: value };
};

export function ClientTimezoneSetting() {
  const { canEdit } = useRole();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [timezoneOptionsState, setTimezoneOptionsState] = useState<TimezoneOption[]>([]);
  const [timezone, setTimezone] = useState(DEFAULT_TIMEZONE_VALUE);
  const [initialTimezone, setInitialTimezone] = useState(DEFAULT_TIMEZONE_VALUE);

  const isDirty = useMemo(() => timezone !== initialTimezone, [timezone, initialTimezone]);
  const timezoneOptions = useMemo(() => {
    const candidate = resolveTimezoneValue(timezone);
    const base = timezoneOptionsState;
    if (candidate && !base.some((item) => item.value === candidate)) {
      return [buildFallbackOption(candidate), ...base];
    }
    return base;
  }, [timezone, timezoneOptionsState]);

  const loadTimezoneOptions = async () => {
    setOptionsLoading(true);
    try {
      const response = await fetch('/api/timezones', { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`Failed to load timezones: ${response.status}`);
      }
      const data = (await response.json()) as { timezones?: TimezoneOption[] };
      setTimezoneOptionsState(Array.isArray(data.timezones) ? data.timezones : []);
    } catch (error) {
      console.error(error);
      toast.error('Не удалось загрузить список часовых поясов');
      setTimezoneOptionsState([]);
    } finally {
      setOptionsLoading(false);
    }
  };

  const loadTimezone = async () => {
    setLoading(true);
    try {
      const data = await clientApi.getSettings();
      const currentTimezone = resolveTimezoneValue(data.timezone);
      const nextTimezone = currentTimezone || DEFAULT_TIMEZONE_VALUE;
      setTimezone(nextTimezone);
      setInitialTimezone(nextTimezone);
    } catch (error) {
      console.error(error);
      toast.error('Не удалось загрузить часовой пояс');
      setTimezone(DEFAULT_TIMEZONE_VALUE);
      setInitialTimezone(DEFAULT_TIMEZONE_VALUE);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTimezoneOptions();
    loadTimezone();
  }, []);

  const handleRefresh = async () => {
    await Promise.all([loadTimezoneOptions(), loadTimezone()]);
  };

  const handleSave = async () => {
    if (!canEdit || saving || !isDirty) {
      return;
    }
    setSaving(true);
    try {
      await clientApi.updateSettings({ timezone });
      toast.success('Часовой пояс обновлён');
      setInitialTimezone(timezone);
    } catch (error) {
      console.error(error);
      toast.error('Ошибка при сохранении часового пояса');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Часовой пояс</CardTitle>
        <CardDescription>
          Используется для планирования публикаций и расписаний.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <Label htmlFor="client-timezone-select">Часовой пояс клиента</Label>
        {loading || optionsLoading ? (
          <div className="text-sm text-muted-foreground">Загрузка...</div>
        ) : (
          <Select
            value={timezone || undefined}
            onValueChange={(value) => setTimezone(value)}
            disabled={!canEdit || saving}
          >
            <SelectTrigger id="client-timezone-select" className="max-w-sm">
              <SelectValue placeholder="Выберите часовой пояс" />
            </SelectTrigger>
            <SelectContent>
              {timezoneOptions.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        {!canEdit && (
          <p className="text-xs text-muted-foreground">
            Редактирование доступно владельцу и редактору.
          </p>
        )}
      </CardContent>
      <CardFooter className="justify-end gap-2">
        <Button
          type="button"
          variant="outline"
          onClick={handleRefresh}
          disabled={loading || optionsLoading || saving}
        >
          Обновить
        </Button>
        <Button
          type="button"
          onClick={handleSave}
          disabled={loading || optionsLoading || !canEdit || saving || !isDirty}
        >
          {saving ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Сохранение...
            </>
          ) : (
            'Сохранить'
          )}
        </Button>
      </CardFooter>
    </Card>
  );
}
