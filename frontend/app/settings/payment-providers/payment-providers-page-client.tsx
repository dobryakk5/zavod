'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowUpRight, CheckCircle2, CircleDashed, RefreshCcw } from 'lucide-react';
import { ApiError, apiFetch } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';

type PaymentProvidersStatus = {
  yookassa?: {
    connected?: boolean;
    connection_type?: 'oauth' | 'manual' | 'connected' | 'none' | string;
  };
  tbank?: {
    connected?: boolean;
    test_mode?: boolean;
    terminal_key_masked?: string;
    has_secret_key?: boolean;
  };
};

const yookassaConnectionTypeLabels: Record<string, string> = {
  oauth: 'OAuth подключение',
  manual: 'Подключено по ключам',
  connected: 'Подключено',
  none: 'Не подключено',
};

export default function PaymentProvidersPageClient() {
  const [status, setStatus] = useState<PaymentProvidersStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [statusError, setStatusError] = useState('');
  const [connectLoading, setConnectLoading] = useState(false);
  const [tbankTerminalKey, setTbankTerminalKey] = useState('');
  const [tbankSecretKey, setTbankSecretKey] = useState('');
  const [tbankSaveLoading, setTbankSaveLoading] = useState(false);

  const loadStatus = useCallback(async (showLoader = true) => {
    if (showLoader) {
      setStatusLoading(true);
    }
    setStatusError('');
    try {
      const data = await apiFetch<PaymentProvidersStatus>('/payments/providers/');
      setStatus(data);
    } catch (error) {
      console.error('Failed to load payment providers status', error);
      setStatusError('Не удалось загрузить статус провайдеров.');
    } finally {
      if (showLoader) {
        setStatusLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const handleConnectYookassa = async () => {
    setConnectLoading(true);
    try {
      const response = await apiFetch<{ redirect_url?: string }>('/payments/yookassa/connect/');
      if (response?.redirect_url) {
        window.location.href = response.redirect_url;
        return;
      }
      toast.error('Не удалось получить ссылку подключения YooKassa.');
    } catch (error) {
      console.error('Failed to start YooKassa OAuth', error);
      const message = error instanceof ApiError && error.body ? error.body : 'Не удалось начать подключение YooKassa.';
      toast.error(message);
    } finally {
      setConnectLoading(false);
    }
  };

  const handleSaveTBankCredentials = async () => {
    const terminalKey = tbankTerminalKey.trim();
    const secretKey = tbankSecretKey.trim();
    if (!terminalKey || !secretKey) {
      toast.error('Введите TerminalKey и SecretKey для T-Bank.');
      return;
    }

    setTbankSaveLoading(true);
    try {
      const response = await apiFetch<{ ok?: boolean; test_mode?: boolean }>('/payments/tbank/credentials/', {
        method: 'POST',
        body: {
          terminal_key: terminalKey,
          secret_key: secretKey,
        },
      });
      if (!response?.ok) {
        toast.error('Не удалось сохранить ключи T-Bank.');
        return;
      }
      toast.success(response.test_mode ? 'Сохранено в тестовом режиме T-Bank.' : 'Ключи T-Bank сохранены.');
      setTbankTerminalKey('');
      setTbankSecretKey('');
      await loadStatus(false);
    } catch (error) {
      console.error('Failed to save T-Bank credentials', error);
      toast.error('Не удалось сохранить ключи T-Bank.');
    } finally {
      setTbankSaveLoading(false);
    }
  };

  const yookassaConnected = Boolean(status?.yookassa?.connected);
  const tbankConnected = Boolean(status?.tbank?.connected);

  const yookassaStatusLabel = useMemo(() => {
    const connectionType = status?.yookassa?.connection_type || 'none';
    return yookassaConnectionTypeLabels[connectionType] || 'Неизвестный статус';
  }, [status?.yookassa?.connection_type]);

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold">Провайдеры оплаты</h1>
        <p className="text-sm text-muted-foreground">
          Подключите нужный сервис для приема платежей от клиентов.
        </p>
      </div>

      <div className="flex items-center gap-2">
        <Button type="button" variant="outline" size="sm" onClick={() => void loadStatus()} disabled={statusLoading}>
          {statusLoading ? 'Обновляем...' : 'Обновить статусы'}
          <RefreshCcw className="ml-2 h-4 w-4" />
        </Button>
        {statusError ? <span className="text-sm text-destructive">{statusError}</span> : null}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <CardTitle className="text-xl">YooKassa</CardTitle>
              <Badge variant={yookassaConnected ? 'default' : 'secondary'}>
                {yookassaConnected ? 'Подключено' : 'Не подключено'}
              </Badge>
            </div>
            <CardDescription>{statusLoading ? 'Проверяем подключение...' : yookassaStatusLabel}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              {yookassaConnected ? <CheckCircle2 className="h-4 w-4 text-green-600" /> : <CircleDashed className="h-4 w-4" />}
              <span>
                {yookassaConnected
                  ? 'YooKassa подключена для текущего клиента.'
                  : 'YooKassa ещё не подключена для текущего клиента.'}
              </span>
            </div>
            <Button type="button" onClick={() => void handleConnectYookassa()} disabled={connectLoading}>
              {connectLoading ? 'Переходим в YooKassa...' : 'Подключить YooKassa'}
              <ArrowUpRight className="ml-2 h-4 w-4" />
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <CardTitle className="text-xl">Tbank</CardTitle>
              <Badge variant={tbankConnected ? 'default' : 'secondary'}>
                {tbankConnected ? 'Подключено' : 'Не подключено'}
              </Badge>
            </div>
            <CardDescription>Укажите TerminalKey и SecretKey для приема платежей через Tbank.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-sm text-muted-foreground space-y-1">
              {status?.tbank?.terminal_key_masked ? (
                <div>Текущий TerminalKey: {status.tbank.terminal_key_masked}</div>
              ) : (
                <div>TerminalKey пока не сохранен.</div>
              )}
              <div>
                Режим: {status?.tbank?.test_mode ? 'Тестовый' : 'Боевой'}
              </div>
            </div>

            <div className="grid gap-3">
              <div className="space-y-2">
                <Label htmlFor="tbank-terminal-key">TerminalKey</Label>
                <Input
                  id="tbank-terminal-key"
                  value={tbankTerminalKey}
                  onChange={(event) => setTbankTerminalKey(event.target.value)}
                  placeholder="TerminalKey"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="tbank-secret-key">SecretKey</Label>
                <Input
                  id="tbank-secret-key"
                  value={tbankSecretKey}
                  onChange={(event) => setTbankSecretKey(event.target.value)}
                  placeholder="SecretKey"
                  type="password"
                />
              </div>
            </div>

            <Button type="button" variant="outline" onClick={() => void handleSaveTBankCredentials()} disabled={tbankSaveLoading}>
              {tbankSaveLoading ? 'Сохраняем...' : 'Сохранить ключи Tbank'}
            </Button>
            <div className="text-xs text-muted-foreground">
              Если используете `TinkoffBankTest`, платежи будут в тестовом режиме.
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
