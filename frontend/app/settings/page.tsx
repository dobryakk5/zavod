'use client';

import { ClientSettingsForm } from '@/components/settings/client-settings-form';
import { SocialAccountsManager } from '@/components/settings/social-accounts-manager';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function SettingsPage() {
  return (
    <div className="container mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Настройки</h1>
        <p className="text-gray-500 mt-2">
          Управляйте настройками клиента и подключенными социальными аккаунтами
        </p>
      </div>

      <Tabs defaultValue="client" className="space-y-6">
        <TabsList>
          <TabsTrigger value="client">Настройки клиента</TabsTrigger>
          <TabsTrigger value="social">Социальные аккаунты</TabsTrigger>
        </TabsList>

        <TabsContent value="client" className="space-y-6">
          <div className="max-w-2xl">
            <ClientSettingsForm />
          </div>
        </TabsContent>

        <TabsContent value="social" className="space-y-6">
          <SocialAccountsManager />
        </TabsContent>
      </Tabs>
    </div>
  );
}
