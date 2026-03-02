"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Check,
  Search,
  UserCheck,
  ListChecks,
  GitBranch,
  FileText,
  TrendingUp,
  Calendar,
  MessageSquare,
  CreditCard,
  Star,
} from "lucide-react";
import { motion, type Variants } from "framer-motion";
import { clientApi } from "@/lib/api/client";
import type { GenerationEventSummary, GenerationEventType } from "@/lib/types";

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: {
      delay: i * 0.3,
      duration: 0.4,
      ease: "easeOut",
    },
  }),
};

const EVENT_LABELS: Record<GenerationEventType, string> = {
  post: "Пост",
  article_write: "Статья: написать",
  article_evaluate: "Статья: оценить",
  channel_analysis: "Аналитика канала",
  website_analysis: "Аналитика сайта",
  weekly_collection: "Подборка",
  seo_group: "SEO группы",
  wordstat_query: "Wordstat",
  google_query: "Google запросы",
  product: "Продукт",
  product_map: "Карта продуктов",
  book_search: "Книги",
  semantic_phrases: "SEO фразы",
};

const STEPS = [
  {
    step: 1,
    title: "AI-аналитика",
    icon: Search,
    color: "indigo",
    bg: "bg-indigo-50",
    href: "/analytics",
    text: "Анализ сайта, Telegram-канала (своего или конкурента), одного канала или подборки. ИИ собирает метрики, выявляет слабые и сильные зоны.",
    events: ["channel_analysis", "website_analysis", "weekly_collection"] as GenerationEventType[],
  },
  {
    step: 2,
    title: "Коррекция позиционирования",
    icon: UserCheck,
    color: "amber",
    bg: "bg-amber-50",
    href: "/settings",
    text: "ИИ помогает переформулировать сильное позиционирование, выгоды, болевые зоны и портреты целевой аудитории.",
    events: ["book_search"] as GenerationEventType[],
  },
  {
    step: 3,
    title: "SEO-ключи и кластеры",
    icon: ListChecks,
    color: "sky",
    bg: "bg-sky-50",
    href: "/seo",
    text: "Получение Wordstat-запросов с автоматической кластеризацией и ранжированием по приоритетам.",
    events: ["seo_group", "wordstat_query", "google_query"] as GenerationEventType[],
  },
  {
    step: 4,
    title: "Продуктовая линейка + Mind Map",
    icon: GitBranch,
    color: "purple",
    bg: "bg-purple-50",
    href: "/mindmap",
    text: "ИИ строит продуктовую линейку из Wordstat-запросов и контекста проекта. Отображает её как ментальную карту.",
    events: ["product", "product_map"] as GenerationEventType[],
  },
  {
    step: 5,
    title: "Генерация контента",
    icon: FileText,
    color: "green",
    bg: "bg-green-50",
    href: "/posts",
    text: "ИИ создаёт SEO-статьи, посты, сценарии видео и карусели с изображениями — по кластерам и ЦА.",
    events: ["post", "article_write", "article_evaluate"] as GenerationEventType[],
  },
  {
    step: 6,
    title: "Аналитика и рост",
    icon: TrendingUp,
    color: "emerald",
    bg: "bg-emerald-50",
    href: "/dashboard",
    text: "Мониторинг охватов, трафика, динамики постов, вовлечённости и точек монетизации.",
  },
];

const CLIENT_MANAGEMENT_BLOCKS = [
  {
    title: "Планирование встреч",
    icon: Calendar,
    color: "rose",
    bg: "bg-rose-50",
    href: "/clients?tab=schedule&scheduleTab=calendar",
    text: "Календарь встреч, задачи и контроль ближайших касаний с клиентами.",
  },
  {
    title: "Цепочка сообщений",
    icon: MessageSquare,
    color: "orange",
    bg: "bg-orange-50",
    href: "/clients?tab=welcome-chain",
    text: "Сценарии сообщений и чат-цепочки для прогрева, сопровождения и возврата клиентов.",
  },
  {
    title: "Прием оплат",
    icon: CreditCard,
    color: "teal",
    bg: "bg-teal-50",
    href: "/clients?tab=deals",
    text: "Настройка и контроль платежей, чтобы быстрее запускать оплату в работу.",
  },
  {
    title: "Сбор обратной связи",
    icon: Star,
    color: "cyan",
    bg: "bg-cyan-50",
    href: "/clients?tab=service-level",
    text: "Фиксация обратной связи после встреч и задач для повышения уровня сервиса.",
  },
];

export default function LoggedInLanding() {
  const router = useRouter();
  const [eventSummary, setEventSummary] = useState<GenerationEventSummary | null>(null);

  useEffect(() => {
    let active = true;
    clientApi
      .generationEventsSummary()
      .then((data) => {
        if (active) {
          setEventSummary(data);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  const eventCounts = useMemo<Partial<Record<GenerationEventType, number>>>(
    () => eventSummary?.counts ?? {},
    [eventSummary]
  );

  const renderEventCounts = (events?: GenerationEventType[]) => {
    if (!eventSummary || !events?.length) {
      return null;
    }

    return (
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        {events.map((eventType) => {
          const count = eventCounts[eventType] ?? 0;
          const hasValue = count > 0;
          return (
            <span key={eventType} className="inline-flex items-center gap-1">
              <span>
                {EVENT_LABELS[eventType]}: {count}
              </span>
              <Check className={`h-3 w-3 ${hasValue ? "text-emerald-500" : "text-slate-300"}`} />
            </span>
          );
        })}
      </div>
    );
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-10 text-center"
      >
        <h1 className="text-3xl font-extrabold text-slate-900">
          Добро пожаловать в управляемый маркетинг
        </h1>
        <p className="mt-3 text-slate-600 text-lg">
          Платформа теперь объединяет две ветки: маркетинг/SEO и управление клиентами.
        </p>
      </motion.div>

      <div className="grid gap-8 lg:grid-cols-[0.95fr_1.35fr]">
        <div>
          <div className="mb-4 flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-slate-500" />
            <h2 className="text-lg font-semibold text-slate-900">Управление клиентами (CRM)</h2>
          </div>
          <div className="space-y-4">
            {CLIENT_MANAGEMENT_BLOCKS.map((block, i) => {
              const Icon = block.icon;
              return (
                <motion.div
                  key={block.title}
                  custom={i}
                  initial="hidden"
                  animate="visible"
                  variants={fadeUp}
                >
                  <motion.div
                    onClick={() => router.push(block.href)}
                    whileHover={{
                      scale: 1.015,
                      transition: { duration: 0.15 },
                    }}
                    whileTap={{
                      scale: 0.98,
                      transition: { duration: 0.1 },
                    }}
                    className="rounded-2xl border p-5 bg-white shadow-sm cursor-pointer select-none"
                  >
                    <div className="flex items-start gap-4">
                      <div className={`rounded-xl ${block.bg} p-3`}>
                        <Icon className={`h-5 w-5 text-${block.color}-600`} />
                      </div>
                      <div>
                        <h3 className="text-base font-bold text-slate-900">
                          {block.title}
                        </h3>
                        <p className="mt-1 text-slate-600 text-sm leading-relaxed">
                          {block.text}
                        </p>
                      </div>
                    </div>
                  </motion.div>
                </motion.div>
              );
            })}
          </div>
        </div>

        <div>
          <div className="mb-4 flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-slate-500" />
            <h2 className="text-lg font-semibold text-slate-900">Маркетинг и SEO</h2>
          </div>
          <div className="space-y-6">
            {STEPS.map((block, i) => {
              const Icon = block.icon;
              return (
                <motion.div
                  key={block.step}
                  custom={i + CLIENT_MANAGEMENT_BLOCKS.length}
                  initial="hidden"
                  animate="visible"
                  variants={fadeUp}
                >
                  <motion.div
                    onClick={() => router.push(block.href)}
                    whileHover={{
                      scale: 1.015,
                      transition: { duration: 0.15 },
                    }}
                    whileTap={{
                      scale: 0.98,
                      transition: { duration: 0.1 },
                    }}
                    className="rounded-2xl border p-6 bg-white shadow-sm cursor-pointer select-none"
                  >
                    <div className="flex items-start gap-4">
                      <div className={`rounded-xl ${block.bg} p-3`}>
                        <Icon className={`h-6 w-6 text-${block.color}-600`} />
                      </div>
                      <div>
                        <div
                          className={`text-sm font-semibold text-${block.color}-600`}
                        >
                          Шаг {block.step}
                        </div>
                        <h3 className="mt-1 text-xl font-bold text-slate-900">
                          {block.title}
                        </h3>
                        <p className="mt-2 text-slate-600 text-sm leading-relaxed">
                          {block.text}
                        </p>
                        {renderEventCounts(block.events)}
                      </div>
                    </div>
                  </motion.div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
