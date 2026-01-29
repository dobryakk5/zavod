'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Users, Calendar, DollarSign, FileText } from 'lucide-react';
import { ClientsTab } from '../products/clients-tab';
import { CategoriesTab } from '../products/categories-tab';
import { CategoriesDisplay } from '../products/categories-display';
import NewClientsEditor from './new/new-clients-editor';

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
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Всего клиентов</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">24</div>
            <p className="text-xs text-muted-foreground">активных клиентов</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Аналитика</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">18</div>
            <p className="text-xs text-muted-foreground">отчетов</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">События</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">12</div>
            <p className="text-xs text-muted-foreground">предстоящих встреч</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Платежи</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">156 000 ₽</div>
            <p className="text-xs text-muted-foreground">в этом месяце</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="clients" className="space-y-6">
        <TabsList className="grid w-full grid-cols-6">
          <TabsTrigger value="clients">Клиенты</TabsTrigger>
          <TabsTrigger value="events">События</TabsTrigger>
          <TabsTrigger value="categories">Теги</TabsTrigger>
          <TabsTrigger value="groups">Категории</TabsTrigger>
          <TabsTrigger value="payments">Платежи</TabsTrigger>
          <TabsTrigger value="notes">Заметки</TabsTrigger>
        </TabsList>

        <TabsContent value="clients" className="space-y-6">
          <div className="bg-white rounded-lg p-6">
            <ClientsTab />
          </div>
        </TabsContent>

        <TabsContent value="events" className="space-y-6">
          <div className="bg-white rounded-lg p-6">
            <NewClientsEditor activeTab="events" />
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

        <TabsContent value="notes" className="space-y-6">
          <div className="bg-white rounded-lg p-6">
            <NewClientsEditor activeTab="notes" />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
