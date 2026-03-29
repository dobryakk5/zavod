import type { Metadata } from 'next';
import { ReactNode } from 'react';
import { AppShell } from '@/components/layout/app-shell';
import { TrialLimitModal } from '@/components/layout/trial-limit-modal';
import { Toaster } from 'sonner';
import './globals.css';

export const metadata: Metadata = {
  title: 'Трекинг прогресса',
  description: 'Личный кабинет',
  icons: {
    icon: '/favicon.ico',
    shortcut: '/favicon.ico',
    apple: '/favicon.ico'
  }
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body className="min-h-screen bg-background text-foreground">
        <AppShell>{children}</AppShell>
        <TrialLimitModal />
        <Toaster position="top-right" richColors />
      </body>
    </html>
  );
}
