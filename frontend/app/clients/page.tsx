'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Users, Calendar, DollarSign, FileText, FolderPlus } from 'lucide-react';
import { ClientsTab } from '../products/clients-tab';

export default function ClientsPage() {
  return (
    <div className="container mx-auto py-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Управление клиентами</h1>
        <p className="text-muted-foreground mt-2">
          Управление клиентами, событиями, платежами и заметками
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
        <Link href="/clients/new">
          <Card className="hover:shadow-md transition-shadow cursor-pointer">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Новый редактор</CardTitle>
              <FolderPlus className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">CRM</div>
              <p className="text-xs text-muted-foreground">Полнофункциональная система</p>
            </CardContent>
          </Card>
        </Link>

        <Link href="/analytics">
          <Card className="hover:shadow-md transition-shadow cursor-pointer">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Аналитика</CardTitle>
              <FileText className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">24</div>
              <p className="text-xs text-muted-foreground">активных клиентов</p>
            </CardContent>
          </Card>
        </Link>

        <Link href="/schedule">
          <Card className="hover:shadow-md transition-shadow cursor-pointer">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">События</CardTitle>
              <Calendar className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">12</div>
              <p className="text-xs text-muted-foreground">предстоящих встреч</p>
            </CardContent>
          </Card>
        </Link>

        <Link href="/payments">
          <Card className="hover:shadow-md transition-shadow cursor-pointer">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Платежи</CardTitle>
              <DollarSign className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">156 000 ₽</div>
              <p className="text-xs text-muted-foreground">в этом месяце</p>
            </CardContent>
          </Card>
        </Link>
      </div>

      <Tabs defaultValue="legacy" className="space-y-6">
        <TabsList>
          <TabsTrigger value="legacy">Текущий редактор</TabsTrigger>
          <TabsTrigger value="new">
            <Link href="/clients/new" className="w-full h-full flex items-center justify-center">
              Новый редактор
            </Link>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="legacy">
          <div className="bg-white dark:bg-gray-900 rounded-lg p-6">
            <ClientsTab />
          </div>
        </TabsContent>
      </Tabs>

      <div className="mt-8 text-center">
        <Link href="/clients/new">
          <Button size="lg">
            Перейти к новому редактору клиентов
          </Button>
        </Link>
        <p className="mt-4 text-sm text-muted-foreground">
          Новый редактор включает полную CRM-систему с управлением клиентами, событиями, платежами и заметками
        </p>
      </div>
    </div>
  );
}