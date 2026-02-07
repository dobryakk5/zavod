'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ClientSettingsForm } from '@/components/settings/client-settings-form';
import { ClientTimezoneSetting } from '@/components/settings/client-timezone-setting';
import { SocialAccountsManager } from '@/components/settings/social-accounts-manager';
import { VkIntegrationsPanel } from '@/components/settings/vk-integrations-panel';
import { PaymentTab } from '@/components/settings/payment-tab';
import { KnowledgeBaseTab } from '@/components/settings/knowledge-base-tab';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function SettingsPageClient() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const tabParam = searchParams.get('tab') ?? 'client';
  const availableTabs = useMemo(() => new Set(['client', 'social', 'vk', 'payment', 'kb']), []);
  const [activeTab, setActiveTab] = useState(() => (availableTabs.has(tabParam) ? tabParam : 'client'));

  useEffect(() => {
    const nextTab = searchParams.get('tab') ?? 'client';
    if (availableTabs.has(nextTab) && nextTab !== activeTab) {
      setActiveTab(nextTab);
    }
  }, [activeTab, availableTabs, searchParams]);

  const handleTabChange = (value: string) => {
    setActiveTab(value);
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', value);
    router.replace(`/settings?${params.toString()}`);
  };

  return (
    <div className="container mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Настройки</h1>
        <p className="text-gray-500 mt-2">
          Управляйте настройками проекта и социальными аккаунтами
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-6">
        <TabsList>
          <TabsTrigger value="client">Настройки клиента</TabsTrigger>
          <TabsTrigger value="social">Социальные аккаунты</TabsTrigger>
          <TabsTrigger value="vk">Группы VK</TabsTrigger>
          <TabsTrigger value="payment">Оплата</TabsTrigger>
          <TabsTrigger value="kb">База знаний</TabsTrigger>
        </TabsList>

        <TabsContent value="client" className="space-y-6">
          <div className="max-w-2xl">
            <ClientSettingsForm />
          </div>
        </TabsContent>

        <TabsContent value="social" className="space-y-6">
          <div className="max-w-2xl">
            <ClientTimezoneSetting />
          </div>
          <SocialAccountsManager />
        </TabsContent>

        <TabsContent value="vk" className="space-y-6">
          <VkIntegrationsPanel />
        </TabsContent>

        <TabsContent value="payment" className="space-y-6">
          <PaymentTab />
        </TabsContent>

        <TabsContent value="kb" className="space-y-6">
          <KnowledgeBaseTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
