import type { Metadata } from 'next';
import { ReactNode } from 'react';
import { AppShell } from '@/components/layout/app-shell';
import { Toaster } from 'sonner';
import './globals.css';

export const metadata: Metadata = {
  title: 'Контент-кабинет',
  description: 'Личный кабинет клиента контент-сервиса'
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body className="min-h-screen bg-background text-foreground">
        <AppShell>{children}</AppShell>
        <Toaster position="top-right" richColors />
      </body>
    </html>
  );
}
