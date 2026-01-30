'use client';

import { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Calendar, DollarSign, FileText, Users } from 'lucide-react';
import { crmContactsApi, crmEventsApi, crmNotesApi, crmPaymentsApi } from '@/lib/api/crm';
import { ClientsTab } from '../products/clients-tab';
import { CategoriesTab } from '../products/categories-tab';
import { CategoriesDisplay } from '../products/categories-display';
import NewClientsEditor from './new/new-clients-editor';
import ClientsSchedule from './clients-schedule';

type ClientsStats = {
  totalClients: number;
  activeClients: number;
  notesCount: number;
  upcomingEvents: number;
  paidThisMonth: number;
};

const emptyStats: ClientsStats = {
  totalClients: 0,
  activeClients: 0,
  notesCount: 0,
  upcomingEvents: 0,
  paidThisMonth: 0,
};

function formatNumber(value: number | null) {
  if (value === null) return '—';
  return value.toLocaleString('ru-RU');
}

function formatCurrency(value: number | null) {
  if (value === null) return '—';
  return `${value.toLocaleString('ru-RU')} ₽`;
}

export default function ClientsPage() {
  const [stats, setStats] = useState<ClientsStats>(emptyStats);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const loadStats = async () => {
      setStatsLoading(true);
      setStatsError(null);

      try {
        const [contacts, events, payments, notes] = await Promise.all([
          crmContactsApi.list(),
          crmEventsApi.list(),
          crmPaymentsApi.list(),
          crmNotesApi.list(),
        ]);

        if (!isActive) return;

        const now = new Date();
        const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
        const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 1);

        const upcomingEvents = events.filter((event) => {
          if (event.status !== 'scheduled') return false;
          const startDate = new Date(event.start_time);
          return !Number.isNaN(startDate.getTime()) && startDate >= now;
        }).length;

        const paidThisMonth = payments.reduce((sum, payment) => {
          if (payment.status !== 'paid') return sum;
          const paidAt = payment.paid_at ?? payment.created_at;
          const paidDate = paidAt ? new Date(paidAt) : null;
          if (!paidDate || Number.isNaN(paidDate.getTime())) return sum;
          if (paidDate < monthStart || paidDate >= monthEnd) return sum;
          return sum + Number(payment.amount || 0);
        }, 0);

        setStats({
          totalClients: contacts.length,
          activeClients: contacts.filter((contact) => contact.status === 'active').length,
          notesCount: notes.length,
          upcomingEvents,
          paidThisMonth,
        });
      } catch (err) {
        if (!isActive) return;
        console.error('Failed to load CRM stats', err);
        setStatsError('Не удалось загрузить статистику CRM.');
      } finally {
        if (isActive) {
          setStatsLoading(false);
        }
      }
    };

    void loadStats();

    return () => {
      isActive = false;
    };
  }, []);

  const displayStats = useMemo(() => {
    if (statsLoading || statsError) {
      return {
        totalClients: null,
        activeClients: null,
        notesCount: null,
        upcomingEvents: null,
        paidThisMonth: null,
      };
    }

    return {
      totalClients: stats.totalClients,
      activeClients: stats.activeClients,
      notesCount: stats.notesCount,
      upcomingEvents: stats.upcomingEvents,
      paidThisMonth: stats.paidThisMonth,
    };
  }, [stats, statsError, statsLoading]);

  return (
    <div className="container mx-auto py-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Управление клиентами</h1>
        <p className="text-muted-foreground mt-2">
          Управление клиентами, расписанием и платежами
        </p>
        {statsError && (
          <p className="text-sm text-red-500 mt-2">{statsError}</p>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Всего клиентов</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatNumber(displayStats.totalClients)}
            </div>
            <p className="text-xs text-muted-foreground">
              {displayStats.activeClients === null
                ? 'активных клиентов'
                : `${formatNumber(displayStats.activeClients)} активных клиентов`}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Заметки</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatNumber(displayStats.notesCount)}
            </div>
            <p className="text-xs text-muted-foreground">заметок</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">События</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatNumber(displayStats.upcomingEvents)}
            </div>
            <p className="text-xs text-muted-foreground">предстоящих встреч</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Платежи</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCurrency(displayStats.paidThisMonth)}
            </div>
            <p className="text-xs text-muted-foreground">в этом месяце</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="clients" className="space-y-6">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="clients">Клиенты</TabsTrigger>
          <TabsTrigger value="schedule">Расписание</TabsTrigger>
          <TabsTrigger value="categories">Теги</TabsTrigger>
          <TabsTrigger value="groups">Категории</TabsTrigger>
          <TabsTrigger value="payments">Платежи</TabsTrigger>
        </TabsList>

        <TabsContent value="clients" className="space-y-6">
          <div className="bg-white rounded-lg p-6">
            <ClientsTab />
          </div>
        </TabsContent>

        <TabsContent value="schedule" className="space-y-6">
          <div className="bg-white rounded-lg">
            <ClientsSchedule />
          </div>
        </TabsContent>

        <TabsContent value="categories" className="space-y-6">
          <div className="bg-white rounded-lg p-6">
            <CategoriesTab />
          </div>
        </TabsContent>

        <TabsContent value="groups" className="space-y-6">
          <div className="bg-white rounded-lg p-6">
            <CategoriesDisplay />
          </div>
        </TabsContent>

        <TabsContent value="payments" className="space-y-6">
          <div className="bg-white rounded-lg p-6">
            <NewClientsEditor activeTab="payments" />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
