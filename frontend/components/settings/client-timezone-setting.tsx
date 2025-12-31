'use client';

import { useEffect, useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { clientApi } from '@/lib/api/client';
import { useRole } from '@/lib/hooks';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const DEFAULT_TIMEZONE_OPTIONS = [
  'UTC',
  'Europe/Helsinki',
  'Europe/Moscow',
  'Europe/London',
  'America/New_York',
  'Asia/Tokyo',
] as const;

const normalizeTimezone = (value?: string | null) => (value ?? '').trim();

export function ClientTimezoneSetting() {
  const { canEdit } = useRole();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [timezone, setTimezone] = useState('');
  const [initialTimezone, setInitialTimezone] = useState('');

  const isDirty = useMemo(() => timezone !== initialTimezone, [timezone, initialTimezone]);
  const timezoneOptions = useMemo(() => {
    const candidate = normalizeTimezone(timezone);
    const base = [...DEFAULT_TIMEZONE_OPTIONS] as string[];
    if (candidate && !base.includes(candidate)) {
      return [candidate, ...base];
    }
    return base;
  }, [timezone]);

  const loadTimezone = async () => {
    setLoading(true);
    try {
      const data = await clientApi.getSettings();
      const currentTimezone = normalizeTimezone(data.timezone);
      setTimezone(currentTimezone);
      setInitialTimezone(currentTimezone);
    } catch (error) {
      console.error(error);
      toast.error('Не удалось загрузить часовой пояс');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTimezone();
  }, []);

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
        {loading ? (
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
              {timezoneOptions.map((value) => (
                <SelectItem key={value} value={value}>
                  {value}
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
          onClick={loadTimezone}
          disabled={loading || saving}
        >
          Обновить
        </Button>
        <Button
          type="button"
          onClick={handleSave}
          disabled={loading || !canEdit || saving || !isDirty}
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
