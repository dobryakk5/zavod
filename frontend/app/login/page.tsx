'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { TelegramAuth } from '@/components/auth/TelegramAuth';

export default function LoginPage() {
  const [open, setOpen] = useState(true);

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 px-4">
      <div className="w-full max-w-lg space-y-4 rounded-2xl border bg-background p-8 text-center shadow">
        <h1 className="text-2xl font-semibold">Войти в личный кабинет</h1>
        <p className="text-sm text-muted-foreground">
          Авторизация проходит через Telegram. Нажмите кнопку ниже и подтвердите вход у нашего бота.
        </p>
        <Button className="w-full" size="lg" onClick={() => setOpen(true)}>
          Войти через Telegram
        </Button>
        <p className="text-xs text-muted-foreground">
          Если у вас нет доступа, напишите менеджеру Контент-завода, чтобы получить приглашение.
        </p>
      </div>

      <TelegramAuth open={open} onClose={() => setOpen(false)} />
    </div>
  );
}
