'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { ArrowUpRight, CheckCircle, Clock3, RefreshCcw, XCircle } from 'lucide-react';
import { ApiError, apiFetch } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { toast } from 'sonner';

type PaymentResponse = {
  id?: string;
  confirmation_url?: string;
};

type TelegramAuthResponse = {
  user?: {
    telegramId?: string;
    firstName?: string;
    lastName?: string;
    username?: string;
    isDev?: boolean;
  };
};

type PaymentStatus = {
  id?: string;
  status?: string;
  paid?: boolean;
  amount?: {
    value?: string;
    currency?: string;
  };
  description?: string;
  created_at?: string;
};

type SubscriptionInfo = {
  plan_name?: string;
  plan_code?: string;
  expires_at?: string | null;
  is_active?: boolean;
};

type PaymentPlan = {
  code: string;
  name: string;
  amount: string;
  currency: string;
  period?: string;
  period_label?: string;
  description?: string;
};

const statusLabels: Record<string, string> = {
  pending: 'Ожидает оплаты',
  waiting_for_capture: 'Ожидает подтверждения',
  succeeded: 'Оплачен',
  canceled: 'Отменен',
};

const periodLabels: Record<string, string> = {
  week: 'Неделя',
  month: 'Месяц',
  year: 'Год',
};

const parsePlanLines = (description?: string) => {
  if (!description) {
    return [];
  }
  return description
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
};

export function PaymentTab() {
  const searchParams = useSearchParams();
  const [planId, setPlanId] = useState<string | null>(null);
  const [plans, setPlans] = useState<PaymentPlan[]>([]);
  const [plansLoading, setPlansLoading] = useState(true);
  const [plansError, setPlansError] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [amount, setAmount] = useState('');
  const [promoCode, setPromoCode] = useState('');
  const [promoLoading, setPromoLoading] = useState(false);
  const [promoError, setPromoError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [telegramUser, setTelegramUser] = useState<TelegramAuthResponse['user'] | null>(null);
  const [paymentId, setPaymentId] = useState<string | null>(null);
  const [paymentStatus, setPaymentStatus] = useState<PaymentStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [statusError, setStatusError] = useState('');
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(null);
  const [subscriptionLoading, setSubscriptionLoading] = useState(true);
  const isDev = Boolean(telegramUser?.isDev || telegramUser?.username === 'dev_user');

  const loadSubscription = useCallback(async (setLoading = true) => {
    if (setLoading) {
      setSubscriptionLoading(true);
    }
    try {
      const data = await apiFetch<SubscriptionInfo>('/payments/subscription/');
      setSubscription(data);
    } catch (subscriptionError) {
      console.error('Unable to load subscription', subscriptionError);
      setSubscription({ plan_name: 'Ознакомительный', expires_at: null, is_active: false });
    } finally {
      if (setLoading) {
        setSubscriptionLoading(false);
      }
    }
  }, []);

  const selectedPlan = useMemo(() => {
    if (!plans.length) {
      return null;
    }
    if (planId) {
      return plans.find((plan) => plan.code === planId) ?? plans[0];
    }
    return plans[0];
  }, [planId, plans]);

  const planDescriptionLines = useMemo(
    () => parsePlanLines(selectedPlan?.description),
    [selectedPlan?.description]
  );

  const periodLabel = selectedPlan?.period_label || (selectedPlan?.period ? periodLabels[selectedPlan.period] : '');

  const formattedAmount = useMemo(() => {
    const baseAmount = amount || selectedPlan?.amount || '';
    const numeric = Number(String(baseAmount).replace(',', '.'));
    if (Number.isNaN(numeric)) {
      return '';
    }
    return new Intl.NumberFormat('ru-RU').format(numeric);
  }, [amount, selectedPlan]);

  useEffect(() => {
    const loadUser = async () => {
      try {
        const data = await apiFetch<TelegramAuthResponse>('/auth/telegram');
        if (data?.user) {
          setTelegramUser(data.user);
          const fullName = [data.user.firstName, data.user.lastName].filter(Boolean).join(' ').trim();
          if (fullName) {
            setName((current) => current || fullName);
          }
        }
      } catch (authError) {
        console.warn('Unable to load Telegram user', authError);
      }
    };

    void loadUser();
  }, []);

  useEffect(() => {
    void loadSubscription();
  }, [loadSubscription]);

  useEffect(() => {
    const loadPlans = async () => {
      setPlansLoading(true);
      setPlansError('');
      try {
        const data = await apiFetch<{ plans?: PaymentPlan[] }>('/payments/plans/');
        const planList = Array.isArray(data?.plans) ? data.plans : [];
        setPlans(planList);
        if (planList.length) {
          setPlanId((current) => (current && planList.some((plan) => plan.code === current) ? current : planList[0].code));
          setAmount((current) => current || planList[0].amount);
        }
      } catch (plansLoadError) {
        console.error('Unable to load plans', plansLoadError);
        setPlansError('Не удалось загрузить тарифы.');
      } finally {
        setPlansLoading(false);
      }
    };

    void loadPlans();
  }, []);

  useEffect(() => {
    if (!selectedPlan) {
      return;
    }
    if (!isDev) {
      setAmount(selectedPlan.amount);
    } else if (!amount) {
      setAmount(selectedPlan.amount);
    }
  }, [amount, isDev, selectedPlan]);

  useEffect(() => {
    const queryPaymentId =
      searchParams.get('payment_id') ||
      searchParams.get('paymentId') ||
      searchParams.get('orderId');
    let storedId: string | null = null;
    try {
      storedId = sessionStorage.getItem('yookassa_payment_id') || localStorage.getItem('yookassa_payment_id');
    } catch (storageError) {
      console.warn('Unable to read payment id', storageError);
    }
    const resolvedId = queryPaymentId || storedId;
    if (resolvedId) {
      setPaymentId(resolvedId);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!paymentId) {
      return;
    }
    void refreshStatus(paymentId);
  }, [paymentId]);

  const onPlanSelect = (nextPlanId: string) => {
    setPlanId(nextPlanId);
    const nextPlan = plans.find((plan) => plan.code === nextPlanId);
    if (nextPlan) {
      setAmount(nextPlan.amount);
    }
  };

  const refreshStatus = async (id: string) => {
    setStatusLoading(true);
    setStatusError('');
    try {
      const data = await apiFetch<PaymentStatus>(`/payments/status/${id}/`);
      setPaymentStatus(data);
    } catch (statusError) {
      console.error('Unable to load payment status', statusError);
      setStatusError('Не удалось получить статус платежа.');
    } finally {
      setStatusLoading(false);
    }
  };

  const handleApplyPromo = async () => {
    const code = promoCode.trim();
    if (!code) {
      setPromoError('Введите промокод.');
      return;
    }

    setPromoLoading(true);
    setPromoError('');
    try {
      const response = await apiFetch<{
        success: boolean;
        message?: string;
        plan_name?: string;
        expires_at?: string;
      }>('/payments/promo/', {
        method: 'POST',
        body: { code },
      });
      toast.success(response.message || 'Промокод применен.');
      setPromoCode('');
      await loadSubscription(false);
    } catch (applyError) {
      let message = 'Промокод не принят.';
      if (applyError instanceof ApiError) {
        try {
          const parsed = JSON.parse(applyError.body ?? '');
          if (parsed?.detail) {
            message = parsed.detail;
          }
        } catch {
          if (applyError.body) {
            message = applyError.body;
          }
        }
      }
      setPromoError(message);
      toast.error(message);
    } finally {
      setPromoLoading(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setError('Укажите email для получения подтверждения оплаты.');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      setError('Укажите корректный email.');
      return;
    }

    if (!selectedPlan && !isDev) {
      setError('Тарифы не настроены. Обратитесь к администратору.');
      return;
    }

    const normalizedAmount = amount.replace(',', '.').trim();
    const numericAmount = isDev ? Number(normalizedAmount) : Number(selectedPlan?.amount ?? 0);
    if (isDev) {
      if (!normalizedAmount || Number.isNaN(numericAmount) || numericAmount <= 0) {
        setError('Введите корректную сумму оплаты.');
        return;
      }
    } else if (!numericAmount || Number.isNaN(numericAmount)) {
      setError('Не удалось определить сумму тарифа.');
      return;
    }

    setIsLoading(true);
    try {
      const returnUrl = `${window.location.origin}/settings?tab=payment`;
      const metadata: Record<string, string> = {};
      if (name) {
        metadata.name = name;
      }
      metadata.email = trimmedEmail;
      if (selectedPlan) {
        metadata.plan = selectedPlan.code;
      }

      const response = await apiFetch<PaymentResponse>('/payments/create/', {
        method: 'POST',
        body: {
          amount: numericAmount.toFixed(2),
          currency: selectedPlan?.currency || 'RUB',
          description: selectedPlan ? `Оплата тарифа ${selectedPlan.name}` : 'Оплата тарифа',
          return_url: returnUrl,
          plan_id: selectedPlan?.code,
          metadata,
        },
      });

      if (response?.confirmation_url) {
        if (response.id) {
          try {
            sessionStorage.setItem('yookassa_payment_id', response.id);
            localStorage.setItem('yookassa_payment_id', response.id);
            setPaymentId(response.id);
          } catch (storageError) {
            console.warn('Unable to store payment id', storageError);
          }
        }
        window.location.href = response.confirmation_url;
        return;
      }

      setError('Не удалось получить ссылку оплаты. Попробуйте еще раз.');
    } catch (submitError) {
      console.error('Failed to create payment', submitError);
      setError('Платеж не создан. Проверьте данные и повторите попытку.');
    } finally {
      setIsLoading(false);
    }
  };

  const statusLabel = paymentStatus?.status ? statusLabels[paymentStatus.status] ?? paymentStatus.status : '';
  const isSuccess = paymentStatus?.paid && paymentStatus?.status === 'succeeded';
  const isPending =
    !isSuccess && (paymentStatus?.status === 'pending' || paymentStatus?.status === 'waiting_for_capture');

  useEffect(() => {
    if (!isSuccess) {
      return;
    }
    void loadSubscription(false);
  }, [isSuccess, loadSubscription]);

  const subscriptionName = subscription?.plan_name || 'Ознакомительный';
  const subscriptionUntil = subscription?.expires_at
    ? new Date(subscription.expires_at).toLocaleDateString('ru-RU')
    : '';

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-2xl font-semibold">
          {subscriptionLoading ? 'Ваш тариф: ...' : `Ваш тариф: ${subscriptionName}`}
          {!subscriptionLoading && subscriptionUntil ? ` до ${subscriptionUntil}` : ''}
        </h2>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader>
            <CardTitle>Параметры оплаты</CardTitle>
            <CardDescription>Выберите тариф и укажите данные для счета.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid gap-3">
              {plansLoading ? (
                <div className="text-sm text-muted-foreground">Загружаем тарифы...</div>
              ) : plans.length ? (
                plans.map((plan) => {
                  const descriptionLine = parsePlanLines(plan.description)[0];
                  return (
                    <button
                      key={plan.code}
                      type="button"
                      onClick={() => onPlanSelect(plan.code)}
                      className={`flex flex-col gap-2 rounded-xl border px-4 py-3 text-left transition ${
                        plan.code === planId
                          ? 'border-primary bg-primary/5 shadow-sm'
                          : 'border-border bg-background hover:bg-muted/30'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="text-sm font-semibold">{plan.name}</div>
                        <div className="text-sm font-semibold">
                          {new Intl.NumberFormat('ru-RU').format(Number(plan.amount))} {plan.currency}
                        </div>
                      </div>
                  {descriptionLine ? (
                    <div className="text-xs text-muted-foreground">{descriptionLine}</div>
                  ) : null}
                  {plan.period ? (
                    <div className="text-xs text-muted-foreground">
                      Период: {plan.period_label || periodLabels[plan.period] || plan.period}
                    </div>
                  ) : null}
                </button>
              );
            })
          ) : (
                <div className="text-sm text-muted-foreground">
                  {plansError || 'Тарифы не настроены.'}
                </div>
              )}
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="pay-name">Имя</Label>
                  <Input
                    id="pay-name"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder="Как к вам обращаться"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="pay-email">Email</Label>
                  <Input
                    id="pay-email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="name@email.com"
                    type="email"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <Label htmlFor="pay-amount">Сумма к оплате, ₽</Label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <button
                        type="button"
                        className="text-xs text-muted-foreground underline decoration-dotted underline-offset-2 transition hover:text-foreground"
                      >
                        Ввести промокод
                      </button>
                    </PopoverTrigger>
                    <PopoverContent className="w-64 space-y-2 p-3">
                      <div className="text-xs font-medium text-foreground">Промокод</div>
                      <Input
                        value={promoCode}
                        onChange={(event) => {
                          setPromoCode(event.target.value);
                          if (promoError) {
                            setPromoError('');
                          }
                        }}
                        placeholder="Например: 1free"
                        className="h-8 text-xs"
                        onKeyDown={(event) => {
                          if (event.key === 'Enter') {
                            event.preventDefault();
                            void handleApplyPromo();
                          }
                        }}
                      />
                      {promoError ? <div className="text-xs text-destructive">{promoError}</div> : null}
                      <Button
                        type="button"
                        size="sm"
                        onClick={handleApplyPromo}
                        disabled={promoLoading || !promoCode.trim()}
                        className="w-full"
                      >
                        {promoLoading ? 'Применяем...' : 'Применить'}
                      </Button>
                      <div className="text-xs text-muted-foreground">
                        Промокод <span className="font-medium text-foreground">1free</span> дает 1 месяц тарифа
                        starter.
                      </div>
                    </PopoverContent>
                  </Popover>
                </div>
                <Input
                  id="pay-amount"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                  inputMode="decimal"
                  placeholder="9900"
                  disabled={!isDev}
                />
                {!isDev ? (
                  <div className="text-xs text-muted-foreground">
                    Сумма фиксирована для выбранного тарифа.
                  </div>
                ) : null}
              </div>

              {error ? <div className="text-sm text-destructive">{error}</div> : null}

              <Button
                type="submit"
                disabled={isLoading || plansLoading || (!selectedPlan && !isDev)}
                className="w-full"
              >
                {isLoading ? 'Создаем платеж...' : 'Перейти к оплате'}
                <ArrowUpRight className="ml-2 h-4 w-4" />
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-semibold">{selectedPlan?.name || 'Тариф не выбран'}</div>
                  {planDescriptionLines.length ? (
                    <div className="text-xs text-muted-foreground">{planDescriptionLines[0]}</div>
                  ) : null}
                  {periodLabel ? (
                    <div className="text-xs text-muted-foreground">Период: {periodLabel}</div>
                  ) : null}
                </div>
                <Badge variant="secondary">
                  {formattedAmount || '—'} {selectedPlan?.currency || 'RUB'}
                </Badge>
              </div>

              {planDescriptionLines.length > 1 ? (
                <div className="rounded-lg border bg-muted/20 p-3 text-sm text-muted-foreground">
                  <div className="font-medium text-foreground">Описание тарифа</div>
                  <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                    {planDescriptionLines.slice(1).map((line) => (
                      <li key={line}>• {line}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {telegramUser?.username ? (
                <div className="text-xs text-muted-foreground">
                  Telegram: <span className="font-medium text-foreground">@{telegramUser.username}</span>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Статус платежа</CardTitle>
              <CardDescription>Проверяем последний платеж по этому аккаунту.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {paymentId ? (
                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2">
                    {isSuccess ? (
                      <CheckCircle className="h-5 w-5 text-green-600" />
                    ) : isPending ? (
                      <Clock3 className="h-5 w-5 text-amber-600" />
                    ) : (
                      <XCircle className="h-5 w-5 text-red-500" />
                    )}
                    <span className="font-medium">{statusLabel || 'Статус неизвестен'}</span>
                  </div>
                  {paymentStatus?.amount?.value ? (
                    <div className="text-muted-foreground">
                      Сумма: {paymentStatus.amount.value} {paymentStatus.amount.currency ?? 'RUB'}
                    </div>
                  ) : null}
                  {paymentStatus?.description ? (
                    <div className="text-muted-foreground">Описание: {paymentStatus.description}</div>
                  ) : null}
                  {statusError ? <div className="text-sm text-destructive">{statusError}</div> : null}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={statusLoading}
                    onClick={() => {
                      if (paymentId) {
                        void refreshStatus(paymentId);
                      }
                    }}
                  >
                    {statusLoading ? 'Проверяем...' : 'Обновить статус'}
                    <RefreshCcw className="ml-2 h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">
                  Пока нет платежей. Создайте новый платеж, чтобы увидеть статус.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
