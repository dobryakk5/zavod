import type { ReactNode } from "react";
import Link from "next/link";
import {
  ArrowRight,
  BarChart2,
  BookOpen,
  Bot,
  Brain,
  Boxes,
  CalendarDays,
  CheckCircle2,
  CreditCard,
  FileText,
  Route,
  Settings,
  Sparkles,
} from "lucide-react";
import LandingFooter from "../footer";

type FeatureRoute = {
  label: string;
  route: string;
  href?: string;
  note?: string;
};

type FeatureGroup = {
  title: string;
  subtitle: string;
  icon: ReactNode;
  what: string[];
  how: string[];
  routes: FeatureRoute[];
  primaryCta: { label: string; href: string };
};

type QuickLink = {
  title: string;
  desc: string;
  route: string;
  href: string;
};

type TemplateRoute = {
  title: string;
  route: string;
  note: string;
  openFrom: { label: string; href: string };
};

const featureGroups: FeatureGroup[] = [
  {
    title: "CRM и работа с клиентами",
    subtitle: "Единое место для сопровождения клиента: встречи, оплаты, воронка, карточка контакта и сервисные действия.",
    icon: <CalendarDays className="h-5 w-5" />,
    what: [
      "вести клиентов и карточки контактов в одном разделе",
      "управлять встречами, оплатами и задачами без таблиц",
      "контролировать воронку продаж по CRM-этапам",
    ],
    how: [
      "Откройте CRM (`/clients`) и выберите нужную вкладку",
      "Перейдите в карточку контакта для детальной работы",
      "Фиксируйте встречи, оплаты и заметки в едином процессе",
    ],
    routes: [
      { label: "CRM", route: "/clients", href: "/clients" },
      { label: "Расписание", route: "/schedule", href: "/schedule" },
      { label: "Карточка контакта", route: "/contact/[id]", note: "Открывается из CRM" },
      { label: "Встреча", route: "/meet/[id]", note: "Открывается из карточки контакта" },
    ],
    primaryCta: { label: "Открыть CRM", href: "/clients" },
  },
  {
    title: "Платежи и клиентский портал",
    subtitle: "Публичная страница клиента для записи, оплаты, цифровой выдачи и повторных покупок.",
    icon: <CreditCard className="h-5 w-5" />,
    what: [
      "отправлять клиента на оплату и видеть статус в системе",
      "давать self-service запись на встречи",
      "выдавать материалы после оплаты и показывать историю покупок",
    ],
    how: [
      "Настройте продукт и оплату в системе",
      "Подготовьте публичную страницу клиента и включите нужные блоки",
      "Отправьте ссылку клиенту — дальше часть действий он делает сам",
    ],
    routes: [
      { label: "Настройки оплаты", route: "/settings", href: "/settings" },
      { label: "Платёжный маршрут", route: "/pay", href: "/pay" },
      { label: "Публичная страница", route: "/c/[client_id]", note: "Шаблон маршрута" },
      { label: "Редактор публичной страницы", route: "/c/[client_id]/edit", note: "Шаблон маршрута" },
    ],
    primaryCta: { label: "Открыть настройки", href: "/settings" },
  },
  {
    title: "ChatBot и CRM-автоматизации",
    subtitle: "Сценарии сообщений и автозапуск после событий CRM: оплата, перенос и отмена встреч.",
    icon: <Bot className="h-5 w-5" />,
    what: [
      "собирать цепочки сообщений в визуальном редакторе",
      "автоматически запускать сценарии после CRM-событий",
      "уменьшать ручную переписку после оплат и переносов",
    ],
    how: [
      "Откройте CRM → ChatBot",
      "Настройте цепочки (например, «После оплаты» и «Перенос встречи»)",
      "Проверьте цепочку и переведите её в статус active",
    ],
    routes: [
      { label: "CRM / ChatBot", route: "/clients", href: "/clients" },
      { label: "Редактор цепочки", route: "/clients/chatbot/[chainId]", note: "Открывается из вкладки ChatBot" },
    ],
    primaryCta: { label: "Открыть CRM", href: "/clients" },
  },
  {
    title: "Аналитика и исследования",
    subtitle: "Подготовка данных для решений: каналы, сайт, конкуренты, гипотезы роста.",
    icon: <BarChart2 className="h-5 w-5" />,
    what: [
      "анализировать каналы и сайт",
      "сравнивать конкурентов и находить рабочие темы",
      "собирать основу для маркетинговой стратегии",
    ],
    how: [
      "Заполните базовые настройки проекта и ниши",
      "Откройте аналитику и выберите источник данных",
      "Используйте выводы для SEO и контент-плана",
    ],
    routes: [
      { label: "Аналитика", route: "/analytics", href: "/analytics" },
      { label: "TGStat", route: "/analytics/tgstat", href: "/analytics/tgstat" },
      { label: "Анализ сайта", route: "/analytics/website/[scanId]/list", note: "Шаблон маршрута" },
    ],
    primaryCta: { label: "Открыть аналитику", href: "/analytics" },
  },
  {
    title: "SEO и контент-производство",
    subtitle: "От темы и семантики до постов, статей и расписания публикаций.",
    icon: <FileText className="h-5 w-5" />,
    what: [
      "собирать темы и кластеры для контента",
      "делать посты, статьи и контент-план",
      "поддерживать регулярный выпуск материалов",
    ],
    how: [
      "Соберите темы в SEO и аналитике",
      "Используйте шаблоны/темы и создайте материалы",
      "Поставьте публикации в расписание",
    ],
    routes: [
      { label: "SEO", route: "/seo", href: "/seo" },
      { label: "Посты", route: "/posts", href: "/posts" },
      { label: "Статьи", route: "/articles", href: "/articles" },
      { label: "Шаблоны", route: "/templates", href: "/templates" },
      { label: "Темы", route: "/topics", href: "/topics" },
    ],
    primaryCta: { label: "Открыть SEO", href: "/seo" },
  },
  {
    title: "Продукты и воронка продаж",
    subtitle: "Упаковка продуктовой линейки, product map и опора для продаж/маркетинга.",
    icon: <Boxes className="h-5 w-5" />,
    what: [
      "вести продукты и типы продуктов",
      "собирать продуктовую карту (mind map)",
      "связывать продукт с контентом и CRM-процессами",
    ],
    how: [
      "Создайте продукт и заполните структуру предложения",
      "Соберите карту продукта и связей",
      "Используйте данные в маркетинге и продажах",
    ],
    routes: [
      { label: "Продукты", route: "/products", href: "/products" },
      { label: "Карточка продукта", route: "/product/[id]", note: "Открывается из списка продуктов" },
      { label: "Product map", route: "/map/[mapId]", note: "Открывается из раздела продуктов" },
    ],
    primaryCta: { label: "Открыть продукты", href: "/products" },
  },
  {
    title: "Настройки и интеграции",
    subtitle: "Фундамент проекта: бренд, ниша, соцаккаунты, оплата, часовой пояс и сервисные настройки.",
    icon: <Settings className="h-5 w-5" />,
    what: [
      "заполнить контекст проекта для AI и маркетинга",
      "подключить каналы и соцаккаунты",
      "настроить оплату и базовые параметры системы",
    ],
    how: [
      "Откройте страницу настроек",
      "Заполните бренд, нишу, продукт и ЦА",
      "Подключите соцаккаунты и проверьте вкладку оплаты",
    ],
    routes: [
      { label: "Настройки", route: "/settings", href: "/settings" },
      { label: "Стартовый экран", route: "/welcome", href: "/welcome" },
      { label: "VK callback", route: "/auth/vk/callback", href: "/auth/vk/callback" },
    ],
    primaryCta: { label: "Открыть настройки", href: "/settings" },
  },
  {
    title: "База знаний и AI-ответы",
    subtitle: "Документы команды, публичные ссылки и быстрые ответы по накопленным материалам.",
    icon: <BookOpen className="h-5 w-5" />,
    what: [
      "хранить инструкции и материалы проекта",
      "делиться документами с клиентами и командой",
      "искать ответы через чат по базе знаний",
    ],
    how: [
      "Создайте документы и структуру базы знаний",
      "Настройте доступ и публичные ссылки",
      "Используйте AI-чат по KB для быстрых ответов",
    ],
    routes: [
      { label: "Настройки (вкладка KB)", route: "/settings", href: "/settings" },
      { label: "Документ KB", route: "/kb/[documentId]", note: "Открывается из списка документов" },
      { label: "Публичная ссылка KB", route: "/kb/share/[token]", note: "Шаблон публичного доступа" },
    ],
    primaryCta: { label: "Открыть настройки", href: "/settings" },
  },
];

const quickLinks: QuickLink[] = [
  { title: "CRM", desc: "Клиенты, воронка, платежи, ChatBot", route: "/clients", href: "/clients" },
  { title: "Настройки", desc: "Проект, интеграции, оплата", route: "/settings", href: "/settings" },
  { title: "Аналитика", desc: "Каналы, сайт, исследования", route: "/analytics", href: "/analytics" },
  { title: "SEO", desc: "Семантика, кластеры, конкуренты", route: "/seo", href: "/seo" },
  { title: "Посты", desc: "Контент и публикации", route: "/posts", href: "/posts" },
  { title: "Статьи", desc: "SEO-статьи и редактура", route: "/articles", href: "/articles" },
  { title: "Продукты", desc: "Линейка продуктов и продажи", route: "/products", href: "/products" },
  { title: "Расписание", desc: "Календарь и загрузка команды", route: "/schedule", href: "/schedule" },
  { title: "Шаблоны", desc: "Шаблоны контента", route: "/templates", href: "/templates" },
  { title: "Темы", desc: "Темы и заготовки", route: "/topics", href: "/topics" },
  { title: "Оплата", desc: "Служебный маршрут оплаты", route: "/pay", href: "/pay" },
  { title: "Welcome", desc: "Стартовый экран и навигация", route: "/welcome", href: "/welcome" },
];

const templateRoutes: TemplateRoute[] = [
  {
    title: "Публичная страница клиента",
    route: "/c/[client_id]",
    note: "Нужен ID клиента. Обычно открывается из CRM или настроек клиента.",
    openFrom: { label: "Открыть CRM", href: "/clients" },
  },
  {
    title: "Редактор публичной страницы",
    route: "/c/[client_id]/edit",
    note: "Нужен ID клиента. Используется для настройки блоков страницы клиента.",
    openFrom: { label: "Открыть настройки", href: "/settings" },
  },
  {
    title: "Карточка контакта",
    route: "/contact/[id]",
    note: "Открывается из списка клиентов в CRM.",
    openFrom: { label: "Открыть CRM", href: "/clients" },
  },
  {
    title: "Редактор встречи",
    route: "/meet/[id]",
    note: "Открывается из карточки контакта или расписания.",
    openFrom: { label: "Открыть расписание", href: "/schedule" },
  },
  {
    title: "Редактор цепочки ChatBot",
    route: "/clients/chatbot/[chainId]",
    note: "Открывается из вкладки ChatBot внутри CRM.",
    openFrom: { label: "Открыть CRM", href: "/clients" },
  },
  {
    title: "Карточка продукта",
    route: "/product/[id]",
    note: "Открывается из списка продуктов.",
    openFrom: { label: "Открыть продукты", href: "/products" },
  },
];

export default function FeaturesPage() {
  return (
    <div className="min-h-screen bg-[#fafaf8] text-gray-900">
      <header className="sticky top-0 z-30 border-b border-black/5 bg-white/90 backdrop-blur">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-4">
          <Link href="/" className="font-semibold tracking-tight text-gray-900">
            Fibonatty
          </Link>
          <nav className="hidden items-center gap-5 md:flex">
            <Link href="/" className="text-sm text-gray-700 hover:underline">
              Платформа
            </Link>
            <a href="#groups" className="text-sm text-gray-700 hover:underline">
              Возможности
            </a>
            <a href="#routes" className="text-sm text-gray-700 hover:underline">
              Разделы продукта
            </a>
            <a href="#how" className="text-sm text-gray-700 hover:underline">
              Как начать
            </a>
            <Link
              href="/login"
              className="ml-2 inline-flex items-center rounded-md border border-gray-200 px-4 py-2 text-sm font-medium hover:shadow"
            >
              Войти
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl px-6 pb-20 pt-8">
        <section className="relative overflow-hidden rounded-3xl border border-gray-200 bg-white p-8 shadow-sm md:p-12">
          <div className="pointer-events-none absolute right-0 top-0 h-40 w-40 rounded-full bg-yellow-200/30 blur-3xl" />
          <div className="pointer-events-none absolute bottom-0 left-0 h-40 w-40 rounded-full bg-emerald-200/20 blur-3xl" />
          <div className="grid grid-cols-1 gap-10 lg:grid-cols-[1.15fr_0.85fr]">
            <div className="relative z-10">
              <div className="inline-flex items-center gap-2 rounded-full border border-yellow-200 bg-yellow-50 px-3 py-1 text-xs font-medium text-yellow-800">
                <Sparkles className="h-4 w-4" />
                Возможности системы для клиентов и команды
              </div>
              <h1 className="mt-4 text-3xl font-semibold leading-tight md:text-5xl">
                Одна платформа для маркетинга, CRM, оплат и автоматизаций
              </h1>
              <p className="mt-5 max-w-3xl text-base leading-7 text-gray-600 md:text-lg">
                Fibonatty помогает не просто “делать контент”, а выстроить рабочую систему: от анализа рынка и SEO до
                встреч, оплат, клиентского портала и сервисных сценариев после событий в CRM.
              </p>

              <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2">
                {[
                  "Видно, что делать сегодня: CRM, встречи, оплаты, воронка",
                  "Контент и SEO связаны с продуктами и продажами",
                  "Автосценарии уменьшают ручную переписку после оплаты",
                  "Клиент получает self-service: запись, оплата, доступ",
                ].map((item) => (
                  <div key={item} className="flex items-start gap-2 rounded-xl border border-gray-100 bg-gray-50 px-3 py-3">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                    <span className="text-sm text-gray-700">{item}</span>
                  </div>
                ))}
              </div>

              <div className="mt-8 flex flex-wrap gap-3">
                <Link
                  href="/login"
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-black px-5 py-3 text-sm font-semibold text-white"
                >
                  Войти в систему
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  href="/#pricing"
                  className="inline-flex items-center justify-center rounded-xl border border-gray-200 px-5 py-3 text-sm font-semibold text-gray-900"
                >
                  Посмотреть тарифы
                </Link>
              </div>
            </div>

            <div className="relative z-10 grid gap-4">
              <div className="rounded-2xl border border-gray-200 bg-gray-50 p-5">
                <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Для кого</div>
                <div className="mt-3 grid gap-2 text-sm text-gray-700">
                  <div>Эксперты и наставники</div>
                  <div>Предприниматели и продюсеры</div>
                  <div>Команды продаж и маркетинга</div>
                </div>
              </div>
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
                <div className="flex items-center gap-2 text-emerald-800">
                  <Brain className="h-4 w-4" />
                  <span className="text-sm font-semibold">Плюс для клиентов</span>
                </div>
                <p className="mt-2 text-sm leading-6 text-emerald-900">
                  Клиент видит понятный путь: записаться, оплатить, получить доступ и инструкции без “пинания” менеджера.
                </p>
              </div>
              <div className="rounded-2xl border border-yellow-200 bg-yellow-50 p-5">
                <div className="text-sm font-semibold text-yellow-900">Free-тариф для старта CRM</div>
                <p className="mt-2 text-sm leading-6 text-yellow-900/90">
                  Можно начать с работы по клиентам: встречи, оплаты и воронка. На landing отдельно показано, что входит и чего нет.
                </p>
                <Link href="/#pricing" className="mt-3 inline-flex text-sm font-medium text-yellow-900 underline">
                  Перейти к тарифам
                </Link>
              </div>
            </div>
          </div>
        </section>

        <section className="py-12">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <ValueCard
              title="Быстрее запуск"
              desc="Один интерфейс для настроек, аналитики, SEO и контент-производства вместо набора разрозненных сервисов."
            />
            <ValueCard
              title="Контроль клиентского пути"
              desc="CRM, встречи, оплаты и публичная страница клиента работают в одной системе и видны команде."
            />
            <ValueCard
              title="Меньше ручной рутины"
              desc="ChatBot и CRM-сценарии закрывают повторяющиеся сообщения после оплат и изменений в расписании."
            />
          </div>
        </section>

        <section id="groups" className="py-8">
          <div className="flex flex-col gap-2">
            <h2 className="text-2xl font-semibold md:text-3xl">Возможности по блокам</h2>
            <p className="max-w-3xl text-gray-600">
              Ниже — что система помогает сделать, как начать и где это находится в продукте. Это удобно и для продажи,
              и для онбординга команды.
            </p>
          </div>

          <div className="mt-8 grid grid-cols-1 gap-6 xl:grid-cols-2">
            {featureGroups.map((group) => (
              <FeatureGroupCard key={group.title} group={group} />
            ))}
          </div>
        </section>

        <section id="routes" className="py-16">
          <div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm md:p-8">
            <div className="flex items-start gap-3">
              <div className="rounded-xl bg-gray-100 p-2 text-gray-700">
                <Route className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-2xl font-semibold md:text-3xl">Быстрые переходы в продукт</h2>
                <p className="mt-2 max-w-3xl text-gray-600">
                  Ссылки на основные разделы, которые можно открыть сразу, и шаблоны маршрутов с ID для карточек клиента,
                  встреч, цепочек и публичных страниц.
                </p>
              </div>
            </div>

            <div className="mt-8">
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Можно открыть сразу</div>
              <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                {quickLinks.map((item) => (
                  <QuickLinkCard key={item.route} item={item} />
                ))}
              </div>
            </div>

            <div className="mt-10">
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Маршруты-шаблоны (нужен ID)</div>
              <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                {templateRoutes.map((item) => (
                  <TemplateRouteCard key={item.route} item={item} />
                ))}
              </div>
            </div>
          </div>
        </section>

        <section id="how" className="pb-12">
          <div className="rounded-3xl border border-gray-200 bg-gradient-to-br from-white to-gray-50 p-6 md:p-8">
            <div className="flex items-start gap-3">
              <div className="rounded-xl bg-emerald-100 p-2 text-emerald-700">
                <CheckCircle2 className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-2xl font-semibold md:text-3xl">Как начать за 1 день</h2>
                <p className="mt-2 max-w-3xl text-gray-600">
                  Минимальный сценарий, чтобы быстро получить пользу и показать клиенту работающий процесс.
                </p>
              </div>
            </div>

            <div className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-4">
              {[
                ["1", "Настройки", "Заполните бренд, нишу, продукт и подключите базовые интеграции в /settings."],
                ["2", "CRM", "Добавьте клиентов, встречи и оплаты в /clients — это база для ежедневной работы."],
                ["3", "Публичная страница", "Подготовьте клиентскую страницу и оплату, чтобы клиент мог действовать сам."],
                ["4", "Автоматизации", "Включите цепочки после оплаты и переносов, чтобы сократить ручные сообщения."],
              ].map(([num, title, desc]) => (
                <div key={title} className="rounded-2xl border border-gray-200 bg-white p-4">
                  <div className="text-sm font-semibold text-emerald-700">Шаг {num}</div>
                  <div className="mt-1 font-semibold text-gray-900">{title}</div>
                  <p className="mt-2 text-sm leading-6 text-gray-600">{desc}</p>
                </div>
              ))}
            </div>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/settings" className="inline-flex items-center gap-2 rounded-xl bg-black px-5 py-3 text-sm font-semibold text-white">
                Начать с настроек
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link href="/clients" className="inline-flex items-center rounded-xl border border-gray-200 px-5 py-3 text-sm font-semibold text-gray-900">
                Открыть CRM
              </Link>
            </div>
          </div>
        </section>
      </main>

      <LandingFooter />
    </div>
  );
}

function FeatureGroupCard({ group }: { group: FeatureGroup }) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="rounded-xl bg-yellow-100 p-2 text-yellow-700">{group.icon}</div>
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{group.title}</h3>
          <p className="mt-1 text-sm leading-6 text-gray-600">{group.subtitle}</p>
        </div>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Что помогает сделать</div>
          <ul className="mt-3 space-y-2">
            {group.what.map((item) => (
              <li key={item} className="flex items-start gap-2 text-sm text-gray-700">
                <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-yellow-500" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Как начать</div>
          <ol className="mt-3 space-y-2">
            {group.how.map((step, idx) => (
              <li key={step} className="flex items-start gap-2 text-sm text-gray-700">
                <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-semibold text-gray-700">
                  {idx + 1}
                </span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <div className="mt-5">
        <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Где это в системе</div>
        <div className="mt-3 flex flex-wrap gap-2">
          {group.routes.map((route) => (
            <RouteChip key={`${group.title}-${route.route}-${route.label}`} route={route} />
          ))}
        </div>
      </div>

      <div className="mt-6 flex items-center justify-between gap-4 rounded-xl border border-gray-100 bg-gray-50 px-4 py-3">
        <div className="flex items-center gap-2 text-sm text-gray-700">
          <Sparkles className="h-4 w-4 text-yellow-600" />
          <span>Можно начать с базового сценария и масштабировать позже</span>
        </div>
        <Link
          href={group.primaryCta.href}
          className="inline-flex items-center gap-1 text-sm font-semibold text-gray-900 hover:underline"
        >
          {group.primaryCta.label}
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </section>
  );
}

function RouteChip({ route }: { route: FeatureRoute }) {
  if (route.href) {
    return (
      <Link
        href={route.href}
        className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-800 hover:bg-gray-50"
        title={route.label}
      >
        <span>{route.label}</span>
        <code className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-700">{route.route}</code>
      </Link>
    );
  }

  return (
    <span
      className="inline-flex items-center gap-2 rounded-full border border-dashed border-gray-300 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-700"
      title={route.note || route.label}
    >
      <span>{route.label}</span>
      <code className="rounded bg-white px-1.5 py-0.5 text-[11px] text-gray-700">{route.route}</code>
    </span>
  );
}

function QuickLinkCard({ item }: { item: QuickLink }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
      <div className="text-sm font-semibold text-gray-900">{item.title}</div>
      <p className="mt-1 text-sm leading-6 text-gray-600">{item.desc}</p>
      <div className="mt-3 flex items-center justify-between gap-3">
        <code className="rounded bg-white px-2 py-1 text-xs text-gray-700">{item.route}</code>
        <Link href={item.href} className="inline-flex items-center gap-1 text-sm font-semibold text-gray-900 hover:underline">
          Открыть
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}

function TemplateRouteCard({ item }: { item: TemplateRoute }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-gray-900">
        <span>{item.title}</span>
        <span className="inline-flex items-center rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-600">
          шаблон
        </span>
      </div>
      <div className="mt-2">
        <code className="rounded bg-gray-100 px-2 py-1 text-xs text-gray-700">{item.route}</code>
      </div>
      <p className="mt-3 text-sm leading-6 text-gray-600">{item.note}</p>
      <div className="mt-3 flex items-center gap-2 text-sm">
        <span className="text-gray-500">Как открыть:</span>
        <Link href={item.openFrom.href} className="font-semibold text-gray-900 hover:underline">
          {item.openFrom.label}
        </Link>
      </div>
    </div>
  );
}

function ValueCard({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2 text-gray-900">
        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
        <div className="font-semibold">{title}</div>
      </div>
      <p className="mt-2 text-sm leading-6 text-gray-600">{desc}</p>
    </div>
  );
}
