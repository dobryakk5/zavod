'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ClientSettingsForm } from '@/components/settings/client-settings-form';
import { ClientTimezoneSetting } from '@/components/settings/client-timezone-setting';
import { ConnectedAccounts } from '@/components/auth/ConnectedAccounts';
import { SocialAccountsManager } from '@/components/settings/social-accounts-manager';
import { ChannelSelector } from '@/components/settings/channel-selector';
import { VkIntegrationsPanel } from '@/components/settings/vk-integrations-panel';
import { PaymentTab } from '@/components/settings/payment-tab';
import { KnowledgeBaseTab } from '@/components/settings/knowledge-base-tab';
import { SiteTab } from '@/components/settings/site-tab';
import { TeamManagement } from '@/components/settings/team-management';
import { RagChatWidget } from '@/components/settings/rag-chat-widget';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useRole } from '@/lib/hooks';

export default function SettingsPageClient() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { role } = useRole();
  const isOwner = role === 'owner';
  const tabParam = searchParams.get('tab') ?? 'client';
  const availableTabs = useMemo(() => {
    const tabs = ['client', 'social', 'site', 'payment', 'kb'];
    if (isOwner) {
      tabs.push('team');
    }
    return new Set(tabs);
  }, [isOwner]);
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
          {isOwner ? <TabsTrigger value="team">Команда</TabsTrigger> : null}
          <TabsTrigger value="social">Социальные аккаунты</TabsTrigger>
          <TabsTrigger value="site">Сайт</TabsTrigger>
          <TabsTrigger value="payment">Оплата</TabsTrigger>
          <TabsTrigger value="kb">База знаний</TabsTrigger>
        </TabsList>

        <TabsContent value="client" className="space-y-6">
          <div className="max-w-2xl">
            <ClientSettingsForm />
          </div>
        </TabsContent>

        {isOwner ? (
          <TabsContent value="team" className="space-y-6">
            <div className="max-w-4xl">
              <TeamManagement />
            </div>
          </TabsContent>
        ) : null}

        <TabsContent value="social" className="space-y-6">
          <div className="max-w-2xl">
            <ClientTimezoneSetting />
          </div>
          <div className="max-w-2xl space-y-3 rounded-xl border bg-background p-5">
            <div>
              <h3 className="text-base font-semibold">Связанные аккаунты входа</h3>
              <p className="text-sm text-muted-foreground">
                Привяжите Telegram и/или VK к системному аккаунту.
              </p>
            </div>
            <ConnectedAccounts />
          </div>

          <div className="max-w-2xl space-y-3 rounded-xl border bg-background p-5">
            <div>
              <h3 className="text-base font-semibold">Канал связи по умолчанию</h3>
              <p className="text-sm text-muted-foreground">
                Этот канал будет использоваться первым при коммуникации с клиентом.
              </p>
            </div>
            <ChannelSelector mode="settings" />
          </div>

          <SocialAccountsManager />

          <div className="space-y-3 rounded-xl border bg-background p-5">
            <VkIntegrationsPanel />
          </div>
        </TabsContent>

        <TabsContent value="site" className="space-y-6">
          <div className="max-w-2xl">
            <SiteTab />
          </div>
        </TabsContent>

        <TabsContent value="payment" className="space-y-6">
          <PaymentTab />
        </TabsContent>

        <TabsContent value="kb" className="space-y-6">
          <KnowledgeBaseTab />
        </TabsContent>
      </Tabs>
      <RagChatWidget />
    </div>
  );
}
