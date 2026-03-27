import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowRight, CalendarDays, CheckCircle2, CreditCard, FolderKanban, LockKeyhole, Sparkles, Workflow } from "lucide-react";
import { Manrope, Merriweather } from "next/font/google";

const manrope = Manrope({
  subsets: ["latin", "cyrillic"],
  variable: "--font-manrope",
  weight: ["400", "500", "600", "700"],
});

const merriweather = Merriweather({
  subsets: ["latin", "cyrillic"],
  variable: "--font-merriweather",
  weight: ["400", "700"],
});

const highlights = [
  "Клиент видит задачи, инсайты и выполненные шаги между сессиями",
  "У специалиста вся история клиента в одном месте, а не в заметках и чатах",
  "Прогресс собирается в понятный трек, который трудно обесценить",
  "Оплаты, программы и сопровождение работают внутри одного процесса",
  "Клиент может сам записаться, перенести встречу и открыть нужные материалы",
  "Квизы, мероприятия и реферальная механика поддерживают рост и удержание",
];

const capabilityCards = [
  {
    title: "Карточка клиента",
    result: "Контекст не теряется между встречами",
    body:
      "Сессии, наблюдения, договоренности и повторяющиеся темы собираются в единой карточке. Перед встречей не нужно вручную восстанавливать историю клиента.",
    routes: [
      "Меню / Клиенты",
      "Меню / Клиенты / Открыть клиента",
      "Меню / Клиенты / Открыть клиента / Встречи",
    ],
  },
  {
    title: "Личный кабинет клиента",
    result: "Клиент остается в процессе между сессиями",
    body:
      "Клиент видит свои задачи, материалы, события и продукты в своем пространстве. Это снижает выпадение из процесса и делает движение видимым для обеих сторон.",
    routes: [
      "Меню / Клиенты / Страница клиента",
      "Меню / Клиенты / Страница клиента / Задания",
      "Меню / Клиенты / Страница клиента / Мероприятия",
    ],
  },
  {
    title: "Трекер прогресса",
    result: "Работа подтверждается фактами, а не ощущением",
    body:
      "Завершенные шаги, инсайты и важные изменения собираются в понятную траекторию. Клиент видит не только следующую задачу, но и уже пройденный путь.",
    routes: [
      "Меню / Клиенты / Страница клиента / Задания",
      "Меню / Клиенты / Страница клиента / Мероприятия",
      "Меню / Клиенты / Страница клиента / Продукты",
    ],
  },
  {
    title: "Заметки и история сопровождения",
    result: "Ничего важного не теряется после сессии",
    body:
      "В карточке клиента сохраняются заметки, договоренности, платежный контекст и важные наблюдения. Это дает непрерывность работы даже при длинном сопровождении.",
    routes: [
      "Меню / Клиенты / Открыть клиента",
      "Меню / Клиенты / Открыть клиента / Встречи",
      "Меню / Клиенты",
    ],
  },
  {
    title: "Встречи и ритм работы",
    result: "Каждая встреча встроена в общий процесс",
    body:
      "Расписание, события и подготовка к следующей сессии живут в системе, а не в отдельных сообщениях. Это помогает держать стабильный ритм сопровождения.",
    routes: [
      "Меню / Клиенты / Расписание",
      "Меню / Клиенты",
      "Меню / Клиенты / Открыть клиента / Встречи",
    ],
  },
  {
    title: "Самостоятельная запись и перенос",
    result: "Меньше ручного согласования времени",
    body:
      "Клиент может выбрать свободный слот и, при необходимости, перенести встречу в своем пространстве. Это снимает лишние переписки и делает процесс удобнее для обеих сторон.",
    routes: [
      "Меню / Клиенты / Страница клиента",
      "Меню / Клиенты / Страница клиента / Мероприятия",
      "Меню / Клиенты / Расписание",
    ],
  },
  {
    title: "Продукты, программы и оплата",
    result: "Коммерческая часть не отрывается от клиентского пути",
    body:
      "Оплаты, продуктовая структура, доступ к материалам и следующий шаг клиента связаны в одной логике. После оплаты не приходится собирать процесс вручную.",
    routes: [
      "Меню / Продукты",
      "Меню / Клиенты / Страница клиента / Оплата",
      "Меню / Клиенты / Страница клиента / Продукты",
    ],
  },
  {
    title: "Покупки, курсы и доступы",
    result: "Клиент сразу получает то, что оплатил",
    body:
      "Список покупок, доступ к курсам, урокам и материалам доступны из клиентского пространства. Клиенту не нужно писать, чтобы найти ссылку или понять, что ему уже открыто.",
    routes: [
      "Меню / Клиенты / Страница клиента / Продукты",
      "Меню / Клиенты / Страница клиента / Продукты / Открыть продукт",
      "Меню / Клиенты / Страница клиента / Продукты / Курс",
    ],
  },
  {
    title: "Мероприятия и групповые форматы",
    result: "Можно сопровождать не только личные сессии",
    body:
      "Публичные события, групповые продукты и связанные с ними предложения показываются в клиентском пространстве. Это расширяет сценарии сопровождения и продажи внутри одной системы.",
    routes: [
      "Меню / Клиенты / Страница клиента / Мероприятия",
      "Меню / Клиенты / Страница клиента / Мероприятия / Открыть событие",
      "Меню / Продукты",
    ],
  },
  {
    title: "Квизы и предварительная диагностика",
    result: "Вход в работу становится понятнее",
    body:
      "Через квизы можно собирать вводную информацию, помогать клиенту лучше сформулировать запрос и подводить его к следующему шагу в работе.",
    routes: [
      "Меню / Настройки / Мои страницы / Квиз",
      "Публичная ссылка на квиз",
      "Меню / Клиенты / Страница клиента",
    ],
  },
  {
    title: "Реферальная программа",
    result: "Лояльные клиенты помогают расти практике",
    body:
      "Клиент может видеть свою реферальную ссылку и приглашения в своем пространстве. Это позволяет усиливать сарафанное привлечение без отдельного сервиса.",
    routes: [
      "Меню / Клиенты / Страница клиента",
      "Меню / Клиенты / Страница клиента / Оплата",
      "Меню / Настройки",
    ],
  },
  {
    title: "Автоматизации сопровождения",
    result: "Меньше ручных напоминаний и сервисной рутины",
    body:
      "Сценарии и цепочки помогают сопровождать клиента после оплат, событий и смены этапов. Система поддерживает процесс, пока вы работаете по сути.",
    routes: [
      "Меню / Клиенты / ChatBot",
      "Меню / Настройки",
      "Меню / Клиенты",
    ],
  },
];

const roleCards = [
  {
    title: "Что получает специалист",
    points: [
      "Подготовка к встрече за минуты, а не через ручной сбор контекста",
      "Единая картина по клиенту: история, задачи, прогресс, оплаты",
      "Больше времени на глубокую работу, меньше на администрирование",
    ],
  },
  {
    title: "Что получает клиент",
    points: [
      "Понятные шаги после каждой встречи",
      "Видимый трек движения, а не размытое ощущение «что-то происходит»",
      "Доступ к материалам, задачам и продуктам в одном месте",
    ],
  },
  {
    title: "Что получает процесс",
    points: [
      "Прозрачность между сессиями",
      "Меньше выпадения клиента из работы",
      "Меньше оснований обесценивать сопровождение, когда результат виден",
    ],
  },
];

const launchSteps = [
  {
    step: "1",
    title: "Завести клиента и встречу",
    body: "Начните с CRM: создайте клиента, добавьте ближайшую встречу и соберите стартовый контекст.",
    route: "Меню / Клиенты",
  },
  {
    step: "2",
    title: "Включить пространство клиента",
    body: "Дайте клиенту личный кабинет, где он видит задачи, события и свой путь между сессиями.",
    route: "Меню / Клиенты / Страница клиента",
  },
  {
    step: "3",
    title: "Зафиксировать действия после встречи",
    body: "Переведите договоренности в конкретные шаги и материалы, чтобы клиент не выпадал из процесса.",
    route: "Меню / Клиенты / Страница клиента / Задания",
  },
  {
    step: "4",
    title: "Подключить оплату и сопровождение",
    body: "Свяжите продукты, оплату и автоматические сценарии, чтобы процесс держался на системе, а не на ручных сообщениях.",
    route: "Меню / Продукты и Меню / Клиенты / Страница клиента / Оплата",
  },
];

const modules = [
  { name: "CRM и встречи", route: "Меню / Клиенты", note: "база ежедневной работы специалиста" },
  { name: "Публичный кабинет клиента", route: "Меню / Клиенты / Страница клиента", note: "пространство клиента между сессиями" },
  { name: "Задачи и события", route: "Меню / Клиенты / Страница клиента / Задания", note: "трек действий и движения" },
  { name: "Мероприятия", route: "Меню / Клиенты / Страница клиента / Мероприятия", note: "события и групповые форматы для клиента" },
  { name: "Покупки и доступы", route: "Меню / Клиенты / Страница клиента / Продукты", note: "все купленные продукты и материалы" },
  { name: "Квизы", route: "Меню / Настройки / Мои страницы / Квиз", note: "диагностика и сценарии входа в работу" },
  { name: "Продукты и программа", route: "Меню / Продукты", note: "структура предложения и этапов" },
  { name: "Оплата", route: "Меню / Клиенты / Страница клиента / Оплата", note: "платежный сценарий внутри процесса" },
  { name: "Автоматизации", route: "Меню / Клиенты / ChatBot", note: "сценарии сопровождения и сервисных касаний" },
];

export default function FeaturesPage() {
  return (
    <div className={`${manrope.variable} ${merriweather.variable} min-h-screen bg-[#f7f6f2] text-[#1a1c24]`}>
      <header className="sticky top-0 z-30 border-b border-black/5 bg-[rgba(247,246,242,0.88)] backdrop-blur">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2 text-sm text-[#707585]">
            <Link href="/" className="font-serif text-xl tracking-[0.02em] text-[#1a1c24]">
              Fibo<span className="text-[#5c52e0]">n</span>atty
            </Link>
            <span>/</span>
            <span className="font-medium text-[#1a1c24]">Возможности</span>
          </div>
          <Link
            href="/login"
            className="inline-flex items-center rounded-full bg-[#5c52e0] px-5 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-0.5"
          >
            Вход в систему
          </Link>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-7xl flex-col gap-20 px-6 pb-20 pt-8 md:pt-10">
        <section className="relative overflow-hidden rounded-[32px] border border-black/5 bg-white px-6 py-8 shadow-[0_24px_80px_rgba(0,0,0,0.06)] md:px-10 md:py-12">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(92,82,224,0.08),transparent_45%),radial-gradient(ellipse_at_bottom_left,rgba(47,143,122,0.08),transparent_40%)]" />
          <div className="relative grid gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-[#5c52e0]/15 bg-[#5c52e0]/[0.07] px-3 py-1 text-xs font-semibold uppercase tracking-[0.08em] text-[#5c52e0]">
                <Sparkles className="h-4 w-4" />
                Функциональные возможности
              </div>
              <h1 className="mt-5 max-w-4xl font-serif text-2xl leading-tight md:text-3xl">
                Система, в которой
                <br />
                клиент <em className="text-[#5c52e0]">видит прогресс</em>,
                <br />
                а специалист держит процесс
              </h1>
              <p className="mt-5 max-w-3xl text-base leading-8 text-[#707585] md:text-lg">
                Эта страница показывает не абстрактные обещания, а то, из каких функций реально собирается процесс:
                карточка клиента, кабинет клиента, задачи между сессиями, трек прогресса, оплаты, продукты и
                автоматизации сопровождения.
              </p>

              <div className="mt-8 grid gap-3 md:grid-cols-2">
                {highlights.map((item) => (
                  <div key={item} className="flex items-start gap-3 rounded-2xl border border-black/5 bg-[#fafaf8] px-4 py-4">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#2f8f7a]" />
                    <span className="text-sm leading-6 text-[#354052]">{item}</span>
                  </div>
                ))}
              </div>

              <div className="mt-8 flex flex-wrap gap-3">
                <Link
                  href="/login"
                  className="inline-flex items-center gap-2 rounded-full bg-[#5c52e0] px-6 py-3 text-sm font-semibold text-white transition hover:-translate-y-0.5"
                >
                  Попробовать с первым клиентом
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  href="/"
                  className="inline-flex items-center rounded-full border border-black/10 px-6 py-3 text-sm font-semibold text-[#1a1c24]"
                >
                  Вернуться на лендинг
                </Link>
              </div>
              <div className="mt-4">
                <Link href="/features/functions" className="text-sm font-medium text-[#5c52e0] underline underline-offset-4">
                  Полное описание функций
                </Link>
              </div>
            </div>

            <div className="rounded-[28px] border border-black/5 bg-[#fafaf8] p-6 shadow-sm">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="text-sm font-semibold text-[#1a1c24]">Карточка клиента</div>
                  <div className="text-xs text-[#707585]">6 недель в работе · 8 из 10 шагов завершены</div>
                </div>
                <div className="rounded-full border border-[#2f8f7a]/20 bg-[#2f8f7a]/10 px-3 py-1 text-xs font-semibold text-[#2f8f7a]">
                  Прогресс виден
                </div>
              </div>

              <div className="mt-5 rounded-2xl border border-[#5c52e0]/10 bg-[#5c52e0]/[0.06] p-4">
                <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#5c52e0]">Сдвиг недели</div>
                <p className="mt-2 text-sm leading-6 text-[#1a1c24]">
                  Клиент провел разговор, который откладывал три недели, и сам отметил, что впервые не вернулся к
                  привычному избеганию.
                </p>
              </div>

              <div className="mt-5">
                <div className="mb-2 flex items-center justify-between text-xs text-[#707585]">
                  <span>Трек программы</span>
                  <span>80%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-black/5">
                  <div className="h-full w-4/5 rounded-full bg-[linear-gradient(90deg,#5c52e0,#2f8f7a)]" />
                </div>
              </div>

              <div className="mt-5 space-y-3">
                {[
                  "Зафиксирован ключевой инсайт после встречи",
                  "Клиент выполнил 2 из 3 шагов между сессиями",
                  "Следующая встреча уже встроена в план работы",
                ].map((item) => (
                  <div key={item} className="flex items-start gap-3 rounded-xl border border-black/5 bg-white px-4 py-3">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#2f8f7a]" />
                    <span className="text-sm text-[#354052]">{item}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          {roleCards.map((card) => (
            <div key={card.title} className="rounded-[24px] border border-black/5 bg-white p-6 shadow-sm">
              <div className="text-sm font-semibold uppercase tracking-[0.08em] text-[#5c52e0]">{card.title}</div>
              <div className="mt-5 space-y-3">
                {card.points.map((point) => (
                  <div key={point} className="flex items-start gap-3 text-sm leading-6 text-[#354052]">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#2f8f7a]" />
                    <span>{point}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </section>

        <section id="capabilities" className="space-y-6">
          <div className="max-w-3xl">
            <div className="text-xs font-semibold uppercase tracking-[0.1em] text-[#5c52e0]">Возможности по функциям</div>
            <h2 className="mt-3 font-serif text-3xl leading-tight md:text-5xl">
              Из чего складывается
              <br />
              функциональный процесс
            </h2>
            <p className="mt-4 text-base leading-8 text-[#707585]">
              Ниже не просто список модулей, а логика, как каждая функция поддерживает ценность вашей работы и делает
              прогресс клиента видимым.
            </p>
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            {capabilityCards.map((card, index) => (
              <section
                key={card.title}
                className="rounded-[28px] border border-black/5 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-[0_20px_60px_rgba(0,0,0,0.06)] md:p-7"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.08em] text-[#5c52e0]">{`0${index + 1}`}</div>
                    <h3 className="mt-2 text-xl font-semibold text-[#1a1c24]">{card.title}</h3>
                  </div>
                  <div className="rounded-full border border-[#2f8f7a]/15 bg-[#2f8f7a]/10 px-3 py-1 text-[11px] font-semibold text-[#2f8f7a]">
                    {card.result}
                  </div>
                </div>

                <p className="mt-4 text-sm leading-7 text-[#707585]">{card.body}</p>

                <div className="mt-5">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#707585]">Как найти в меню</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {card.routes.map((route) => (
                      <span
                        key={`${card.title}-${route}`}
                        className="inline-flex items-center rounded-full border border-black/10 bg-[#fafaf8] px-3 py-1.5 text-xs font-medium leading-5 text-[#354052]"
                      >
                        {route}
                      </span>
                    ))}
                  </div>
                </div>
              </section>
            ))}
          </div>
        </section>

        <section className="rounded-[32px] border border-black/5 bg-white p-6 shadow-sm md:p-8">
          <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.1em] text-[#5c52e0]">Модули системы</div>
              <h2 className="mt-3 font-serif text-3xl leading-tight md:text-4xl">
                Куда смотреть
                <br />
                после входа в продукт
              </h2>
              <p className="mt-4 text-base leading-8 text-[#707585]">
                Если вам нужно быстро показать командно, где живут основные функции, используйте эти опорные точки.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {modules.map((module) => (
                <div key={module.route} className="rounded-2xl border border-black/5 bg-[#fafaf8] p-4">
                  <div className="text-sm font-semibold text-[#1a1c24]">{module.name}</div>
                  <div className="mt-3 inline-flex rounded-2xl border border-black/10 bg-white px-3 py-2 text-xs font-medium leading-5 text-[#354052]">
                    {module.route}
                  </div>
                  <p className="mt-3 text-sm leading-6 text-[#707585]">{module.note}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="launch" className="rounded-[32px] border border-black/5 bg-[linear-gradient(135deg,rgba(92,82,224,0.06),rgba(47,143,122,0.05))] p-6 shadow-sm md:p-8">
          <div className="max-w-3xl">
            <div className="text-xs font-semibold uppercase tracking-[0.1em] text-[#5c52e0]">Как запустить</div>
            <h2 className="mt-3 font-serif text-3xl leading-tight md:text-5xl">
              Минимальный сценарий,
              <br />
              чтобы система начала работать
            </h2>
            <p className="mt-4 text-base leading-8 text-[#707585]">
              Начинать можно без большого внедрения. Важно не количество настроек, а то, что клиент быстро получает
              понятный путь, а вы перестаете вести процесс только через память и переписки.
            </p>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {launchSteps.map((item) => (
              <div key={item.title} className="rounded-[24px] border border-black/5 bg-white p-5">
                <div className="text-sm font-semibold text-[#5c52e0]">Шаг {item.step}</div>
                <div className="mt-2 text-lg font-semibold text-[#1a1c24]">{item.title}</div>
                <p className="mt-3 text-sm leading-6 text-[#707585]">{item.body}</p>
                <div className="mt-4 inline-flex rounded-2xl border border-black/10 bg-[#fafaf8] px-3 py-2 text-xs font-medium leading-5 text-[#354052]">
                  {item.route}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/login"
              className="inline-flex items-center gap-2 rounded-full bg-[#5c52e0] px-6 py-3 text-sm font-semibold text-white transition hover:-translate-y-0.5"
            >
              Начать с первого клиента
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/"
              className="inline-flex items-center rounded-full border border-black/10 px-6 py-3 text-sm font-semibold text-[#1a1c24]"
            >
              Вернуться на лендинг
            </Link>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-4">
          <InfoCard
            icon={<FolderKanban className="h-5 w-5" />}
            title="Карточка и контекст"
            body="История клиента собрана в одном месте и не зависит от памяти специалиста."
          />
          <InfoCard
            icon={<Workflow className="h-5 w-5" />}
            title="Движение между встречами"
            body="Система связывает сессию, задачи, события и следующий шаг клиента."
          />
          <InfoCard
            icon={<CalendarDays className="h-5 w-5" />}
            title="Ритм и встречи"
            body="Расписание и подготовка к сессии встроены в процесс сопровождения."
          />
          <InfoCard
            icon={<CreditCard className="h-5 w-5" />}
            title="Оплата и доступ"
            body="Коммерческий шаг встроен в путь клиента, а не живет отдельно от работы."
          />
        </section>

        <section className="rounded-[32px] border border-black/5 bg-white p-6 shadow-sm md:p-8">
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-[#2f8f7a]/15 bg-[#2f8f7a]/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.08em] text-[#2f8f7a]">
                <LockKeyhole className="h-4 w-4" />
                Главный эффект
              </div>
              <p className="mt-4 font-serif text-2xl leading-relaxed md:text-4xl">
                Когда клиент видит свой путь, а система хранит контекст и шаги,
                <span className="text-[#5c52e0]"> ценность вашей работы становится очевидной.</span>
              </p>
            </div>
            <Link
              href="/login"
              className="inline-flex items-center justify-center gap-2 rounded-full bg-[#5c52e0] px-6 py-3 text-sm font-semibold text-white transition hover:-translate-y-0.5"
            >
              Открыть продукт
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-black/5 bg-[#f0ede8] px-6 py-8">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="font-serif text-lg text-[#707585]">
              Fibo<span className="text-[#5c52e0]">n</span>atty
            </div>
            <div className="mt-1 text-sm text-[#707585]">Система сопровождения, где прогресс клиента становится видимым.</div>
          </div>
          <div className="flex flex-wrap gap-5 text-sm text-[#707585]">
            <Link href="/">Лендинг</Link>
            <Link href="/login">Вход</Link>
            <a href="mailto:hello@fibonatty.ru">hello@fibonatty.ru</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function InfoCard({ icon, title, body }: { icon: ReactNode; title: string; body: string }) {
  return (
    <div className="rounded-[24px] border border-black/5 bg-white p-5 shadow-sm">
      <div className="inline-flex rounded-2xl bg-[#5c52e0]/[0.07] p-3 text-[#5c52e0]">{icon}</div>
      <div className="mt-4 text-base font-semibold text-[#1a1c24]">{title}</div>
      <p className="mt-2 text-sm leading-6 text-[#707585]">{body}</p>
    </div>
  );
}
