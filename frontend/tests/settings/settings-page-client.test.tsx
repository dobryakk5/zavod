import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  replace: vi.fn(),
  role: 'owner' as 'owner' | 'editor' | 'viewer',
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: testState.replace }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/lib/hooks', () => ({
  useRole: () => ({ role: testState.role, loading: false, canEdit: testState.role !== 'viewer', canView: true }),
}));

vi.mock('@/components/settings/client-settings-form', () => ({
  ClientSettingsForm: () => <div>ClientSettingsForm</div>,
}));

vi.mock('@/components/settings/client-timezone-setting', () => ({
  ClientTimezoneSetting: () => <div>ClientTimezoneSetting</div>,
}));

vi.mock('@/components/auth/ConnectedAccounts', () => ({
  ConnectedAccounts: () => <div>ConnectedAccounts</div>,
}));

vi.mock('@/components/settings/social-accounts-manager', () => ({
  SocialAccountsManager: () => <div>SocialAccountsManager</div>,
}));

vi.mock('@/components/settings/channel-selector', () => ({
  ChannelSelector: () => <div>ChannelSelector</div>,
}));

vi.mock('@/components/settings/vk-integrations-panel', () => ({
  VkIntegrationsPanel: () => <div>VkIntegrationsPanel</div>,
}));

vi.mock('@/components/settings/payment-tab', () => ({
  PaymentTab: () => <div>PaymentTab</div>,
}));

vi.mock('@/components/settings/knowledge-base-tab', () => ({
  KnowledgeBaseTab: () => <div>KnowledgeBaseTab</div>,
}));

vi.mock('@/components/settings/site-tab', () => ({
  SiteTab: () => <div>SiteTab</div>,
}));

vi.mock('@/components/settings/team-management', () => ({
  TeamManagement: () => <div>TeamManagement</div>,
}));

vi.mock('@/components/settings/rag-chat-widget', () => ({
  RagChatWidget: () => <div>RagChatWidget</div>,
}));

describe('SettingsPageClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testState.role = 'owner';
  });

  afterEach(() => {
    cleanup();
  });

  it('shows team tab for owner', async () => {
    const mod = await import('@/app/settings/settings-page-client');
    const SettingsPageClient = mod.default;

    render(<SettingsPageClient />);

    expect(screen.getByRole('tab', { name: 'Команда' })).toBeInTheDocument();
  });

  it('hides team tab for editor', async () => {
    testState.role = 'editor';
    const mod = await import('@/app/settings/settings-page-client');
    const SettingsPageClient = mod.default;

    render(<SettingsPageClient />);

    expect(screen.queryByRole('tab', { name: 'Команда' })).not.toBeInTheDocument();
  });
});
