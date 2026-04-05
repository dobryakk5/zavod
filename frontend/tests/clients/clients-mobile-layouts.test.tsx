import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  searchParams: new URLSearchParams(),
  push: vi.fn(),
  router: { push: vi.fn() },
  crmContactsList: vi.fn(),
  crmDealsList: vi.fn(),
  crmEventsList: vi.fn(),
  crmEventTypesList: vi.fn(),
  crmAvailabilityList: vi.fn(),
  clientProductsList: vi.fn(),
  clientSettings: vi.fn(),
  inboxList: vi.fn(),
  inboxReply: vi.fn(),
  inboxAcceptCourse: vi.fn(),
  chainGetGraph: vi.fn(),
}));

vi.mock('next/link', async () => {
  const ReactModule = await import('react');
  return {
    default: ({ href, children, ...props }: any) => ReactModule.createElement('a', { href, ...props }, children),
  };
});

vi.mock('next/navigation', () => ({
  useRouter: () => testState.router,
  useSearchParams: () => ({
    get: (key: string) => testState.searchParams.get(key),
    toString: () => testState.searchParams.toString(),
  }),
}));

vi.mock('@/lib/api/crm', () => ({
  crmContactsApi: {
    list: (...args: unknown[]) => testState.crmContactsList(...args),
  },
  crmDealsApi: {
    list: (...args: unknown[]) => testState.crmDealsList(...args),
  },
  crmEventsApi: {
    list: (...args: unknown[]) => testState.crmEventsList(...args),
    update: vi.fn(),
    delete: vi.fn(),
  },
  crmEventTypesApi: {
    list: (...args: unknown[]) => testState.crmEventTypesList(...args),
  },
  crmAvailabilityEventsApi: {
    list: (...args: unknown[]) => testState.crmAvailabilityList(...args),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('@/lib/api/clientProducts', () => ({
  clientProductsApi: {
    list: (...args: unknown[]) => testState.clientProductsList(...args),
  },
}));

vi.mock('@/lib/api/client', () => ({
  clientApi: {
    getSettings: (...args: unknown[]) => testState.clientSettings(...args),
  },
}));

vi.mock('@/lib/api/unifiedInbox', () => ({
  unifiedInboxApi: {
    list: (...args: unknown[]) => testState.inboxList(...args),
    reply: (...args: unknown[]) => testState.inboxReply(...args),
    acceptCourse: (...args: unknown[]) => testState.inboxAcceptCourse(...args),
  },
}));

vi.mock('@/lib/api/chains', () => ({
  chainsApi: {
    forChain: () => ({
      getGraph: (...args: unknown[]) => testState.chainGetGraph(...args),
    }),
  },
}));

vi.mock('@/components/chain-editor', () => ({
  default: ({ chainId }: { chainId: number }) => <div data-testid="chain-editor">editor-{chainId}</div>,
}));

function mockMobileViewport() {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(max-width: 767px)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

describe('CRM mobile layouts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testState.searchParams = new URLSearchParams();
    testState.router = { push: testState.push };
    mockMobileViewport();

    testState.crmContactsList.mockResolvedValue([
      { id: 7, name: 'Анна Иванова', parent_id: null },
    ]);
    testState.crmDealsList.mockResolvedValue([
      {
        id: 11,
        contact_id: 7,
        contact_name: 'Анна Иванова',
        product_id: 5,
        stage: 'interest',
        amount: 25000,
        currency: 'rub',
        created_at: '2026-03-01T10:00:00.000Z',
        updated_at: '2026-03-02T10:00:00.000Z',
        lost_reason_code: '',
        lost_reason_text: '',
      },
    ]);
    testState.clientProductsList.mockResolvedValue([
      { id: 5, name: 'Флагман', structure: null },
    ]);
    testState.crmEventsList.mockResolvedValue([
      {
        id: 20,
        title: 'Диагностика',
        contact_id: 7,
        start_time: '2026-03-03T09:00:00.000Z',
        end_time: '2026-03-03T10:00:00.000Z',
        status: 'scheduled',
        location: '',
        event_type_id: null,
      },
    ]);
    testState.crmEventTypesList.mockResolvedValue([]);
    testState.crmAvailabilityList.mockResolvedValue([]);
    testState.clientSettings.mockResolvedValue({ timezone: 'Europe/Moscow' });
    testState.inboxList.mockResolvedValue({
      threads: [
        {
          id: 'thread-1',
          sourceChannel: 'telegram',
          inquiryType: 'support',
          serviceLevel: 'high',
          slaState: 'risk',
          slaDeadlineLabel: 'До SLA 10 мин',
          status: 'new',
          unreadCount: 2,
          subject: 'Не пришёл доступ',
          lastMessagePreview: 'Не вижу письмо с доступом',
          lastMessageAtLabel: 'Сегодня, 10:12',
          lastMessageSort: 10,
          client: {
            id: 7,
            name: 'Анна Иванова',
            company: 'Studio',
            manager: 'Мария',
            phone: '+79991234567',
            email: 'anna@example.com',
            tags: ['VIP'],
            channels: [{ channel: 'telegram', handle: '@anna' }],
            notes: 'Пишет только в Telegram',
          },
          messages: [
            {
              id: 'm1',
              channel: 'telegram',
              direction: 'in',
              author: 'Анна Иванова',
              text: 'Не вижу письмо с доступом',
              createdAtLabel: 'Сегодня, 10:12',
              createdAtSort: 10,
            },
          ],
        },
      ],
      sources: null,
    });
    testState.inboxReply.mockResolvedValue({
      message: {
        id: 'm2',
        channel: 'telegram',
        direction: 'out',
        author: 'Мария',
        text: 'Отправили повторно',
        createdAtLabel: 'Сегодня, 10:15',
        createdAtSort: 11,
      },
    });
    testState.inboxAcceptCourse.mockResolvedValue({});
    testState.chainGetGraph.mockResolvedValue({
      chain: {
        id: 12,
        tenant_id: 1,
        name: 'Welcome chain',
        description: 'Приветственная цепочка',
        status: 'draft',
        start_node_id: 1,
        created_at: '2026-03-01T10:00:00.000Z',
        updated_at: '2026-03-02T10:00:00.000Z',
      },
      nodes: [
        { id: 1, chain_id: 12, node_type: 'start', payload: {}, delay_seconds: 0, pos_x: 0, pos_y: 0, created_at: '', updated_at: '' },
        { id: 2, chain_id: 12, node_type: 'text', payload: {}, delay_seconds: 0, pos_x: 0, pos_y: 0, created_at: '', updated_at: '' },
        { id: 3, chain_id: 12, node_type: 'buttons', payload: {}, delay_seconds: 0, pos_x: 0, pos_y: 0, created_at: '', updated_at: '' },
      ],
      edges: [
        { id: 1, chain_id: 12, source_node_id: 1, target_node_id: 2, priority: 0, created_at: '', updated_at: '' },
      ],
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('renders CRM shell navigation chips', async () => {
    const mod = await import('@/app/clients/deals/page');
    const DealsPage = mod.default;

    render(<DealsPage />);

    expect(screen.getByRole('heading', { name: 'Сделки' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Разделы CRM' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Клиенты' })).toHaveAttribute('href', '/clients/list');
    expect(screen.getByRole('link', { name: 'ChatBot' })).toHaveAttribute('href', '/clients/chatbot');
  });

  it('renders deals as mobile cards', async () => {
    const mod = await import('@/app/clients/deals-tab');
    const DealsTab = mod.DealsTab;

    render(<DealsTab />);

    await waitFor(() => {
      expect(screen.getByTestId('deals-mobile-list')).toBeInTheDocument();
    });

    const mobileList = screen.getByTestId('deals-mobile-list');
    expect(within(mobileList).getByText('Флагман')).toBeInTheDocument();
    expect(within(mobileList).getByText('Анна Иванова')).toBeInTheDocument();
    expect(within(mobileList).getByRole('link', { name: /Флагман/i })).toHaveAttribute('href', '/clients/deals/11');
  });

  it('renders schedule in mobile agenda mode', async () => {
    const mod = await import('@/app/clients/clients-schedule');
    const ClientsSchedule = mod.default;

    render(<ClientsSchedule />);

    await waitFor(() => {
      expect(screen.getByTestId('clients-schedule-mobile-agenda')).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: 'Лента дня' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Добавить свободное окно' })).toBeInTheDocument();
  });

  it('uses stepped mobile inbox flow', async () => {
    const mod = await import('@/app/clients/unified-inbox-tab');
    const UnifiedInboxTab = mod.default;

    render(<UnifiedInboxTab />);

    await waitFor(() => {
      expect(screen.getByText('Не пришёл доступ')).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: 'Фильтры' })).toBeInTheDocument();

    fireEvent.click(screen.getByText('Не пришёл доступ'));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '← К очереди' })).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: 'Клиент' })).toBeInTheDocument();
  });

  it('shows chatbot summary mode on mobile detail page', async () => {
    const mod = await import('@/app/clients/chatbot/[chainId]/page');
    const ChatbotChainPage = mod.default;

    const element = await ChatbotChainPage({
      params: Promise.resolve({ chainId: '12' }),
    });

    render(element);

    await waitFor(() => {
      expect(screen.getByTestId('chatbot-mobile-summary')).toBeInTheDocument();
    });

    expect(screen.getByText('Welcome chain')).toBeInTheDocument();
    expect(screen.getByText('Canvas-редактор оставлен для планшета и десктопа. На телефоне доступна только сводка.')).toBeInTheDocument();
  });
});
