'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  unifiedInboxApi,
  type UnifiedInboxClientCard as ApiClientCardData,
  type UnifiedInboxClientChannelHandle as ApiClientChannelHandle,
  type UnifiedInboxMessageDirection as ApiMessageDirection,
  type UnifiedInboxResponse,
  type UnifiedInboxSlaState as ApiSlaState,
  type UnifiedInboxThread as ApiInboxThread,
  type UnifiedInboxThreadMessage as ApiThreadMessage,
  type UnifiedInboxThreadStatus as ApiThreadStatus,
  type UnifiedInboxInquiryType as ApiInquiryType,
  type UnifiedInboxServiceLevel as ApiServiceLevel,
  type UnifiedInboxChannel as ApiInboxChannel,
} from '@/lib/api/unifiedInbox';
import { cn } from '@/lib/utils';

type InboxChannel = ApiInboxChannel;
type InquiryType = ApiInquiryType;
type ServiceLevel = ApiServiceLevel;
type ThreadStatus = ApiThreadStatus;
type SlaState = ApiSlaState;
type MessageDirection = ApiMessageDirection;
type ThreadMessage = ApiThreadMessage;
type ClientChannelHandle = ApiClientChannelHandle;
type ClientCardData = ApiClientCardData;
type InboxThread = ApiInboxThread;

type SourceInfo = NonNullable<UnifiedInboxResponse['sources']>;

const CHANNEL_META: Record<InboxChannel, { label: string; short: string; badgeClass: string }> = {
  telegram: {
    label: 'Telegram',
    short: 'TG',
    badgeClass: 'border-blue-200 bg-blue-50 text-blue-700',
  },
  whatsapp: {
    label: 'WhatsApp',
    short: 'WA',
    badgeClass: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  },
  email: {
    label: 'Email',
    short: 'Email',
    badgeClass: 'border-slate-200 bg-slate-50 text-slate-700',
  },
  vk: {
    label: 'VK',
    short: 'VK',
    badgeClass: 'border-indigo-200 bg-indigo-50 text-indigo-700',
  },
  instagram: {
    label: 'Instagram',
    short: 'IG',
    badgeClass: 'border-pink-200 bg-pink-50 text-pink-700',
  },
  courses: {
    label: 'Курсы',
    short: 'LMS',
    badgeClass: 'border-teal-200 bg-teal-50 text-teal-700',
  },
};

const INQUIRY_TYPE_LABELS: Record<InquiryType, string> = {
  support: 'Поддержка',
  sales: 'Продажа',
  payment: 'Оплата',
  documents: 'Документы',
  feedback: 'Обратная связь',
};

const SERVICE_LEVEL_LABELS: Record<ServiceLevel, string> = {
  critical: 'Критичный',
  high: 'Высокий',
  normal: 'Нормальный',
  low: 'Базовый',
};

const SERVICE_LEVEL_BADGE_CLASS: Record<ServiceLevel, string> = {
  critical: 'border-red-200 bg-red-50 text-red-700',
  high: 'border-orange-200 bg-orange-50 text-orange-700',
  normal: 'border-sky-200 bg-sky-50 text-sky-700',
  low: 'border-gray-200 bg-gray-50 text-gray-700',
};

const THREAD_STATUS_LABELS: Record<ThreadStatus, string> = {
  new: 'Новый',
  in_progress: 'В работе',
  waiting_client: 'Ждём клиента',
  closed: 'Закрыт',
};

const THREAD_STATUS_BADGE_CLASS: Record<ThreadStatus, string> = {
  new: 'border-rose-200 bg-rose-50 text-rose-700',
  in_progress: 'border-amber-200 bg-amber-50 text-amber-700',
  waiting_client: 'border-violet-200 bg-violet-50 text-violet-700',
  closed: 'border-emerald-200 bg-emerald-50 text-emerald-700',
};

const SLA_LABELS: Record<SlaState, string> = {
  breached: 'SLA просрочен',
  risk: 'SLA под риском',
  ok: 'SLA в норме',
};

const SLA_BADGE_CLASS: Record<SlaState, string> = {
  breached: 'border-red-200 bg-red-50 text-red-700',
  risk: 'border-yellow-200 bg-yellow-50 text-yellow-700',
  ok: 'border-emerald-200 bg-emerald-50 text-emerald-700',
};

const selectClassName =
  'h-9 rounded-md border border-input bg-white px-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring';
const REPLY_CHANNEL_WHITELIST = new Set<InboxChannel>(['courses', 'telegram', 'vk', 'email']);

function createSeedThreads(): InboxThread[] {
  return [
    {
      id: 'thread-anna',
      sourceChannel: 'telegram',
      inquiryType: 'support',
      serviceLevel: 'critical',
      slaState: 'breached',
      slaDeadlineLabel: 'Ответ просрочен на 18 мин',
      status: 'new',
      unreadCount: 3,
      subject: 'Не открывается доступ к модулю после оплаты',
      lastMessagePreview: 'Оплатила час назад, в кабинете всё ещё нет доступа. Можете проверить?',
      lastMessageAtLabel: 'Сегодня, 10:42',
      lastMessageSort: 1_000,
      client: {
        id: 142,
        name: 'Анна Петрова',
        company: 'Школа речи "Голос"',
        manager: 'Мария К.',
        phone: '+7 999 123-45-67',
        email: 'anna@voice-school.ru',
        tags: ['VIP', 'Повторная покупка', 'Онлайн-курс'],
        channels: [
          { channel: 'telegram', handle: '@annapetrova' },
          { channel: 'email', handle: 'anna@voice-school.ru' },
          { channel: 'whatsapp', handle: '+7 999 123-45-67' },
        ],
        notes: 'Пишет часто в Telegram, но документы просит отправлять на email.',
      },
      messages: [
        {
          id: 'm-anna-1',
          channel: 'email',
          direction: 'in',
          author: 'Анна Петрова',
          text: 'Добрый день! Оплатила тариф "Практикум", жду доступ и чек на почту.',
          createdAtLabel: 'Сегодня, 09:58',
          createdAtSort: 998,
        },
        {
          id: 'm-anna-2',
          channel: 'telegram',
          direction: 'in',
          author: 'Анна Петрова',
          text: 'Продублирую сюда: оплатыла, но уроки не открываются.',
          createdAtLabel: 'Сегодня, 10:09',
          createdAtSort: 999,
        },
        {
          id: 'm-anna-3',
          channel: 'telegram',
          direction: 'in',
          author: 'Анна Петрова',
          text: 'Оплатила час назад, в кабинете всё ещё нет доступа. Можете проверить?',
          createdAtLabel: 'Сегодня, 10:42',
          createdAtSort: 1_000,
        },
      ],
    },
    {
      id: 'thread-igor',
      sourceChannel: 'vk',
      inquiryType: 'sales',
      serviceLevel: 'high',
      slaState: 'risk',
      slaDeadlineLabel: 'До SLA 12 мин',
      status: 'in_progress',
      unreadCount: 1,
      subject: 'Запрос коммерческого предложения для команды',
      lastMessagePreview: 'Нас 8 человек, нужен доступ с оплатой по счёту. Что посоветуете?',
      lastMessageAtLabel: 'Сегодня, 10:31',
      lastMessageSort: 990,
      client: {
        id: 218,
        name: 'Игорь Смирнов',
        company: 'ООО НордТех',
        manager: 'Олег С.',
        phone: '+7 921 777-12-12',
        email: 'igor@nordtech.ru',
        tags: ['B2B', 'Новый лид', 'Счёт/договор'],
        channels: [
          { channel: 'vk', handle: 'vk.com/igor.smirnov' },
          { channel: 'email', handle: 'igor@nordtech.ru' },
          { channel: 'whatsapp', handle: '+7 921 777-12-12' },
        ],
        notes: 'Предпочитает перейти на email после первичного контакта во ВКонтакте.',
      },
      messages: [
        {
          id: 'm-igor-1',
          channel: 'vk',
          direction: 'in',
          author: 'Игорь Смирнов',
          text: 'Здравствуйте. Ищем платформу для внутреннего обучения менеджеров.',
          createdAtLabel: 'Сегодня, 10:12',
          createdAtSort: 986,
        },
        {
          id: 'm-igor-2',
          channel: 'vk',
          direction: 'out',
          author: 'Мария К.',
          text: 'Добрый день! Подскажите количество сотрудников и нужен ли договор/счёт?',
          createdAtLabel: 'Сегодня, 10:18',
          createdAtSort: 987,
        },
        {
          id: 'm-igor-3',
          channel: 'vk',
          direction: 'in',
          author: 'Игорь Смирнов',
          text: 'Нас 8 человек, нужен доступ с оплатой по счёту. Что посоветуете?',
          createdAtLabel: 'Сегодня, 10:31',
          createdAtSort: 990,
        },
      ],
    },
    {
      id: 'thread-elena',
      sourceChannel: 'email',
      inquiryType: 'payment',
      serviceLevel: 'normal',
      slaState: 'ok',
      slaDeadlineLabel: 'SLA до 14:30',
      status: 'waiting_client',
      unreadCount: 0,
      subject: 'Чек и закрывающие документы за январь',
      lastMessagePreview: 'Отправили акт и чек. Ждём подтверждение получения.',
      lastMessageAtLabel: 'Сегодня, 09:47',
      lastMessageSort: 950,
      client: {
        id: 301,
        name: 'Елена Воронцова',
        company: 'ИП Воронцова',
        manager: 'Мария К.',
        phone: '+7 926 888-33-11',
        email: 'finance@vorontsova.pro',
        tags: ['Бухгалтерия', 'Документы', 'Активный'],
        channels: [
          { channel: 'email', handle: 'finance@vorontsova.pro' },
          { channel: 'whatsapp', handle: '+7 926 888-33-11' },
        ],
      },
      messages: [
        {
          id: 'm-elena-1',
          channel: 'email',
          direction: 'in',
          author: 'Елена Воронцова',
          text: 'Нужны чек и акт за январь, пожалуйста отправьте на эту почту.',
          createdAtLabel: 'Сегодня, 09:05',
          createdAtSort: 944,
        },
        {
          id: 'm-elena-2',
          channel: 'email',
          direction: 'out',
          author: 'Мария К.',
          text: 'Отправили чек и акт во вложении, проверьте пожалуйста.',
          createdAtLabel: 'Сегодня, 09:47',
          createdAtSort: 950,
        },
      ],
    },
    {
      id: 'thread-maksim',
      sourceChannel: 'whatsapp',
      inquiryType: 'documents',
      serviceLevel: 'high',
      slaState: 'risk',
      slaDeadlineLabel: 'До SLA 27 мин',
      status: 'new',
      unreadCount: 2,
      subject: 'Нужен шаблон договора под юрлицо',
      lastMessagePreview: 'Можно прислать шаблон договора и реквизиты вашей компании?',
      lastMessageAtLabel: 'Сегодня, 10:03',
      lastMessageSort: 970,
      client: {
        id: 377,
        name: 'Максим Давыдов',
        company: 'ООО СтримМаркет',
        manager: 'Олег С.',
        phone: '+7 903 222-40-50',
        email: 'maxim@streammarket.ru',
        tags: ['Юрлицо', 'Договор', 'Лид'],
        channels: [
          { channel: 'whatsapp', handle: '+7 903 222-40-50' },
          { channel: 'telegram', handle: '@mdvydov' },
          { channel: 'email', handle: 'maxim@streammarket.ru' },
        ],
        notes: 'Начал в WhatsApp, готов перейти в email для документов.',
      },
      messages: [
        {
          id: 'm-max-1',
          channel: 'whatsapp',
          direction: 'in',
          author: 'Максим Давыдов',
          text: 'Здравствуйте, хочу подключить 2 менеджеров на тест.',
          createdAtLabel: 'Сегодня, 09:51',
          createdAtSort: 965,
        },
        {
          id: 'm-max-2',
          channel: 'whatsapp',
          direction: 'in',
          author: 'Максим Давыдов',
          text: 'Можно прислать шаблон договора и реквизиты вашей компании?',
          createdAtLabel: 'Сегодня, 10:03',
          createdAtSort: 970,
        },
      ],
    },
    {
      id: 'thread-ksenia',
      sourceChannel: 'instagram',
      inquiryType: 'feedback',
      serviceLevel: 'low',
      slaState: 'ok',
      slaDeadlineLabel: 'SLA до 18:00',
      status: 'closed',
      unreadCount: 0,
      subject: 'Отзыв после внедрения + вопрос по продлению',
      lastMessagePreview: 'Спасибо за быстрый ответ, продлимся в следующем месяце.',
      lastMessageAtLabel: 'Вчера, 18:24',
      lastMessageSort: 880,
      client: {
        id: 419,
        name: 'Ксения Миронова',
        company: 'Студия "Mira"',
        manager: 'Мария К.',
        phone: '+7 916 444-22-11',
        email: 'hello@mirastudio.ru',
        tags: ['Соцсети', 'Лояльный', 'Продление'],
        channels: [
          { channel: 'instagram', handle: '@mirastudio' },
          { channel: 'telegram', handle: '@kseniamira' },
          { channel: 'email', handle: 'hello@mirastudio.ru' },
        ],
      },
      messages: [
        {
          id: 'm-ks-1',
          channel: 'instagram',
          direction: 'in',
          author: 'Ксения Миронова',
          text: 'Спасибо за внедрение 🙌 Подскажите, когда лучше продлевать тариф?',
          createdAtLabel: 'Вчера, 17:58',
          createdAtSort: 875,
        },
        {
          id: 'm-ks-2',
          channel: 'telegram',
          direction: 'out',
          author: 'Мария К.',
          text: 'Лучше за 3-5 дней до окончания, я напомню и подготовлю ссылку.',
          createdAtLabel: 'Вчера, 18:05',
          createdAtSort: 878,
        },
        {
          id: 'm-ks-3',
          channel: 'instagram',
          direction: 'in',
          author: 'Ксения Миронова',
          text: 'Спасибо за быстрый ответ, продлимся в следующем месяце.',
          createdAtLabel: 'Вчера, 18:24',
          createdAtSort: 880,
        },
      ],
    },
  ];
}

function channelBadge(channel: InboxChannel) {
  const meta = CHANNEL_META[channel];
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium',
        meta.badgeClass,
      )}
      title={meta.label}
    >
      {meta.short}
    </span>
  );
}

function serviceLevelRank(level: ServiceLevel) {
  switch (level) {
    case 'critical':
      return 4;
    case 'high':
      return 3;
    case 'normal':
      return 2;
    case 'low':
      return 1;
  }
}

type ChannelFilter = 'all' | InboxChannel;
type InquiryTypeFilter = 'all' | InquiryType;
type ServiceLevelFilter = 'all' | ServiceLevel;
type StatusFilter = 'all' | ThreadStatus;
type SlaFilter = 'all' | SlaState;

export default function UnifiedInboxTab() {
  const [threads, setThreads] = useState<InboxThread[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sourceInfo, setSourceInfo] = useState<SourceInfo | null>(null);
  const [search, setSearch] = useState('');
  const [channelFilter, setChannelFilter] = useState<ChannelFilter>('all');
  const [inquiryTypeFilter, setInquiryTypeFilter] = useState<InquiryTypeFilter>('all');
  const [serviceLevelFilter, setServiceLevelFilter] = useState<ServiceLevelFilter>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [slaFilter, setSlaFilter] = useState<SlaFilter>('all');
  const [onlyUnread, setOnlyUnread] = useState(false);
  const [draftsByThreadId, setDraftsByThreadId] = useState<Record<string, string>>({});
  const [replyChannelByThreadId, setReplyChannelByThreadId] = useState<Partial<Record<string, InboxChannel>>>({});
  const [sendingThreadId, setSendingThreadId] = useState<string | null>(null);
  const [acceptingThreadId, setAcceptingThreadId] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const loadThreads = async () => {
      setIsLoading(true);
      setLoadError(null);
      try {
        const response = await unifiedInboxApi.list();
        if (!isActive) return;
        setThreads(Array.isArray(response.threads) ? response.threads : []);
        setSourceInfo(response.sources ?? null);
        setSelectedThreadId((prev) => {
          if (prev && response.threads.some((thread) => thread.id === prev)) return prev;
          return response.threads[0]?.id ?? '';
        });
      } catch (error) {
        if (!isActive) return;
        console.error('Failed to load unified inbox threads', error);
        setLoadError('Не удалось загрузить реальные входящие сообщения (Telegram/VK/Email).');
        setThreads([]);
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    void loadThreads();

    return () => {
      isActive = false;
    };
  }, []);

  const allStats = useMemo(() => {
    const unread = threads.filter((thread) => thread.unreadCount > 0).length;
    const slaRisk = threads.filter((thread) => thread.slaState === 'risk' || thread.slaState === 'breached').length;
    const byChannel = threads.reduce<Record<InboxChannel, number>>(
      (acc, thread) => {
        acc[thread.sourceChannel] += 1;
        return acc;
      },
      {
        telegram: 0,
        whatsapp: 0,
        email: 0,
        vk: 0,
        instagram: 0,
        courses: 0,
      },
    );

    return {
      total: threads.length,
      unread,
      slaRisk,
      byChannel,
    };
  }, [threads]);

  const filteredThreads = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();

    return [...threads]
      .filter((thread) => {
        if (channelFilter !== 'all' && thread.sourceChannel !== channelFilter) return false;
        if (inquiryTypeFilter !== 'all' && thread.inquiryType !== inquiryTypeFilter) return false;
        if (serviceLevelFilter !== 'all' && thread.serviceLevel !== serviceLevelFilter) return false;
        if (statusFilter !== 'all' && thread.status !== statusFilter) return false;
        if (slaFilter !== 'all' && thread.slaState !== slaFilter) return false;
        if (onlyUnread && thread.unreadCount === 0) return false;

        if (!normalizedSearch) return true;

        const haystack = [
          thread.client.name,
          thread.client.company ?? '',
          thread.subject,
          thread.lastMessagePreview,
          thread.client.email ?? '',
          thread.client.phone ?? '',
          ...thread.client.tags,
          ...thread.messages.map((message) => message.text),
        ]
          .join(' ')
          .toLowerCase();

        return haystack.includes(normalizedSearch);
      })
      .sort((a, b) => {
        const slaDelta = (b.slaState === 'breached' ? 2 : b.slaState === 'risk' ? 1 : 0)
          - (a.slaState === 'breached' ? 2 : a.slaState === 'risk' ? 1 : 0);
        if (slaDelta !== 0) return slaDelta;

        const serviceDelta = serviceLevelRank(b.serviceLevel) - serviceLevelRank(a.serviceLevel);
        if (serviceDelta !== 0) return serviceDelta;

        return b.lastMessageSort - a.lastMessageSort;
      });
  }, [threads, channelFilter, inquiryTypeFilter, serviceLevelFilter, statusFilter, slaFilter, onlyUnread, search]);

  const activeThread = useMemo(() => {
    if (filteredThreads.length === 0) return null;
    return filteredThreads.find((thread) => thread.id === selectedThreadId) ?? filteredThreads[0];
  }, [filteredThreads, selectedThreadId]);

  const activeReplyChannels = useMemo(() => {
    if (!activeThread) return [] as InboxChannel[];
    const channels: InboxChannel[] = [];
    const pushUnique = (value: InboxChannel) => {
      if (!REPLY_CHANNEL_WHITELIST.has(value)) return;
      if (!channels.includes(value)) channels.push(value);
    };

    pushUnique(activeThread.sourceChannel);
    activeThread.client.channels.forEach((item) => pushUnique(item.channel));
    return channels;
  }, [activeThread]);

  const activeDraft = activeThread ? (draftsByThreadId[activeThread.id] ?? '') : '';
  const activeReplyChannel = activeThread
    ? (activeReplyChannels.includes(replyChannelByThreadId[activeThread.id] as InboxChannel)
      ? (replyChannelByThreadId[activeThread.id] as InboxChannel)
      : (activeReplyChannels[0] ?? 'telegram'))
    : 'telegram';

  const handleSelectThread = (threadId: string) => {
    setSelectedThreadId(threadId);
    setSendError(null);
    setThreads((prev) =>
      prev.map((thread) =>
        thread.id === threadId && thread.unreadCount > 0
          ? { ...thread, unreadCount: 0 }
          : thread,
      ),
    );
  };

  const handleUpdateStatus = (nextStatus: ThreadStatus) => {
    if (!activeThread) return;
    setThreads((prev) =>
      prev.map((thread) =>
        thread.id === activeThread.id
          ? { ...thread, status: nextStatus }
          : thread,
      ),
    );
  };

  const handleSendReply = async () => {
    if (!activeThread) return;
    const text = activeDraft.trim();
    if (!text) return;

    setSendError(null);
    setSendingThreadId(activeThread.id);
    try {
      const response = await unifiedInboxApi.reply({
        thread_id: activeThread.id,
        channel: activeReplyChannel,
        text,
        contact_id: activeThread.client.id > 0 ? activeThread.client.id : undefined,
      });

      setThreads((prev) =>
        prev.map((thread) => {
          if (thread.id !== activeThread.id) return thread;

          const nextMessages: ThreadMessage[] = [...thread.messages, response.message];
          return {
            ...thread,
            status: thread.status === 'closed' ? 'in_progress' : thread.status,
            unreadCount: 0,
            lastMessagePreview: response.message.text,
            lastMessageAtLabel: response.message.createdAtLabel,
            lastMessageSort: response.message.createdAtSort,
            messages: nextMessages,
          };
        }),
      );
      setDraftsByThreadId((prev) => ({ ...prev, [activeThread.id]: '' }));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Не удалось отправить сообщение.';
      setSendError(message);
    } finally {
      setSendingThreadId(null);
    }
  };

  const handleAcceptCourse = async () => {
    if (!activeThread || activeThread.sourceChannel !== 'courses') return;
    if (!activeThread.courseEvent || activeThread.courseEvent.accepted) return;

    setSendError(null);
    setAcceptingThreadId(activeThread.id);
    try {
      const response = await unifiedInboxApi.acceptCourse({ thread_id: activeThread.id });
      setThreads((prev) =>
        prev.map((thread) => {
          if (thread.id !== activeThread.id) return thread;
          const nextMessages = response.message ? [...thread.messages, response.message] : thread.messages;
          return {
            ...thread,
            status: 'closed',
            serviceLevel: 'normal',
            courseEvent: thread.courseEvent ? { ...thread.courseEvent, accepted: true } : thread.courseEvent,
            lastMessagePreview: response.message?.text || thread.lastMessagePreview,
            lastMessageAtLabel: response.message?.createdAtLabel || thread.lastMessageAtLabel,
            lastMessageSort: response.message?.createdAtSort || thread.lastMessageSort,
            messages: nextMessages,
          };
        }),
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Не удалось принять урок.';
      setSendError(message);
    } finally {
      setAcceptingThreadId(null);
    }
  };

  const activeClientTimeline = useMemo(() => {
    if (!activeThread) return [];
    return [...activeThread.messages]
      .sort((a, b) => b.createdAtSort - a.createdAtSort)
      .slice(0, 6);
  }, [activeThread]);

  return (
    <div className="space-y-4">
      <div className="rounded-xl border bg-gradient-to-r from-slate-50 to-white p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Входящие</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Единый inbox по каналам: Telegram, WhatsApp, email и соцсети. Менеджер отвечает из одного окна,
              история общения хранится в карточке клиента.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <div className="rounded-md border bg-white px-3 py-1.5">
              Диалогов: <span className="font-semibold">{allStats.total}</span>
            </div>
            <div className="rounded-md border bg-white px-3 py-1.5">
              Непрочитанные: <span className="font-semibold">{allStats.unread}</span>
            </div>
            <div className="rounded-md border bg-white px-3 py-1.5">
              SLA под контролем: <span className="font-semibold">{allStats.slaRisk}</span>
            </div>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {(Object.keys(CHANNEL_META) as InboxChannel[]).map((channel) => (
            <div key={channel} className="rounded-full border bg-white px-3 py-1 text-xs text-slate-700">
              {CHANNEL_META[channel].label}: <span className="font-semibold">{allStats.byChannel[channel]}</span>
            </div>
          ))}
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {isLoading && (
            <div className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600">
              Загрузка реальных входящих…
            </div>
          )}
          {loadError && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-1.5 text-xs text-red-700">
              {loadError}
            </div>
          )}
          {sourceInfo?.telegram && (
            <div className="rounded-md border bg-white px-3 py-1.5 text-xs">
              Telegram: <span className="font-semibold">{sourceInfo.telegram.thread_count}</span>
            </div>
          )}
          {sourceInfo?.vk && (
            <div className="rounded-md border bg-white px-3 py-1.5 text-xs">
              VK: <span className="font-semibold">{sourceInfo.vk.thread_count}</span>
            </div>
          )}
          {sourceInfo?.email && (
            <div className="rounded-md border bg-white px-3 py-1.5 text-xs">
              Email: <span className="font-semibold">{sourceInfo.email.thread_count}</span>
              {!sourceInfo.email.enabled && sourceInfo.email.reason ? (
                <span className="text-muted-foreground"> · {sourceInfo.email.reason}</span>
              ) : null}
            </div>
          )}
          {sourceInfo?.courses && (
            <div className="rounded-md border bg-white px-3 py-1.5 text-xs">
              Курсы: <span className="font-semibold">{sourceInfo.courses.thread_count}</span>
            </div>
          )}
        </div>
      </div>

      <div className="rounded-xl border bg-white p-4">
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1.1fr_1fr_1fr_1fr_auto]">
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Поиск по клиенту, сообщению, email, телефону..."
          />

          <select
            value={channelFilter}
            onChange={(event) => setChannelFilter(event.target.value as ChannelFilter)}
            className={selectClassName}
            aria-label="Фильтр по каналу"
          >
            <option value="all">Все каналы</option>
            {(Object.keys(CHANNEL_META) as InboxChannel[]).map((channel) => (
              <option key={channel} value={channel}>
                {CHANNEL_META[channel].label}
              </option>
            ))}
          </select>

          <select
            value={inquiryTypeFilter}
            onChange={(event) => setInquiryTypeFilter(event.target.value as InquiryTypeFilter)}
            className={selectClassName}
            aria-label="Фильтр по типу обращения"
          >
            <option value="all">Все типы</option>
            {(Object.keys(INQUIRY_TYPE_LABELS) as InquiryType[]).map((type) => (
              <option key={type} value={type}>
                {INQUIRY_TYPE_LABELS[type]}
              </option>
            ))}
          </select>

          <select
            value={serviceLevelFilter}
            onChange={(event) => setServiceLevelFilter(event.target.value as ServiceLevelFilter)}
            className={selectClassName}
            aria-label="Фильтр по уровню сервиса"
          >
            <option value="all">Уровень сервиса: все</option>
            {(Object.keys(SERVICE_LEVEL_LABELS) as ServiceLevel[]).map((level) => (
              <option key={level} value={level}>
                {SERVICE_LEVEL_LABELS[level]}
              </option>
            ))}
          </select>

          <Button
            type="button"
            variant={onlyUnread ? 'default' : 'outline'}
            className="h-9"
            onClick={() => setOnlyUnread((prev) => !prev)}
          >
            Только непрочитанные
          </Button>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <span className="text-xs text-muted-foreground pt-1">SLA:</span>
          {([
            ['all', 'Все'],
            ['breached', 'Просрочено'],
            ['risk', 'Под риском'],
            ['ok', 'В норме'],
          ] as Array<[SlaFilter, string]>).map(([value, label]) => (
            <Button
              key={value}
              type="button"
              size="sm"
              variant={slaFilter === value ? 'secondary' : 'outline'}
              className="h-7 text-xs"
              onClick={() => setSlaFilter(value)}
            >
              {label}
            </Button>
          ))}

          <span className="ml-2 text-xs text-muted-foreground pt-1">Статус:</span>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
            className={cn(selectClassName, 'h-7 px-2 text-xs')}
            aria-label="Фильтр по статусу обращения"
          >
            <option value="all">Все статусы</option>
            {(Object.keys(THREAD_STATUS_LABELS) as ThreadStatus[]).map((status) => (
              <option key={status} value={status}>
                {THREAD_STATUS_LABELS[status]}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[360px_minmax(0,1fr)_320px]">
        <div className="rounded-xl border bg-white">
          <div className="border-b px-4 py-3">
            <div className="text-sm font-semibold">Очередь входящих</div>
            <div className="text-xs text-muted-foreground mt-1">
              {filteredThreads.length} диалог(ов) по текущим фильтрам
            </div>
          </div>

          <div className="max-h-[720px] overflow-y-auto">
            {isLoading ? (
              <div className="p-4 text-sm text-muted-foreground">Загружаем входящие сообщения…</div>
            ) : filteredThreads.length === 0 ? (
              <div className="p-4 text-sm text-muted-foreground">
                Ничего не найдено. Сбросьте фильтры или измените поиск.
              </div>
            ) : (
              filteredThreads.map((thread) => {
                const isActive = activeThread?.id === thread.id;
                return (
                  <button
                    key={thread.id}
                    type="button"
                    onClick={() => handleSelectThread(thread.id)}
                    className={cn(
                      'w-full border-b px-4 py-3 text-left transition-colors hover:bg-slate-50',
                      isActive && 'bg-slate-50',
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          {channelBadge(thread.sourceChannel)}
                          <span className="truncate text-sm font-medium">{thread.client.name}</span>
                          {thread.unreadCount > 0 && (
                            <span className="rounded-full bg-slate-900 px-2 py-0.5 text-[10px] font-semibold text-white">
                              {thread.unreadCount}
                            </span>
                          )}
                        </div>
                        <div className="mt-1 truncate text-xs text-muted-foreground">
                          {thread.client.company || `ID клиента: ${thread.client.id}`}
                        </div>
                      </div>

                      <div className="text-right text-[11px] text-muted-foreground">
                        {thread.lastMessageAtLabel}
                      </div>
                    </div>

                    <div className="mt-2 truncate text-sm font-medium">{thread.subject}</div>
                    <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                      {thread.lastMessagePreview}
                    </div>

                    <div className="mt-3 flex flex-wrap gap-1.5">
                      <span
                        className={cn(
                          'inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium',
                          SERVICE_LEVEL_BADGE_CLASS[thread.serviceLevel],
                        )}
                      >
                        {SERVICE_LEVEL_LABELS[thread.serviceLevel]}
                      </span>
                      <span
                        className={cn(
                          'inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium',
                          SLA_BADGE_CLASS[thread.slaState],
                        )}
                      >
                        {SLA_LABELS[thread.slaState]}
                      </span>
                      <span
                        className={cn(
                          'inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium',
                          THREAD_STATUS_BADGE_CLASS[thread.status],
                        )}
                      >
                        {THREAD_STATUS_LABELS[thread.status]}
                      </span>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        <div className="rounded-xl border bg-white">
          {activeThread ? (
            <div className="flex h-full min-h-[720px] flex-col">
              <div className="border-b px-4 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-semibold">{activeThread.client.name}</h3>
                      {channelBadge(activeThread.sourceChannel)}
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">{activeThread.subject}</p>
                  </div>

                  <div className="flex flex-wrap gap-1.5">
                    <Badge variant="outline" className={cn('border', THREAD_STATUS_BADGE_CLASS[activeThread.status])}>
                      {THREAD_STATUS_LABELS[activeThread.status]}
                    </Badge>
                    <Badge variant="outline" className={cn('border', SERVICE_LEVEL_BADGE_CLASS[activeThread.serviceLevel])}>
                      {SERVICE_LEVEL_LABELS[activeThread.serviceLevel]}
                    </Badge>
                    <Badge variant="outline" className={cn('border', SLA_BADGE_CLASS[activeThread.slaState])}>
                      {activeThread.slaDeadlineLabel}
                    </Badge>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  <Button type="button" size="sm" variant="outline" onClick={() => handleUpdateStatus('in_progress')}>
                    В работу
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => handleUpdateStatus('waiting_client')}>
                    Ждём клиента
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => handleUpdateStatus('closed')}>
                    Закрыть
                  </Button>
                  {activeThread.sourceChannel === 'courses' && activeThread.courseEvent && !activeThread.courseEvent.accepted ? (
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => { void handleAcceptCourse(); }}
                      disabled={acceptingThreadId === activeThread.id}
                    >
                      {acceptingThreadId === activeThread.id ? 'Принимаем...' : 'Принять'}
                    </Button>
                  ) : null}
                  {activeThread.sourceChannel === 'courses' && activeThread.courseEvent?.curator_url ? (
                    <Button asChild type="button" size="sm" variant="outline">
                      <Link href={activeThread.courseEvent.curator_url}>Открыть урок</Link>
                    </Button>
                  ) : null}
                </div>
              </div>

              <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
                {activeThread.messages
                  .slice()
                  .sort((a, b) => a.createdAtSort - b.createdAtSort)
                  .map((message) => {
                    const isOutgoing = message.direction === 'out';

                    return (
                      <div
                        key={message.id}
                        className={cn('flex', isOutgoing ? 'justify-end' : 'justify-start')}
                      >
                        <div
                          className={cn(
                            'max-w-[85%] rounded-2xl border px-3 py-2',
                            isOutgoing ? 'bg-slate-900 text-white border-slate-900' : 'bg-white',
                          )}
                        >
                          <div
                            className={cn(
                              'mb-1 flex items-center gap-2 text-[11px]',
                              isOutgoing ? 'text-slate-200' : 'text-muted-foreground',
                            )}
                          >
                            {channelBadge(message.channel)}
                            <span>{message.author}</span>
                            <span>·</span>
                            <span>{message.createdAtLabel}</span>
                          </div>
                          <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.text}</p>
                        </div>
                      </div>
                    );
                  })}
              </div>

              <div className="border-t px-4 py-4 space-y-3">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_220px]">
                  <Textarea
                    value={activeDraft}
                    onChange={(event) =>
                      setDraftsByThreadId((prev) => ({ ...prev, [activeThread.id]: event.target.value }))
                    }
                    placeholder="Ответ клиенту (единое окно для всех каналов)..."
                    className="min-h-[96px] resize-y"
                    disabled={sendingThreadId === activeThread.id}
                  />
                  <div className="space-y-2">
                    <label className="block text-xs text-muted-foreground">Канал ответа</label>
                    <select
                      value={activeReplyChannel}
                      onChange={(event) =>
                        setReplyChannelByThreadId((prev) => ({
                          ...prev,
                          [activeThread.id]: event.target.value as InboxChannel,
                        }))
                      }
                      className={cn(selectClassName, 'w-full')}
                      disabled={sendingThreadId === activeThread.id}
                    >
                      {activeReplyChannels.map((channel) => {
                        const handle = activeThread.client.channels.find((item) => item.channel === channel)?.handle;
                        return (
                          <option key={`${activeThread.id}-${channel}`} value={channel}>
                            {CHANNEL_META[channel].label}{handle ? ` (${handle})` : ''}
                          </option>
                        );
                      })}
                    </select>

                    <div className="rounded-md border bg-slate-50 px-3 py-2 text-xs text-slate-600">
                      Ответ отправляется из одного окна, а сообщение добавляется в историю клиента.
                    </div>
                  </div>
                </div>

                {sendError && (
                  <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                    {sendError}
                  </div>
                )}

                <div className="flex items-center justify-between gap-3">
                  <div className="text-xs text-muted-foreground">
                    Выбранный канал: <span className="font-medium">{CHANNEL_META[activeReplyChannel].label}</span>
                  </div>
                  <Button
                    type="button"
                    onClick={() => { void handleSendReply(); }}
                    disabled={!activeDraft.trim() || sendingThreadId === activeThread.id}
                  >
                    {sendingThreadId === activeThread.id ? 'Отправка…' : 'Отправить'}
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex min-h-[720px] items-center justify-center p-6 text-center text-sm text-muted-foreground">
              Нет выбранного диалога.
            </div>
          )}
        </div>

        <div className="rounded-xl border bg-white">
          {activeThread ? (
            <div className="space-y-4 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-base font-semibold">Карточка клиента</h3>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Вся история по каналам хранится в карточке клиента
                  </p>
                </div>
                {activeThread.client.id > 0 ? (
                  <Button asChild type="button" size="sm" variant="outline">
                    <Link href={`/contact/${activeThread.client.id}`}>Открыть</Link>
                  </Button>
                ) : (
                  <Button type="button" size="sm" variant="outline" disabled>
                    Нет карточки
                  </Button>
                )}
              </div>

              <div className="rounded-lg border p-3">
                <div className="text-sm font-medium">{activeThread.client.name}</div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {activeThread.client.company || 'Без компании'} · Менеджер: {activeThread.client.manager}
                </div>
                <div className="mt-3 space-y-1 text-xs">
                  {activeThread.client.phone && (
                    <div>Телефон: {activeThread.client.phone}</div>
                  )}
                  {activeThread.client.email && (
                    <div>Email: {activeThread.client.email}</div>
                  )}
                  <div>ID клиента: {activeThread.client.id > 0 ? activeThread.client.id : 'не привязан'}</div>
                </div>
              </div>

              <div>
                <div className="text-xs font-medium text-slate-700">Каналы клиента</div>
                <div className="mt-2 space-y-2">
                  {activeThread.client.channels.map((item) => (
                    <div
                      key={`${activeThread.client.id}-${item.channel}-${item.handle}`}
                      className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-xs"
                    >
                      <div className="flex items-center gap-2">
                        {channelBadge(item.channel)}
                        <span>{CHANNEL_META[item.channel].label}</span>
                      </div>
                      <span className="truncate text-muted-foreground">{item.handle}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="text-xs font-medium text-slate-700">Теги</div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {activeThread.client.tags.map((tag) => (
                    <Badge key={`${activeThread.client.id}-${tag}`} variant="outline" className="text-[11px]">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </div>

              {activeThread.client.notes && (
                <div className="rounded-lg border bg-slate-50 p-3 text-xs text-slate-700">
                  {activeThread.client.notes}
                </div>
              )}

              <div>
                <div className="text-xs font-medium text-slate-700">История взаимодействий (последние)</div>
                <div className="mt-2 space-y-2">
                  {activeClientTimeline.map((entry) => (
                    <div key={`${activeThread.id}-${entry.id}`} className="rounded-md border p-2">
                      <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                        {channelBadge(entry.channel)}
                        <span>{entry.createdAtLabel}</span>
                        <span>·</span>
                        <span>{entry.direction === 'out' ? 'Ответ менеджера' : 'Сообщение клиента'}</span>
                      </div>
                      <div className="mt-1 line-clamp-2 text-xs text-slate-700">{entry.text}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="p-4 text-sm text-muted-foreground">Выберите диалог, чтобы открыть карточку клиента.</div>
          )}
        </div>
      </div>
    </div>
  );
}
