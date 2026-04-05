'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  BarChart3,
  CalendarClock,
  FileSpreadsheet,
  Newspaper,
  Search,
  Users2,
} from 'lucide-react';
import { clientApi } from '@/lib/api/client';
import { crmContactsApi, crmDealsApi, crmEventsApi } from '@/lib/api/crm';
import type { ClientSummary, GenerationEventSummary, GenerationEventType } from '@/lib/types';

type OverviewCard = {
  label: string;
  value: string;
  note: string;
};

type SectionMetric = {
  label: string;
  value: string;
};

type SectionLink = {
  label: string;
  href: string;
};

type MarketingSection = {
  title: string;
  description: string;
  href: string;
  icon: typeof BarChart3;
  eyebrow: string;
  accentClass: string;
  iconClass: string;
  metrics: SectionMetric[];
  secondaryLinks: SectionLink[];
};

type CrmOverview = {
  contacts: number;
  upcomingEvents: number;
  deals: number;
};

const formatCount = (value: number | null | undefined) => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '...';
  }
  return new Intl.NumberFormat('ru-RU').format(value);
};

const getEventCount = (
  summary: GenerationEventSummary | null,
  eventTypes: GenerationEventType[],
) => eventTypes.reduce((total, eventType) => total + (summary?.counts?.[eventType] ?? 0), 0);

function buildOverviewCards(
  eventSummary: GenerationEventSummary | null,
  contentSummary: ClientSummary | null,
  crmOverview: CrmOverview | null,
): OverviewCard[] {
  const generatedItems = getEventCount(eventSummary, [
    'post',
    'article_write',
    'article_evaluate',
    'channel_analysis',
    'website_analysis',
    'weekly_collection',
    'seo_group',
    'wordstat_query',
    'google_query',
    'semantic_phrases',
  ]);

  return [
    {
      label: 'AI-запуски',
      value: formatCount(generatedItems),
      note: 'аналитика, SEO и контент',
    },
    {
      label: 'Опубликовано',
      value: formatCount(contentSummary?.posts_published),
      note: `${formatCount(contentSummary?.posts_scheduled)} запланировано`,
    },
    {
      label: 'Клиенты',
      value: formatCount(crmOverview?.contacts),
      note: `${formatCount(crmOverview?.deals)} сделок в CRM`,
    },
    {
      label: 'Ближайшие касания',
      value: formatCount(crmOverview?.upcomingEvents),
      note: 'встречи и follow-up в работе',
    },
  ];
}

function buildMarketingSections(
  eventSummary: GenerationEventSummary | null,
  contentSummary: ClientSummary | null,
  crmOverview: CrmOverview | null,
): MarketingSection[] {
  return [
    {
      title: 'Аналитика',
      description: 'Анализируйте каналы, сайты и подборки, чтобы быстро находить рабочие темы и точки роста.',
      href: '/analytics',
      icon: BarChart3,
      eyebrow: 'Исследование',
      accentClass: 'bg-blue-50',
      iconClass: 'text-blue-700',
      metrics: [
        { label: 'Запусков', value: formatCount(getEventCount(eventSummary, ['channel_analysis', 'website_analysis', 'weekly_collection'])) },
        { label: 'Сайт', value: formatCount(eventSummary?.counts?.website_analysis ?? null) },
        { label: 'Каналы', value: formatCount(eventSummary?.counts?.channel_analysis ?? null) },
      ],
      secondaryLinks: [
        { label: 'Website', href: '/analytics?tab=website' },
        { label: 'Подборка', href: '/analytics?tab=weekly' },
      ],
    },
    {
      title: 'SEO',
      description: 'Собирайте смыслы, Wordstat и конкурентные запросы, чтобы строить тему и спрос под контент.',
      href: '/seo',
      icon: Search,
      eyebrow: 'Трафик',
      accentClass: 'bg-amber-50',
      iconClass: 'text-amber-700',
      metrics: [
        { label: 'Группы', value: formatCount(eventSummary?.counts?.seo_group ?? null) },
        { label: 'Wordstat', value: formatCount(eventSummary?.counts?.wordstat_query ?? null) },
        { label: 'Google', value: formatCount(eventSummary?.counts?.google_query ?? null) },
      ],
      secondaryLinks: [
        { label: 'Смыслы', href: '/seo?tab=groups' },
        { label: 'Конкуренты', href: '/seo?tab=competitors' },
      ],
    },
    {
      title: 'Контент / Посты',
      description: 'Планируйте сетку, создавайте посты и управляйте расписанием публикаций из одного маршрута.',
      href: '/posts',
      icon: FileSpreadsheet,
      eyebrow: 'Контент-поток',
      accentClass: 'bg-emerald-50',
      iconClass: 'text-emerald-700',
      metrics: [
        { label: 'Постов', value: formatCount(contentSummary?.total_posts) },
        { label: 'Опубликовано', value: formatCount(contentSummary?.posts_published) },
        { label: 'AI-генераций', value: formatCount(eventSummary?.counts?.post ?? null) },
      ],
      secondaryLinks: [
        { label: 'Расписание', href: '/posts' },
        { label: 'Новый пост', href: '/posts/new' },
      ],
    },
    {
      title: 'Статьи',
      description: 'Пишите, оценивайте и дорабатывайте длинные материалы, не выпадая из маркетингового контура.',
      href: '/articles',
      icon: Newspaper,
      eyebrow: 'Long-form',
      accentClass: 'bg-violet-50',
      iconClass: 'text-violet-700',
      metrics: [
        { label: 'Написано', value: formatCount(eventSummary?.counts?.article_write ?? null) },
        { label: 'Оценено', value: formatCount(eventSummary?.counts?.article_evaluate ?? null) },
        { label: 'Готово к публикации', value: formatCount(contentSummary?.posts_published) },
      ],
      secondaryLinks: [
        { label: 'Открыть статьи', href: '/articles' },
        { label: 'Из SEO-избранного', href: '/seo/favorites' },
      ],
    },
    {
      title: 'Клиенты',
      description: 'Держите в одном месте CRM, сделки, встречи, inbox и chatbot-цепочки, связанные с маркетингом.',
      href: '/clients',
      icon: Users2,
      eyebrow: 'CRM',
      accentClass: 'bg-rose-50',
      iconClass: 'text-rose-700',
      metrics: [
        { label: 'Контактов', value: formatCount(crmOverview?.contacts) },
        { label: 'Сделок', value: formatCount(crmOverview?.deals) },
        { label: 'Встреч впереди', value: formatCount(crmOverview?.upcomingEvents) },
      ],
      secondaryLinks: [
        { label: 'Календарь', href: '/clients/schedule' },
        { label: 'Сделки', href: '/clients/deals' },
      ],
    },
  ];
}

function OverviewMetricCard({ card }: { card: OverviewCard }) {
  return (
    <div className="rounded-xl border border-gray-100 bg-white p-5">
      <p className="mb-1 text-xs text-gray-500">{card.label}</p>
      <p className="text-2xl font-medium text-gray-900">{card.value}</p>
      <p className="mt-1 text-xs text-gray-400">{card.note}</p>
    </div>
  );
}

function SectionMetricPill({ metric }: { metric: SectionMetric }) {
  return (
    <div className="rounded-full bg-gray-50 px-2 py-1 text-[11px] text-gray-500">
      <span className="font-medium text-gray-700">{metric.value}</span> · {metric.label}
    </div>
  );
}

function MarketingRouteRow({ section }: { section: MarketingSection }) {
  const Icon = section.icon;

  return (
    <Link href={section.href} className="flex items-start gap-3 rounded-lg p-3 transition-colors hover:bg-gray-50">
      <div className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full ${section.accentClass}`}>
        <Icon className={`h-4 w-4 ${section.iconClass}`} />
      </div>
      <div className="min-w-0 flex-1">
        <h2 className="text-sm font-medium text-gray-900">{section.title}</h2>
        <p className="mt-1 text-xs leading-relaxed text-gray-400">{section.description}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {section.metrics.map((metric) => (
            <SectionMetricPill key={`${section.title}-${metric.label}`} metric={metric} />
          ))}
        </div>
      </div>
      <ArrowRight className="mt-1 h-4 w-4 flex-shrink-0 text-gray-300" />
    </Link>
  );
}

function QuickLinkCard({
  title,
  description,
  links,
  tone = 'neutral',
}: {
  title: string;
  description: string;
  links: SectionLink[];
  tone?: 'neutral' | 'accent';
}) {
  const toneClass = tone === 'accent'
    ? 'bg-emerald-50 border-emerald-100'
    : 'bg-white border-gray-100';

  return (
    <div className={`rounded-xl border p-5 ${toneClass}`}>
      <h2 className="mb-1 text-sm font-medium text-gray-900">{title}</h2>
      <p className="mb-4 text-xs leading-relaxed text-gray-500">{description}</p>
      <div className="space-y-2">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="flex items-center justify-between rounded-lg px-3 py-2 text-xs text-gray-600 transition-colors hover:bg-white/70 hover:text-gray-900"
          >
            {link.label}
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        ))}
      </div>
    </div>
  );
}

export default function MarketingPage() {
  const [eventSummary, setEventSummary] = useState<GenerationEventSummary | null>(null);
  const [contentSummary, setContentSummary] = useState<ClientSummary | null>(null);
  const [crmOverview, setCrmOverview] = useState<CrmOverview | null>(null);

  useEffect(() => {
    let active = true;

    const loadDashboard = async () => {
      const [eventSummaryResult, contentSummaryResult, contactsResult, eventsResult, dealsResult] = await Promise.allSettled([
        clientApi.generationEventsSummary(),
        clientApi.summary(),
        crmContactsApi.list(),
        crmEventsApi.list(),
        crmDealsApi.list(),
      ]);

      if (!active) {
        return;
      }

      if (eventSummaryResult.status === 'fulfilled') {
        setEventSummary(eventSummaryResult.value);
      }

      if (contentSummaryResult.status === 'fulfilled') {
        setContentSummary(contentSummaryResult.value);
      }

      if (
        contactsResult.status === 'fulfilled'
        && eventsResult.status === 'fulfilled'
        && dealsResult.status === 'fulfilled'
      ) {
        const now = Date.now();
        const upcomingEvents = eventsResult.value.filter((event) => {
          if (event.status !== 'scheduled') {
            return false;
          }
          const timestamp = new Date(event.start_time).getTime();
          return Number.isFinite(timestamp) && timestamp >= now;
        }).length;

        setCrmOverview({
          contacts: contactsResult.value.length,
          upcomingEvents,
          deals: dealsResult.value.length,
        });
      }
    };

    void loadDashboard();

    return () => {
      active = false;
    };
  }, []);

  const overviewCards = useMemo(
    () => buildOverviewCards(eventSummary, contentSummary, crmOverview),
    [contentSummary, crmOverview, eventSummary],
  );

  const sections = useMemo(
    () => buildMarketingSections(eventSummary, contentSummary, crmOverview),
    [contentSummary, crmOverview, eventSummary],
  );

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-medium text-gray-900">Маркетинг</h1>
        <p className="mt-1 text-sm text-gray-500">
          Сегодня единая точка входа в аналитику, SEO, контент, статьи и клиентские процессы.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {overviewCards.slice(0, 3).map((card) => (
          <OverviewMetricCard key={card.label} card={card} />
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3 rounded-xl border border-gray-100 bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-medium text-gray-900">Маркетинговые маршруты</h2>
              <p className="mt-1 text-xs text-gray-400">Все бывшие top-level разделы теперь собраны в одном списке.</p>
            </div>
            <Link href="/analytics" className="text-xs text-blue-600 hover:underline">
              открыть аналитику →
            </Link>
          </div>
          <div className="space-y-1">
            {sections.map((section) => (
              <MarketingRouteRow key={section.title} section={section} />
            ))}
          </div>
        </div>

        <div className="space-y-4 lg:col-span-2">
          <QuickLinkCard
            title="Быстрые переходы"
            description="Самые частые дочерние маршруты, которые раньше жили отдельными пунктами меню."
            links={[
              { label: 'Website', href: '/analytics?tab=website' },
              { label: 'Конкуренты', href: '/seo?tab=competitors' },
              { label: 'Новый пост', href: '/posts/new' },
              { label: 'Открыть статьи', href: '/articles' },
              { label: 'Календарь', href: '/clients/schedule' },
            ]}
          />

          <QuickLinkCard
            title="Состояние контура"
            description="Session-логика и deep pages сохранены: изменена только оболочка и навигационная композиция."
            tone="accent"
            links={[
              { label: `AI-запуски: ${overviewCards[0]?.value ?? '...'}`, href: '/welcome' },
              { label: `Публикации: ${overviewCards[1]?.value ?? '...'}`, href: '/posts' },
              { label: `Клиенты: ${overviewCards[2]?.value ?? '...'}`, href: '/clients' },
              { label: `Касания: ${overviewCards[3]?.value ?? '...'}`, href: '/clients/schedule' },
            ]}
          />

          <div className="rounded-xl border border-gray-100 bg-white p-5">
            <div className="mb-3 flex items-center gap-2">
              <CalendarClock className="h-4 w-4 text-gray-500" />
              <h2 className="text-sm font-medium text-gray-900">Что изменилось</h2>
            </div>
            <div className="space-y-2 text-xs leading-relaxed text-gray-500">
              <p>Topbar и сетка теперь собраны по шаблонному dashboard-паттерну.</p>
              <p>Отдельные пункты `Аналитика`, `Посты`, `SEO`, `Статьи`, `Клиенты` убраны из верхнего меню.</p>
              <p>Все старые маршруты доступны из этого экрана и по прямым ссылкам.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
